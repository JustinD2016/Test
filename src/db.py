"""Database connection and query layer for the Lahman baseball database."""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "lahman.db"


@st.cache_resource
def get_connection() -> sqlite3.Connection:
    """Get a cached SQLite connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a SQL query and return a DataFrame."""
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


@st.cache_data(ttl=3600)
def get_year_range() -> tuple[int, int]:
    """Get the min and max year in the database."""
    df = query_df("SELECT MIN(yearID) as min_year, MAX(yearID) as max_year FROM batting_consolidated")
    return int(df.iloc[0]["min_year"]), int(df.iloc[0]["max_year"])


@st.cache_data(ttl=3600)
def get_positions() -> list[str]:
    """Get all available positions."""
    df = query_df("SELECT DISTINCT POS FROM primary_positions ORDER BY POS")
    return df["POS"].tolist()


@st.cache_data(ttl=3600)
def get_batting_stats(start_year: int, end_year: int, position: str | None = None,
                      min_pa: int = 100) -> pd.DataFrame:
    """
    Get aggregated batting stats for players in a year range, optionally filtered by position.
    Returns one row per player with career totals within the range.
    """
    pos_join = ""
    pos_where = ""
    params: list = [start_year, end_year, min_pa]

    if position and position != "All":
        if position == "OF":
            pos_join = "INNER JOIN primary_positions pp ON b.playerID = pp.playerID AND b.yearID = pp.yearID"
            pos_where = "AND pp.POS IN ('LF', 'CF', 'RF')"
        else:
            pos_join = "INNER JOIN primary_positions pp ON b.playerID = pp.playerID AND b.yearID = pp.yearID"
            pos_where = "AND pp.POS = ?"
            params.append(position)

    sql = f"""
        SELECT
            b.playerID,
            p.nameFirst || ' ' || p.nameLast as name,
            MIN(b.yearID) as first_year,
            MAX(b.yearID) as last_year,
            COUNT(DISTINCT b.yearID) as seasons,
            SUM(b.G) as G,
            SUM(b.AB) as AB,
            SUM(b.PA) as PA,
            SUM(b.R) as R,
            SUM(b.H) as H,
            SUM(b."2B") as "2B",
            SUM(b."3B") as "3B",
            SUM(b.HR) as HR,
            SUM(b.RBI) as RBI,
            SUM(b.SB) as SB,
            SUM(b.BB) as BB,
            SUM(b.SO) as SO,
            -- Rate stats computed from totals
            CASE WHEN SUM(b.AB) > 0
                THEN CAST(SUM(b.H) AS REAL) / SUM(b.AB)
                ELSE NULL END as BA,
            CASE WHEN (SUM(b.AB) + SUM(COALESCE(b.BB,0)) + SUM(COALESCE(b.HBP,0)) + SUM(COALESCE(b.SF,0))) > 0
                THEN CAST(SUM(b.H) + SUM(COALESCE(b.BB,0)) + SUM(COALESCE(b.HBP,0)) AS REAL) /
                     (SUM(b.AB) + SUM(COALESCE(b.BB,0)) + SUM(COALESCE(b.HBP,0)) + SUM(COALESCE(b.SF,0)))
                ELSE NULL END as OBP,
            CASE WHEN SUM(b.AB) > 0
                THEN CAST(SUM(b.H) + SUM(b."2B") + 2*SUM(b."3B") + 3*SUM(b.HR) AS REAL) / SUM(b.AB)
                ELSE NULL END as SLG
        FROM batting_consolidated b
        INNER JOIN people p ON b.playerID = p.playerID
        {pos_join}
        WHERE b.yearID BETWEEN ? AND ?
        {pos_where}
        GROUP BY b.playerID
        HAVING SUM(b.PA) >= ?
        ORDER BY SUM(b.H) DESC
    """
    df = query_df(sql, tuple(params))
    if not df.empty:
        df["OPS"] = df["OBP"].fillna(0) + df["SLG"].fillna(0)
    return df


@st.cache_data(ttl=3600)
def get_pitching_stats(start_year: int, end_year: int, min_ip: int = 30) -> pd.DataFrame:
    """Get aggregated pitching stats for players in a year range."""
    sql = """
        SELECT
            pc.playerID,
            p.nameFirst || ' ' || p.nameLast as name,
            MIN(pc.yearID) as first_year,
            MAX(pc.yearID) as last_year,
            COUNT(DISTINCT pc.yearID) as seasons,
            SUM(pc.W) as W,
            SUM(pc.L) as L,
            SUM(pc.G) as G,
            SUM(pc.GS) as GS,
            SUM(pc.CG) as CG,
            SUM(pc.SHO) as SHO,
            SUM(pc.SV) as SV,
            SUM(pc.IPouts) as IPouts,
            CAST(SUM(pc.IPouts) AS REAL) / 3.0 as IP,
            SUM(pc.H) as H,
            SUM(pc.ER) as ER,
            SUM(pc.HR) as HR,
            SUM(pc.BB) as BB,
            SUM(pc.SO) as SO,
            CASE WHEN SUM(pc.IPouts) > 0
                THEN CAST(SUM(pc.ER) AS REAL) * 27.0 / SUM(pc.IPouts)
                ELSE NULL END as ERA,
            CASE WHEN SUM(pc.IPouts) > 0
                THEN CAST(SUM(pc.BB) + SUM(pc.H) AS REAL) * 3.0 / SUM(pc.IPouts)
                ELSE NULL END as WHIP,
            CASE WHEN SUM(pc.IPouts) > 0
                THEN CAST(SUM(pc.SO) AS REAL) * 27.0 / SUM(pc.IPouts)
                ELSE NULL END as K9,
            CASE WHEN SUM(pc.IPouts) > 0
                THEN CAST(SUM(pc.BB) AS REAL) * 27.0 / SUM(pc.IPouts)
                ELSE NULL END as BB9
        FROM pitching_consolidated pc
        INNER JOIN people p ON pc.playerID = p.playerID
        WHERE pc.yearID BETWEEN ? AND ?
        GROUP BY pc.playerID
        HAVING CAST(SUM(pc.IPouts) AS REAL) / 3.0 >= ?
        ORDER BY SUM(pc.SO) DESC
    """
    return query_df(sql, (start_year, end_year, min_ip))


