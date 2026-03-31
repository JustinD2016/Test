#!/usr/bin/env python3
"""
Download Lahman baseball CSVs and build the SQLite database.

Usage:
    python scripts/build_db.py

Downloads from the Chadwick Bureau's baseballdatabank (canonical Lahman CSV source),
then imports into SQLite with indexes, derived stats, and pre-computed z-scores.
"""

import io
import os
import sqlite3
import zipfile
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "lahman.db"
# CSVs can be in data/csv/ or in the repo root (if uploaded directly)
CSV_DIR = REPO_ROOT / "data" / "csv"

# Chadwick Bureau baseballdatabank - canonical source for Lahman CSVs
DOWNLOAD_URL = "https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/master.zip"

TABLES_TO_IMPORT = [
    "People",
    "Batting",
    "Pitching",
    "Fielding",
    "Teams",
    "Parks",
    "HomeGames",
]


def find_csv_dir() -> Path:
    """Find where the CSV files are (repo root or data/csv/)."""
    # Check repo root first (user may have uploaded CSVs directly)
    root_csvs = list(REPO_ROOT.glob("*.csv"))
    if any(f.stem in TABLES_TO_IMPORT for f in root_csvs):
        print(f"Found CSV files in repo root: {REPO_ROOT}")
        return REPO_ROOT

    # Check data/csv/
    if CSV_DIR.exists():
        csv_files = list(CSV_DIR.glob("*.csv"))
        if any(f.stem in TABLES_TO_IMPORT for f in csv_files):
            print(f"Found CSV files in {CSV_DIR}")
            return CSV_DIR

    return CSV_DIR  # Default, will trigger download


def download_csvs():
    """Download and extract Lahman CSVs from Chadwick Bureau if not already present."""
    csv_dir = find_csv_dir()

    # Check if CSVs already exist
    existing = [f for f in csv_dir.glob("*.csv") if f.stem in TABLES_TO_IMPORT]
    if len(existing) >= len(TABLES_TO_IMPORT):
        print(f"CSVs already exist in {csv_dir} ({len(existing)} files). Skipping download.")
        return csv_dir

    # If some CSVs found in repo root, use those
    root_csvs = [f for f in REPO_ROOT.glob("*.csv") if f.stem in TABLES_TO_IMPORT]
    if len(root_csvs) >= len(TABLES_TO_IMPORT):
        print(f"Using CSV files from repo root.")
        return REPO_ROOT

    CSV_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Lahman database from {DOWNLOAD_URL}...")
    response = urlopen(DOWNLOAD_URL)
    zip_data = response.read()
    print(f"Downloaded {len(zip_data) / 1024 / 1024:.1f} MB")

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        for name in zf.namelist():
            basename = os.path.basename(name)
            if basename.endswith(".csv"):
                data = zf.read(name)
                dest = CSV_DIR / basename
                dest.write_bytes(data)
                print(f"  Extracted {basename}")

    print("Download complete.")
    return CSV_DIR


def import_csvs(conn: sqlite3.Connection, csv_dir: Path):
    """Import CSV files into SQLite tables."""
    for table_name in TABLES_TO_IMPORT:
        csv_path = csv_dir / f"{table_name}.csv"
        if not csv_path.exists():
            print(f"  WARNING: {csv_path} not found, skipping.")
            continue

        df = pd.read_csv(csv_path, low_memory=False)
        df.to_sql(table_name.lower(), conn, if_exists="replace", index=False)
        print(f"  Imported {table_name}: {len(df)} rows")


