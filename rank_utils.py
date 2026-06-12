# League of Legends rank tiers and party restrictions
# Based on Riot's actual queue restrictions

RANK_ORDER = [
    "IRON IV", "IRON III", "IRON II", "IRON I",
    "BRONZE IV", "BRONZE III", "BRONZE II", "BRONZE I",
    "SILVER IV", "SILVER III", "SILVER II", "SILVER I",
    "GOLD IV", "GOLD III", "GOLD II", "GOLD I",
    "PLATINUM IV", "PLATINUM III", "PLATINUM II", "PLATINUM I",
    "EMERALD IV", "EMERALD III", "EMERALD II", "EMERALD I",
    "DIAMOND IV", "DIAMOND III", "DIAMOND II", "DIAMOND I",
    "MASTER I",
    "GRANDMASTER I",
    "CHALLENGER I",
]

# Riot's party restriction groups — players can only queue together within the same group
RANK_GROUPS = [
    ["IRON IV", "IRON III", "IRON II", "IRON I", "BRONZE IV", "BRONZE III", "BRONZE II", "BRONZE I"],
    ["BRONZE IV", "BRONZE III", "BRONZE II", "BRONZE I", "SILVER IV", "SILVER III", "SILVER II", "SILVER I"],
    ["SILVER IV", "SILVER III", "SILVER II", "SILVER I", "GOLD IV", "GOLD III", "GOLD II", "GOLD I"],
    ["GOLD IV", "GOLD III", "GOLD II", "GOLD I", "PLATINUM IV", "PLATINUM III", "PLATINUM II", "PLATINUM I"],
    ["PLATINUM IV", "PLATINUM III", "PLATINUM II", "PLATINUM I", "EMERALD IV", "EMERALD III", "EMERALD II", "EMERALD I"],
    ["EMERALD IV", "EMERALD III", "EMERALD II", "EMERALD I", "DIAMOND IV", "DIAMOND III", "DIAMOND II", "DIAMOND I"],
    ["DIAMOND IV", "DIAMOND III", "DIAMOND II", "DIAMOND I", "MASTER I", "GRANDMASTER I", "CHALLENGER I"],
]

def normalize_rank(tier: str, division: str) -> str:
    """Convert API tier/division to a normalized rank string."""
    tier = tier.upper()
    division = division.upper()
    # Master, Grandmaster, Challenger don't have divisions
    if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
        return f"{tier} I"
    return f"{tier} {division}"

def get_playable_ranks(rank: str) -> list[str]:
    """Return all ranks that can queue together with the given rank."""
    rank = rank.upper()
    for group in RANK_GROUPS:
        if rank in group:
            return group
    return [rank]  # fallback: only exact rank

def ranks_can_play_together(rank_a: str, rank_b: str) -> bool:
    """Check if two ranks can queue together."""
    playable = get_playable_ranks(rank_a)
    return rank_b.upper() in [r.upper() for r in playable]

def winrate_compatible(wr_a: float, wr_b: float, tolerance: float = 10.0) -> bool:
    """Check if two winrates are within tolerance of each other."""
    return abs(wr_a - wr_b) <= tolerance
