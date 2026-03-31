"""Stat definitions and metadata for batting and pitching statistics."""

from dataclasses import dataclass


@dataclass
class StatDef:
    """Definition of a baseball statistic."""
    key: str                # Column name in z-score table (e.g., "HR_z")
    display_name: str       # Human-readable name (e.g., "Home Runs")
    short_name: str         # Abbreviation (e.g., "HR")
    raw_column: str         # Column name in raw stats table (e.g., "HR")
    higher_is_better: bool  # True if higher values are better
    is_rate: bool           # True if it's a rate stat (BA, ERA) vs counting (HR, W)
    description: str


# Batting stats available for ranking
BATTING_STATS: dict[str, StatDef] = {
    "BA": StatDef("BA_z", "Batting Average", "BA", "BA", True, True,
                  "Hits divided by at-bats"),
    "OBP": StatDef("OBP_z", "On-Base Percentage", "OBP", "OBP", True, True,
                   "Frequency of reaching base (H+BB+HBP)/(AB+BB+HBP+SF)"),
    "SLG": StatDef("SLG_z", "Slugging Percentage", "SLG", "SLG", True, True,
                   "Total bases divided by at-bats"),
    "OPS": StatDef("OPS_z", "On-Base Plus Slugging", "OPS", "OPS", True, True,
                   "OBP + SLG, measures overall offensive value"),
    "HR": StatDef("HR_z", "Home Runs", "HR", "HR", True, False,
                  "Total home runs hit"),
    "RBI": StatDef("RBI_z", "Runs Batted In", "RBI", "RBI", True, False,
                   "Runs driven in by the batter"),
    "R": StatDef("R_z", "Runs Scored", "R", "R", True, False,
                 "Times the player scored a run"),
    "H": StatDef("H_z", "Hits", "H", "H", True, False,
                 "Total base hits"),
    "SB": StatDef("SB_z", "Stolen Bases", "SB", "SB", True, False,
                  "Bases stolen"),
    "BB": StatDef("BB_z", "Walks", "BB", "BB", True, False,
                  "Bases on balls (walks) received"),
}

# Pitching stats available for ranking
PITCHING_STATS: dict[str, StatDef] = {
    "ERA": StatDef("ERA_z", "Earned Run Average", "ERA", "ERA", False, True,
                   "Earned runs allowed per 9 innings (lower is better, z-score already inverted)"),
    "WHIP": StatDef("WHIP_z", "WHIP", "WHIP", "WHIP", False, True,
                    "Walks + hits per inning pitched (lower is better)"),
    "K9": StatDef("K9_z", "Strikeouts per 9 Inn", "K/9", "K9", True, True,
                  "Strikeouts per 9 innings pitched"),
    "BB9": StatDef("BB9_z", "Walks per 9 Inn", "BB/9", "BB9", False, True,
                   "Walks per 9 innings (lower is better)"),
    "W": StatDef("W_z", "Wins", "W", "W", True, False,
                 "Games won as pitcher of record"),
    "SO": StatDef("SO_z", "Strikeouts", "SO", "SO", True, False,
                  "Total strikeouts"),
    "SV": StatDef("SV_z", "Saves", "SV", "SV", True, False,
                  "Games saved as relief pitcher"),
    "CG": StatDef("CG_z", "Complete Games", "CG", "CG", True, False,
                  "Games pitched start to finish"),
    "SHO": StatDef("SHO_z", "Shutouts", "SHO", "SHO", True, False,
                   "Complete games with zero runs allowed"),
    "IP": StatDef("IP_z", "Innings Pitched", "IP", "IP", True, False,
                  "Total innings pitched"),
}

# Default stat selections and weights
DEFAULT_BATTING_STATS = ["OPS", "HR", "RBI", "BA", "SB"]
DEFAULT_BATTING_WEIGHTS = {"OPS": 30, "HR": 20, "RBI": 20, "BA": 15, "SB": 15}

DEFAULT_PITCHING_STATS = ["ERA", "W", "SO", "WHIP", "SV"]
DEFAULT_PITCHING_WEIGHTS = {"ERA": 30, "W": 20, "SO": 20, "WHIP": 15, "SV": 15}


BATTER_POSITIONS = ["All", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH"]
