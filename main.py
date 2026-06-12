"""
LFG Tool — FastAPI Middleware
Handles all business logic between the client and Supabase/Riot API.
Never exposes Supabase credentials to the client.
"""

import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from upstash_redis import Redis
from dotenv import load_dotenv

from riot_client import get_player_profile
from rank_utils import get_playable_ranks, winrate_compatible
from email_service import (
    send_request_notification,
    send_approval_email,
    send_denial_email,
    send_approval_confirmation_to_owner,
)

load_dotenv()

# ── Init services ─────────────────────────────────────────────────────────────

app = FastAPI(title="LFG Tool API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock this down once you have a domain
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
)

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL", ""),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN", ""),
)

MIN_GAMES = 20          # minimum ranked games to be listed
WR_TOLERANCE = 10.0     # ±% winrate window for matching
PAGE_SIZE = 10          # listings per page

# ── Request models ─────────────────────────────────────────────────────────────

class PostListingRequest(BaseModel):
    riot_id: str          # "GameName#TAG"
    region: str           # "NA1"
    role: str             # "Mid"
    notes: Optional[str] = ""
    email: str            # contact email

class BrowseRequest(BaseModel):
    riot_id: str
    region: str
    page: int = 1

class SendRequestModel(BaseModel):
    listing_id: str
    requester_riot_id: str
    requester_region: str
    requester_role: str
    requester_notes: Optional[str] = ""
    requester_email: str

class RespondToRequest(BaseModel):
    request_id: str
    listing_id: str       # for auth — must match requester's listing
    action: str           # "approve" or "deny"
    owner_riot_id: str    # to verify ownership

class FulfillRequest(BaseModel):
    listing_id: str
    riot_id: str          # for verification

# ── Rate limiting helper ───────────────────────────────────────────────────────

def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    try:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, window_seconds)
        return count <= limit
    except Exception:
        return True  # fail open if Redis is down

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/validate-riot-id")
def validate_riot_id(riot_id: str, region: str, request: Request):
    """Validate a Riot ID and return player stats. Used before posting/browsing."""
    ip = request.client.host
    if not rate_limit(f"validate:{ip}", limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Wait a minute.")

    # Cache check — same ID/region combo within 5 min returns cached result
    cache_key = f"profile:{riot_id.lower()}:{region.lower()}"
    try:
        cached = redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)
    except Exception:
        pass

    profile = get_player_profile(riot_id, region)
    
    if not profile["success"]:
        raise HTTPException(status_code=404, detail=profile["error"])

    if profile["rank"] == "UNRANKED":
        raise HTTPException(status_code=400, detail="You need at least 1 ranked game to use LFG.")

    # Cache for 5 minutes
    try:
        import json
        redis.set(cache_key, json.dumps(profile), ex=300)
    except Exception:
        pass

    return profile

@app.post("/listings")
def post_listing(body: PostListingRequest, request: Request):
    """Post yourself as available to play."""
    ip = request.client.host
    if not rate_limit(f"post:{ip}", limit=5, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many listing posts. Try again later.")

    # Validate Riot ID and pull stats
    profile = get_player_profile(body.riot_id, body.region)
    if not profile["success"]:
        raise HTTPException(status_code=404, detail=profile["error"])

    if profile["rank"] == "UNRANKED":
        raise HTTPException(status_code=400, detail="Must be ranked to post a listing.")

    if profile["total_games"] < MIN_GAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {MIN_GAMES} ranked games to post. You have {profile['total_games']}."
        )

    # Check for duplicate active listing
    existing = (
        supabase.table("listings")
        .select("id")
        .eq("region", body.region.upper())
        .eq("fulfilled", False)
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .execute()
    )
    # Simple check: if too many listings exist (can't filter by riot_id without decryption),
    # we proceed — duplicate prevention is best-effort via RSO (future)

    result = supabase.table("listings").insert({
        "riot_id": body.riot_id,        # TODO: encrypt with pgcrypto in production
        "region": body.region.upper(),
        "rank": profile["rank"],
        "tier": profile["tier"],
        "winrate": profile["winrate"],
        "total_games": profile["total_games"],
        "role": body.role,
        "notes": body.notes or "",
        "email": body.email,            # TODO: encrypt with pgcrypto in production
    }).execute()

    listing = result.data[0]
    return {
        "success": True,
        "listing_id": listing["id"],
        "expires_at": listing["expires_at"],
        "message": "You're listed! Your listing expires in 60 minutes.",
    }