def create_indexes(conn: sqlite3.Connection):
    """Create indexes for fast queries."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_batting_player ON batting(playerID)",
        "CREATE INDEX IF NOT EXISTS idx_batting_player_year ON batting(playerID, yearID)",
        "CREATE INDEX IF NOT EXISTS idx_batting_year ON batting(yearID)",
        "CREATE INDEX IF NOT EXISTS idx_pitching_player ON pitching(playerID)",
        "CREATE INDEX IF NOT EXISTS idx_pitching_player_year ON pitching(playerID, yearID)",
        "CREATE INDEX IF NOT EXISTS idx_pitching_year ON pitching(yearID)",
        "CREATE INDEX IF NOT EXISTS idx_fielding_player ON fielding(playerID)",
        "CREATE INDEX IF NOT EXISTS idx_fielding_player_year ON fielding(playerID, yearID)",
        "CREATE INDEX IF NOT EXISTS idx_fielding_pos ON fielding(POS)",
        "CREATE INDEX IF NOT EXISTS idx_people_player ON people(playerID)",
        "CREATE INDEX IF NOT EXISTS idx_teams_year ON teams(yearID, teamID)",
    ]
    for sql in indexes:
        conn.execute(sql)
    conn.commit()
    print("  Created indexes.")


def build_batting_consolidated(conn: sqlite3.Connection):
    """
    Build a consolidated batting table that:
    1. Sums counting stats across stints (multi-team seasons)
    2. Computes derived rate stats (BA, OBP, SLG, OPS)
    """
    conn.execute("DROP TABLE IF EXISTS batting_consolidated")
    conn.execute("""
        CREATE TABLE batting_consolidated AS
        SELECT
            playerID,
            yearID,
            SUM(G) as G,
            SUM(AB) as AB,
            SUM(R) as R,
            SUM(H) as H,
            SUM("2B") as "2B",
            SUM("3B") as "3B",
            SUM(HR) as HR,
            SUM(RBI) as RBI,
            SUM(SB) as SB,
            SUM(CS) as CS,
            SUM(BB) as BB,
            SUM(SO) as SO,
            SUM(IBB) as IBB,
            SUM(HBP) as HBP,
            SUM(SH) as SH,
            SUM(SF) as SF,
            SUM(GIDP) as GIDP,
            -- Plate appearances
            SUM(AB) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) + SUM(COALESCE(SF,0)) + SUM(COALESCE(SH,0)) as PA,
            -- Derived rate stats (NULL if AB=0)
            CASE WHEN SUM(AB) > 0
                THEN CAST(SUM(H) AS REAL) / SUM(AB)
                ELSE NULL END as BA,
            CASE WHEN (SUM(AB) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) + SUM(COALESCE(SF,0))) > 0
                THEN CAST(SUM(H) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) AS REAL) /
                     (SUM(AB) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) + SUM(COALESCE(SF,0)))
                ELSE NULL END as OBP,
            CASE WHEN SUM(AB) > 0
                THEN CAST(SUM(H) + SUM("2B") + 2*SUM("3B") + 3*SUM(HR) AS REAL) / SUM(AB)
                ELSE NULL END as SLG,
            CASE WHEN SUM(AB) > 0 AND (SUM(AB) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) + SUM(COALESCE(SF,0))) > 0
                THEN (CAST(SUM(H) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) AS REAL) /
                      (SUM(AB) + SUM(COALESCE(BB,0)) + SUM(COALESCE(HBP,0)) + SUM(COALESCE(SF,0))))
                   + (CAST(SUM(H) + SUM("2B") + 2*SUM("3B") + 3*SUM(HR) AS REAL) / SUM(AB))
                ELSE NULL END as OPS
        FROM batting
        GROUP BY playerID, yearID
    """)
    conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batcon_player_year ON batting_consolidated(playerID, yearID)")
    conn.commit()
    print("  Built batting_consolidated table.")


def build_pitching_consolidated(conn: sqlite3.Connection):
    """
    Build a consolidated pitching table that:
    1. Sums counting stats across stints
    2. Computes derived stats (IP, ERA, WHIP, K9, BB9)
    """
    conn.execute("DROP TABLE IF EXISTS pitching_consolidated")
    conn.execute("""
        CREATE TABLE pitching_consolidated AS
        SELECT
            playerID,
            yearID,
            SUM(W) as W,
            SUM(L) as L,
            SUM(G) as G,
            SUM(GS) as GS,
            SUM(CG) as CG,
            SUM(SHO) as SHO,
            SUM(SV) as SV,
            SUM(IPouts) as IPouts,
            SUM(H) as H,
            SUM(ER) as ER,
            SUM(HR) as HR,
            SUM(BB) as BB,
            SUM(SO) as SO,
            SUM(COALESCE(IBB,0)) as IBB,
            SUM(COALESCE(WP,0)) as WP,
            SUM(COALESCE(HBP,0)) as HBP,
            SUM(COALESCE(BK,0)) as BK,
            SUM(COALESCE(BFP,0)) as BFP,
            SUM(R) as R,
            SUM(COALESCE(SH,0)) as SH,
            SUM(COALESCE(SF,0)) as SF,
            SUM(COALESCE(GIDP,0)) as GIDP,
            -- Derived stats
            CAST(SUM(IPouts) AS REAL) / 3.0 as IP,
            CASE WHEN SUM(IPouts) > 0
                THEN CAST(SUM(ER) AS REAL) * 27.0 / SUM(IPouts)
                ELSE NULL END as ERA,
            CASE WHEN SUM(IPouts) > 0
                THEN CAST(SUM(BB) + SUM(H) AS REAL) * 3.0 / SUM(IPouts)
                ELSE NULL END as WHIP,
            CASE WHEN SUM(IPouts) > 0
                THEN CAST(SUM(SO) AS REAL) * 27.0 / SUM(IPouts)
                ELSE NULL END as K9,
            CASE WHEN SUM(IPouts) > 0
                THEN CAST(SUM(BB) AS REAL) * 27.0 / SUM(IPouts)
                ELSE NULL END as BB9,
            CASE WHEN SUM(IPouts) > 0
                THEN CAST(SUM(SO) AS REAL) / NULLIF(SUM(BB), 0)
                ELSE NULL END as KBB
        FROM pitching
        GROUP BY playerID, yearID
    """)
    conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pitcon_player_year ON pitching_consolidated(playerID, yearID)")
    conn.commit()
    print("  Built pitching_consolidated table.")


def build_league_averages(conn: sqlite3.Connection):
    """Compute league averages per year for batting and pitching stats."""
    # Batting league averages (only qualified players: PA >= 100)
    conn.execute("DROP TABLE IF EXISTS league_avg_batting")
    conn.execute("""
        CREATE TABLE league_avg_batting AS
        SELECT
            yearID,
            COUNT(*) as n_players,
            AVG(BA) as lg_BA,
            AVG(OBP) as lg_OBP,
            AVG(SLG) as lg_SLG,
            AVG(OPS) as lg_OPS,
            AVG(HR) as lg_HR,
            AVG(RBI) as lg_RBI,
            AVG(R) as lg_R,
            AVG(H) as lg_H,
            AVG(SB) as lg_SB,
            AVG(BB) as lg_BB,
            AVG(SO) as lg_SO,
            AVG(PA) as lg_PA,
            -- Standard deviations for z-score computation
            COALESCE(NULLIF(STDEV_POP_BA, 0), 1) as std_BA,
            COALESCE(NULLIF(STDEV_POP_OBP, 0), 1) as std_OBP,
            COALESCE(NULLIF(STDEV_POP_SLG, 0), 1) as std_SLG,
            COALESCE(NULLIF(STDEV_POP_OPS, 0), 1) as std_OPS,
            COALESCE(NULLIF(STDEV_POP_HR, 0), 1) as std_HR,
            COALESCE(NULLIF(STDEV_POP_RBI, 0), 1) as std_RBI,
            COALESCE(NULLIF(STDEV_POP_R, 0), 1) as std_R,
            COALESCE(NULLIF(STDEV_POP_H, 0), 1) as std_H,
            COALESCE(NULLIF(STDEV_POP_SB, 0), 1) as std_SB,
            COALESCE(NULLIF(STDEV_POP_BB, 0), 1) as std_BB,
            COALESCE(NULLIF(STDEV_POP_SO, 0), 1) as std_SO
        FROM (
            SELECT
                yearID, BA, OBP, SLG, OPS, HR, RBI, R, H, SB, BB, SO, PA,
                -- SQLite doesn't have STDDEV, we compute it via subquery
                0 as STDEV_POP_BA, 0 as STDEV_POP_OBP, 0 as STDEV_POP_SLG,
                0 as STDEV_POP_OPS, 0 as STDEV_POP_HR, 0 as STDEV_POP_RBI,
                0 as STDEV_POP_R, 0 as STDEV_POP_H, 0 as STDEV_POP_SB,
                0 as STDEV_POP_BB, 0 as STDEV_POP_SO
            FROM batting_consolidated
            WHERE PA >= 100 AND BA IS NOT NULL
        )
        GROUP BY yearID
    """)
    conn.commit()

    # Pitching league averages (qualified: IP >= 30)
    conn.execute("DROP TABLE IF EXISTS league_avg_pitching")
    conn.execute("""
        CREATE TABLE league_avg_pitching AS
        SELECT
            yearID,
            COUNT(*) as n_players,
            AVG(ERA) as lg_ERA,
            AVG(WHIP) as lg_WHIP,
            AVG(K9) as lg_K9,
            AVG(BB9) as lg_BB9,
            AVG(W) as lg_W,
            AVG(L) as lg_L,
            AVG(SO) as lg_SO,
            AVG(SV) as lg_SV,
            AVG(IP) as lg_IP,
            AVG(CG) as lg_CG,
            AVG(SHO) as lg_SHO
        FROM pitching_consolidated
        WHERE IP >= 30 AND ERA IS NOT NULL
        GROUP BY yearID
    """)
    conn.commit()
    print("  Built league average tables.")


def build_zscores_with_pandas(conn: sqlite3.Connection):
    """
    Compute z-scores using pandas (since SQLite lacks STDDEV).
    For each stat in each year, z = (value - mean) / std.
    """
    # Batting z-scores
    bat_df = pd.read_sql("SELECT * FROM batting_consolidated WHERE PA >= 100 AND BA IS NOT NULL", conn)

    batting_stats = ["BA", "OBP", "SLG", "OPS", "HR", "RBI", "R", "H", "SB", "BB"]
    bat_grouped = bat_df.groupby("yearID")

    zscore_cols = {}
    for stat in batting_stats:
        mean = bat_grouped[stat].transform("mean")
        std = bat_grouped[stat].transform("std").replace(0, 1).fillna(1)
        zscore_cols[f"{stat}_z"] = (bat_df[stat] - mean) / std

    bat_zscores = bat_df[["playerID", "yearID", "PA"]].copy()
    for col, values in zscore_cols.items():
        bat_zscores[col] = values

    bat_zscores.to_sql("batting_zscores", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batz_player_year ON batting_zscores(playerID, yearID)")
    conn.commit()
    print(f"  Built batting_zscores: {len(bat_zscores)} rows")

    # Pitching z-scores
    pit_df = pd.read_sql("SELECT * FROM pitching_consolidated WHERE IP >= 30 AND ERA IS NOT NULL", conn)

    # For pitching: ERA, WHIP, BB9 are "lower is better" -> negate z-score
    pitching_stats_config = {
        "ERA": True,    # lower is better -> negate
        "WHIP": True,
        "K9": False,    # higher is better
        "BB9": True,    # lower is better
        "W": False,
        "SO": False,
        "SV": False,
        "CG": False,
        "SHO": False,
        "IP": False,
        "KBB": False,   # higher is better (K/BB ratio)
    }

    pit_grouped = pit_df.groupby("yearID")
    zscore_cols = {}
    for stat, invert in pitching_stats_config.items():
        if stat not in pit_df.columns:
            continue
        mean = pit_grouped[stat].transform("mean")
        std = pit_grouped[stat].transform("std").replace(0, 1).fillna(1)
        z = (pit_df[stat] - mean) / std
        if invert:
            z = -z  # Negate so higher z = better
        zscore_cols[f"{stat}_z"] = z

    pit_zscores = pit_df[["playerID", "yearID", "IP"]].copy()
    for col, values in zscore_cols.items():
        pit_zscores[col] = values

    pit_zscores.to_sql("pitching_zscores", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pitz_player_year ON pitching_zscores(playerID, yearID)")
    conn.commit()
    print(f"  Built pitching_zscores: {len(pit_zscores)} rows")

    # Update league_avg_batting with actual std values
    bat_std = bat_df.groupby("yearID")[batting_stats].std().fillna(1).replace(0, 1)
    bat_mean = bat_df.groupby("yearID")[batting_stats].mean()

    league_bat = bat_mean.join(bat_std, lsuffix="_mean", rsuffix="_std").reset_index()
    # Add count
    counts = bat_df.groupby("yearID").size().reset_index(name="n_players")
    league_bat = league_bat.merge(counts, on="yearID")

    league_bat.to_sql("league_avg_batting", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lgbat_year ON league_avg_batting(yearID)")
    conn.commit()

    # Update league_avg_pitching with actual std values
    pit_stats_list = [s for s in pitching_stats_config.keys() if s in pit_df.columns]
    pit_std = pit_df.groupby("yearID")[pit_stats_list].std().fillna(1).replace(0, 1)
    pit_mean = pit_df.groupby("yearID")[pit_stats_list].mean()

    league_pit = pit_mean.join(pit_std, lsuffix="_mean", rsuffix="_std").reset_index()
    counts = pit_df.groupby("yearID").size().reset_index(name="n_players")
    league_pit = league_pit.merge(counts, on="yearID")

    league_pit.to_sql("league_avg_pitching", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lgpit_year ON league_avg_pitching(yearID)")
    conn.commit()
    print("  Updated league averages with std values.")


def build_primary_positions(conn: sqlite3.Connection):
    """Determine each player's primary position per year (most games played)."""
    conn.execute("DROP TABLE IF EXISTS primary_positions")
    conn.execute("""
        CREATE TABLE primary_positions AS
        SELECT playerID, yearID, POS, G
        FROM (
            SELECT
                playerID, yearID, POS, G,
                ROW_NUMBER() OVER (PARTITION BY playerID, yearID ORDER BY G DESC) as rn
            FROM fielding
        )
        WHERE rn = 1
    """)
    conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pripos_player_year ON primary_positions(playerID, yearID)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pripos_pos ON primary_positions(POS)")
    conn.commit()
    print("  Built primary_positions table.")


