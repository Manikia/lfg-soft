import os
import requests
from typing import Optional
from rank_utils import normalize_rank

RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")

# Region to routing mapping
ROUTING = {
    "NA1": "americas",
    "BR1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    "EUW1": "europe",
    "EUN1": "europe",
    "TR1": "europe",
    "RU": "europe",
    "KR": "asia",
    "JP1": "asia",
    "OC1": "sea",
    "PH2": "sea",
    "SG2": "sea",
    "TH2": "sea",
    "TW2": "sea",
    "VN2": "sea",
}

def get_headers():
    return {"X-Riot-Token": RIOT_API_KEY}

def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> Optional[dict]:
    """Look up account PUUID by Riot ID (gameName#tagLine)."""
    routing = ROUTING.get(region.upper(), "americas")
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    r = requests.get(url, headers=get_headers(), timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def get_summoner_by_puuid(puuid: str, region: str) -> Optional[dict]:
    """Get summoner data from PUUID."""
    url = f"https://{region.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    r = requests.get(url, headers=get_headers(), timeout=10)
    if r.status_code == 200:
        return r.json()
    return None

def get_ranked_stats(summoner_id: str, region: str) -> Optional[dict]:
    """Get ranked stats for a summoner. Returns solo queue data."""
    url = f"https://{region.lower()}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    r = requests.get(url, headers=get_headers(), timeout=10)
    if r.status_code != 200:
        return None
    
    entries = r.json()
    # Find solo ranked queue
    for entry in entries:
        if entry.get("queueType") == "RANKED_SOLO_5x5":
            wins = entry.get("wins", 0)
            losses = entry.get("losses", 0)
            total = wins + losses
            winrate = round((wins / total) * 100, 1) if total > 0 else 0.0
            return {
                "tier": entry["tier"],
                "division": entry["rank"],
                "rank": normalize_rank(entry["tier"], entry["rank"]),
                "lp": entry.get("leaguePoints", 0),
                "wins": wins,
                "losses": losses,
                "total_games": total,
                "winrate": winrate,
            }
    return None  # Unranked

def get_player_profile(riot_id: str, region: str) -> dict:
    """
    Full lookup: takes 'GameName#TAG' and region, returns profile data.
    Returns dict with success flag and player data or error message.
    """
    if "#" not in riot_id:
        return {"success": False, "error": "Invalid Riot ID format. Use GameName#TAG"}
    
    game_name, tag_line = riot_id.rsplit("#", 1)
    
    # Step 1: Get account (PUUID)
    account = get_account_by_riot_id(game_name, tag_line, region)
    if not account:
        return {"success": False, "error": "Riot ID not found. Check spelling and tag."}
    
    puuid = account["puuid"]
    
    # Step 2: Get summoner ID
    summoner = get_summoner_by_puuid(puuid, region)
    if not summoner:
        return {"success": False, "error": "Could not fetch summoner data."}
    
    # Step 3: Get ranked stats
    ranked = get_ranked_stats(summoner["id"], region)
    
    if ranked:
        return {
            "success": True,
            "riot_id": riot_id,
            "region": region.upper(),
            "puuid": puuid,
            "summoner_id": summoner["id"],
            "rank": ranked["rank"],
            "tier": ranked["tier"],
            "division": ranked["division"],
            "lp": ranked["lp"],
            "wins": ranked["wins"],
            "losses": ranked["losses"],
            "total_games": ranked["total_games"],
            "winrate": ranked["winrate"],
        }
    else:
        # Unranked player — still valid but excluded from ranked LFG
        return {
            "success": True,
            "riot_id": riot_id,
            "region": region.upper(),
            "puuid": puuid,
            "summoner_id": summoner["id"],
            "rank": "UNRANKED",
            "tier": "UNRANKED",
            "division": None,
            "lp": 0,
            "wins": 0,
            "losses": 0,
            "total_games": 0,
            "winrate": 0.0,
        }