@app.post("/listings/browse")
def browse_listings(body: BrowseRequest, request: Request):
    """Browse available players matching your rank and winrate."""
    ip = request.client.host
    if not rate_limit(f"browse:{ip}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests.")

    # Validate and get browsing player's stats
    profile = get_player_profile(body.riot_id, body.region)
    if not profile["success"]:
        raise HTTPException(status_code=404, detail=profile["error"])

    if profile["rank"] == "UNRANKED":
        raise HTTPException(status_code=400, detail="Must be ranked to browse listings.")

    my_rank = profile["rank"]
    my_wr = profile["winrate"]
    playable_ranks = get_playable_ranks(my_rank)

    # Fetch listings in the same region, not expired, not fulfilled
    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("listings")
        .select("id, rank, tier, winrate, total_games, role, notes, created_at")
        .eq("region", body.region.upper())
        .eq("fulfilled", False)
        .gt("expires_at", now)
        .order("created_at", desc=True)
        .execute()
    )

    all_listings = result.data

    # Filter by rank compatibility and winrate window
    compatible = [
        l for l in all_listings
        if l["rank"].upper() in [r.upper() for r in playable_ranks]
        and winrate_compatible(my_wr, l["winrate"], WR_TOLERANCE)
        and l["total_games"] >= MIN_GAMES
    ]

    # Paginate
    total = len(compatible)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(body.page, total_pages))
    start = (page - 1) * PAGE_SIZE
    page_listings = compatible[start:start + PAGE_SIZE]

    # Format for display — NO riot IDs exposed
    formatted = []
    for i, l in enumerate(page_listings):
        formatted.append({
            "number": start + i + 1,
            "id": l["id"],
            "rank": l["rank"],
            "role": l["role"],
            "winrate": l["winrate"],
            "total_games": l["total_games"],
            "notes": l["notes"] or "",
        })

    return {
        "listings": formatted,
        "page": page,
        "total_pages": total_pages,
        "total_results": total,
        "your_rank": my_rank,
        "your_winrate": my_wr,
    }