def build_park_factors(conn: sqlite3.Connection):
    """
    Compute park factors from Teams table following Baseball Reference methodology.
    PF = (home_runs_scored + home_runs_allowed) / (road_runs_scored + road_runs_allowed)
    normalized so 1.0 = neutral park.

    Uses 3-year rolling average when available.
    """
    teams_df = pd.read_sql("""
        SELECT yearID, teamID, franchID, park,
               Ghome, R, RA,
               -- Total games, home runs scored/allowed at home vs away
               -- The Teams table has total R and RA but not split by home/road.
               -- We approximate using HomeGames if available.
               W, L, G
        FROM teams
        WHERE yearID >= 1871
        ORDER BY yearID, teamID
    """, conn)

    # Simple approximation: use the Teams table R/RA and assume
    # home/road split roughly even, adjusted by home W-L record.
    # For a more accurate factor, we'd need game-level data.
    # We'll compute a basic factor: lgR_per_game / teamR_per_game ratio
    # as an approximation, then use a 3-year rolling average.

    # Group by year to get league averages
    lg_avgs = teams_df.groupby("yearID").agg(
        lg_R=("R", "sum"),
        lg_G=("G", "sum"),
    ).reset_index()
    lg_avgs["lg_rpg"] = lg_avgs["lg_R"] / lg_avgs["lg_G"]

    teams_df = teams_df.merge(lg_avgs[["yearID", "lg_rpg"]], on="yearID")
    teams_df["team_rpg"] = (teams_df["R"] + teams_df["RA"]) / teams_df["G"]
    teams_df["pf_raw"] = teams_df["team_rpg"] / (2 * teams_df["lg_rpg"])

    # 3-year rolling average park factor per team
    teams_df = teams_df.sort_values(["teamID", "yearID"])
    teams_df["pf"] = (
        teams_df.groupby("teamID")["pf_raw"]
        .transform(lambda x: x.rolling(3, min_periods=1, center=True).mean())
    )

    # Store park factors
    pf_df = teams_df[["yearID", "teamID", "pf_raw", "pf"]].copy()
    pf_df.to_sql("park_factors", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pf_team_year ON park_factors(teamID, yearID)")
    conn.commit()
    print(f"  Built park_factors: {len(pf_df)} rows")


def main():
    print("=== Building Lahman Baseball Database ===\n")

    # Step 1: Find/Download CSVs
    print("Step 1: Locating CSVs...")
    csv_dir = download_csvs()

    # Step 2: Create SQLite database
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"\nRemoved existing database at {DB_PATH}")

    print(f"\nStep 2: Creating SQLite database at {DB_PATH}...")
    conn = sqlite3.connect(str(DB_PATH))

    try:
        print("\nStep 3: Importing CSVs...")
        import_csvs(conn, csv_dir)

        print("\nStep 4: Creating indexes...")
        create_indexes(conn)

        print("\nStep 5: Building consolidated batting table...")
        build_batting_consolidated(conn)

        print("\nStep 6: Building consolidated pitching table...")
        build_pitching_consolidated(conn)

        print("\nStep 7: Building primary positions...")
        build_primary_positions(conn)

        print("\nStep 8: Computing park factors...")
        build_park_factors(conn)

        print("\nStep 9: Computing league averages and z-scores...")
        build_league_averages(conn)
        build_zscores_with_pandas(conn)

        # Drop raw import tables to save space (CSVs are in the repo)
        print("\nStep 10: Dropping raw import tables to reduce DB size...")
        for table in ["batting", "pitching", "fielding", "teams", "parks", "homegames"]:
            conn.execute(f"DROP TABLE IF EXISTS [{table}]")
        conn.execute("VACUUM")
        conn.commit()
        print("  Dropped raw tables and vacuumed.")

        # Print summary
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"\n=== Database built successfully! ===")
        print(f"Location: {DB_PATH}")
        print(f"Tables: {', '.join(t[0] for t in tables)}")
        for table in tables:
            count = cursor.execute(f"SELECT COUNT(*) FROM [{table[0]}]").fetchone()[0]
            print(f"  {table[0]}: {count} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