@st.cache_data(ttl=3600)
def get_batting_zscores(start_year: int, end_year: int, position: str | None = None,
                        min_pa: int = 100) -> pd.DataFrame:
    """
    Get z-scores for batting, aggregated across years weighted by PA.
    Returns one row per player with PA-weighted average z-scores.
    """
    pos_join = ""
    pos_where = ""
    params: list = [start_year, end_year, min_pa]

    if position and position != "All":
        if position == "OF":
            pos_join = "INNER JOIN primary_positions pp ON bz.playerID = pp.playerID AND bz.yearID = pp.yearID"
            pos_where = "AND pp.POS IN ('LF', 'CF', 'RF')"
        else:
            pos_join = "INNER JOIN primary_positions pp ON bz.playerID = pp.playerID AND bz.yearID = pp.yearID"
            pos_where = "AND pp.POS = ?"
            params.append(position)

    sql = f"""
        SELECT
            bz.playerID,
            p.nameFirst || ' ' || p.nameLast as name,
            SUM(bz.PA) as total_PA,
            COUNT(*) as seasons,
            -- PA-weighted average z-scores
            SUM(bz.BA_z * bz.PA) / SUM(bz.PA) as BA_z,
            SUM(bz.OBP_z * bz.PA) / SUM(bz.PA) as OBP_z,
            SUM(bz.SLG_z * bz.PA) / SUM(bz.PA) as SLG_z,
            SUM(bz.OPS_z * bz.PA) / SUM(bz.PA) as OPS_z,
            SUM(bz.HR_z * bz.PA) / SUM(bz.PA) as HR_z,
            SUM(bz.RBI_z * bz.PA) / SUM(bz.PA) as RBI_z,
            SUM(bz.R_z * bz.PA) / SUM(bz.PA) as R_z,
            SUM(bz.H_z * bz.PA) / SUM(bz.PA) as H_z,
            SUM(bz.SB_z * bz.PA) / SUM(bz.PA) as SB_z,
            SUM(bz.BB_z * bz.PA) / SUM(bz.PA) as BB_z
        FROM batting_zscores bz
        INNER JOIN people p ON bz.playerID = p.playerID
        {pos_join}
        WHERE bz.yearID BETWEEN ? AND ?
        {pos_where}
        GROUP BY bz.playerID
        HAVING SUM(bz.PA) >= ?
    """
    return query_df(sql, tuple(params))


@st.cache_data(ttl=3600)
def get_pitching_zscores(start_year: int, end_year: int, min_ip: int = 30) -> pd.DataFrame:
    """
    Get z-scores for pitching, aggregated across years weighted by IP.
    """
    sql = """
        SELECT
            pz.playerID,
            p.nameFirst || ' ' || p.nameLast as name,
            SUM(pz.IP) as total_IP,
            COUNT(*) as seasons,
            -- IP-weighted average z-scores
            SUM(pz.ERA_z * pz.IP) / SUM(pz.IP) as ERA_z,
            SUM(pz.WHIP_z * pz.IP) / SUM(pz.IP) as WHIP_z,
            SUM(pz.K9_z * pz.IP) / SUM(pz.IP) as K9_z,
            SUM(pz.BB9_z * pz.IP) / SUM(pz.IP) as BB9_z,
            SUM(pz.W_z * pz.IP) / SUM(pz.IP) as W_z,
            SUM(pz.SO_z * pz.IP) / SUM(pz.IP) as SO_z,
            SUM(pz.SV_z * pz.IP) / SUM(pz.IP) as SV_z,
            SUM(pz.CG_z * pz.IP) / SUM(pz.IP) as CG_z,
            SUM(pz.SHO_z * pz.IP) / SUM(pz.IP) as SHO_z,
            SUM(pz.IP_z * pz.IP) / SUM(pz.IP) as IP_z
        FROM pitching_zscores pz
        INNER JOIN people p ON pz.playerID = p.playerID
        WHERE pz.yearID BETWEEN ? AND ?
        GROUP BY pz.playerID
        HAVING SUM(pz.IP) >= ?
    """
    return query_df(sql, (start_year, end_year, min_ip))