@app.post("/requests/send")
def send_request(body: SendRequestModel, request: Request):
    """Send a play request to a listing owner."""
    ip = request.client.host
    if not rate_limit(f"request:{ip}", limit=10, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many requests sent. Slow down.")

    # Validate requester's Riot ID
    profile = get_player_profile(body.requester_riot_id, body.requester_region)
    if not profile["success"]:
        raise HTTPException(status_code=404, detail="Your Riot ID could not be validated.")

    # Check listing exists and is active
    listing_result = (
        supabase.table("listings")
        .select("*")
        .eq("id", body.listing_id)
        .eq("fulfilled", False)
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .execute()
    )

    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Listing not found or has expired.")

    listing = listing_result.data[0]

    # Check for duplicate pending request
    dupe = (
        supabase.table("requests")
        .select("id")
        .eq("requester_riot_id", body.requester_riot_id)
        .eq("target_listing_id", body.listing_id)
        .eq("status", "pending")
        .execute()
    )
    if dupe.data:
        raise HTTPException(status_code=409, detail="You already sent a request to this player.")

    # Store the request
    req_result = supabase.table("requests").insert({
        "requester_riot_id": body.requester_riot_id,
        "requester_rank": profile["rank"],
        "requester_role": body.requester_role,
        "requester_winrate": profile["winrate"],
        "requester_notes": body.requester_notes or "",
        "requester_email": body.requester_email,
        "target_listing_id": body.listing_id,
        "status": "pending",
    }).execute()

    # Email the listing owner
    send_request_notification(
        target_email=listing["email"],
        requester_rank=profile["rank"],
        requester_role=body.requester_role,
        requester_wr=profile["winrate"],
        requester_notes=body.requester_notes or "",
    )

    return {
        "success": True,
        "request_id": req_result.data[0]["id"],
        "message": "Request sent! You'll get an email when they respond.",
    }

@app.post("/requests/respond")
def respond_to_request(body: RespondToRequest, request: Request):
    """Approve or deny an incoming request."""
    if body.action not in ("approve", "deny"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'deny'.")

    # Fetch the request
    req_result = (
        supabase.table("requests")
        .select("*")
        .eq("id", body.request_id)
        .eq("status", "pending")
        .execute()
    )
    if not req_result.data:
        raise HTTPException(status_code=404, detail="Request not found or already handled.")

    req = req_result.data[0]

    # Verify owner — check that provided riot_id matches the listing owner
    listing_result = (
        supabase.table("listings")
        .select("*")
        .eq("id", req["target_listing_id"])
        .execute()
    )
    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Listing not found.")

    listing = listing_result.data[0]

    if listing["riot_id"].lower() != body.owner_riot_id.lower():
        raise HTTPException(status_code=403, detail="You don't own this listing.")

    # Update request status
    supabase.table("requests").update({"status": body.action + "d"}).eq("id", body.request_id).execute()

    if body.action == "approve":
        # Mark listing as fulfilled
        supabase.table("listings").update({"fulfilled": True}).eq("id", req["target_listing_id"]).execute()

        # Email both parties with each other's Riot IDs
        send_approval_email(
            requester_email=req["requester_email"],
            target_riot_id=listing["riot_id"],
            target_rank=listing["rank"],
            target_role=listing["role"],
        )
        send_approval_confirmation_to_owner(
            owner_email=listing["email"],
            requester_riot_id=req["requester_riot_id"],
            requester_rank=req["requester_rank"],
            requester_role=req["requester_role"],
        )
        return {"success": True, "message": "Approved! Both players have been emailed each other's Riot IDs."}

    else:
        send_denial_email(requester_email=req["requester_email"])
        return {"success": True, "message": "Request denied."}

@app.get("/requests/pending/{listing_id}")
def get_pending_requests(listing_id: str, owner_riot_id: str, request: Request):
    """Get all pending requests for a listing. Owner must verify with their Riot ID."""
    # Verify ownership
    listing_result = (
        supabase.table("listings")
        .select("*")
        .eq("id", listing_id)
        .execute()
    )
    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Listing not found.")

    listing = listing_result.data[0]
    if listing["riot_id"].lower() != owner_riot_id.lower():
        raise HTTPException(status_code=403, detail="You don't own this listing.")

    # Fetch pending requests
    reqs = (
        supabase.table("requests")
        .select("id, requester_rank, requester_role, requester_winrate, requester_notes, created_at")
        .eq("target_listing_id", listing_id)
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )

    formatted = []
    for i, r in enumerate(reqs.data):
        formatted.append({
            "number": i + 1,
            "id": r["id"],
            "rank": r["requester_rank"],
            "role": r["requester_role"],
            "winrate": r["requester_winrate"],
            "notes": r["requester_notes"] or "",
        })

    return {
        "listing_id": listing_id,
        "pending_requests": formatted,
        "count": len(formatted),
    }

@app.post("/listings/fulfill")
def fulfill_listing(body: FulfillRequest):
    """Mark your own listing as done (you found a group)."""
    listing_result = (
        supabase.table("listings")
        .select("*")
        .eq("id", body.listing_id)
        .execute()
    )
    if not listing_result.data:
        raise HTTPException(status_code=404, detail="Listing not found.")

    listing = listing_result.data[0]
    if listing["riot_id"].lower() != body.riot_id.lower():
        raise HTTPException(status_code=403, detail="You don't own this listing.")

    supabase.table("listings").update({"fulfilled": True}).eq("id", body.listing_id).execute()
    return {"success": True, "message": "Listing removed. Have fun!"}

@app.delete("/cleanup")
def cleanup_expired():
    """Remove expired unfulfilled listings. Call this on a schedule."""
    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("listings")
        .delete()
        .lt("expires_at", now)
        .eq("fulfilled", False)
        .execute()
    )
    return {"deleted": len(result.data) if result.data else 0}

@app.get("/regions")
def list_regions():
    """Return supported regions."""
    return {
        "regions": [
            {"code": "NA1",  "name": "North America"},
            {"code": "EUW1", "name": "Europe West"},
            {"code": "EUN1", "name": "Europe Nordic & East"},
            {"code": "KR",   "name": "Korea"},
            {"code": "BR1",  "name": "Brazil"},
            {"code": "JP1",  "name": "Japan"},
            {"code": "OC1",  "name": "Oceania"},
            {"code": "TR1",  "name": "Turkey"},
            {"code": "RU",   "name": "Russia"},
            {"code": "LA1",  "name": "Latin America North"},
            {"code": "LA2",  "name": "Latin America South"},
        ]
    }
