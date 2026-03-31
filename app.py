"""
Baseball Player Comparison Tool

Compare historical baseball players across any era using the Lahman database.
Rank players by configurable weighted stats with era-adjusted z-scores.
"""

import streamlit as st

st.set_page_config(
    page_title="Baseball Player Ranker",
    page_icon="\u26be",
    layout="wide",
)

from src.db import (
    get_year_range,
    get_batting_stats,
    get_pitching_stats,
    get_batting_zscores,
    get_pitching_zscores,
)
from src.stats import BATTING_STATS, PITCHING_STATS
from src.ranking import rank_batters, rank_pitchers
from src.ui import render_sidebar, render_stat_controls, render_results


def main():
    st.title("Baseball Player Ranker")
    st.caption(
        "Compare historical baseball players across any era. "
        "Stats are normalized using z-scores per season so players from different eras "
        "can be compared fairly. Adjust the stat weights to reflect what matters most to you."
    )

    # Get year range from database
    try:
        min_year, max_year = get_year_range()
    except Exception as e:
        st.error(
            f"Could not connect to database: {e}\n\n"
            "Please run `python scripts/build_db.py` first to build the database."
        )
        return

    # Render sidebar and get user selections
    config = render_sidebar(min_year, max_year)

    mode = config["mode"]
    start_year = config["start_year"]
    end_year = config["end_year"]
    position = config["position"]
    top_n = config["top_n"]
    min_pa = config["min_pa"]
    min_ip = config["min_ip"]

    # Display current filter summary
    st.markdown(f"**Showing top {top_n} {mode.lower()}** from **{start_year}** to **{end_year}**"
                + (f" at **{position}**" if mode == "Batters" and position != "All" else ""))

    # Stat selection and weights on main page
    selected_stats, weights = render_stat_controls(mode)

    st.divider()

    if mode == "Batters":
        stat_defs = BATTING_STATS

        with st.spinner("Querying batting data..."):
            raw_stats = get_batting_stats(start_year, end_year, position, min_pa)
            zscores = get_batting_zscores(start_year, end_year, position, min_pa)

        if zscores.empty:
            st.warning("No qualifying batters found. Try lowering the minimum PA or expanding the year range.")
            return

        results = rank_batters(zscores, raw_stats, selected_stats, weights, top_n)

    else:  # Pitchers
        stat_defs = PITCHING_STATS

        with st.spinner("Querying pitching data..."):
            raw_stats = get_pitching_stats(start_year, end_year, min_ip)
            zscores = get_pitching_zscores(start_year, end_year, min_ip)

        if zscores.empty:
            st.warning("No qualifying pitchers found. Try lowering the minimum IP or expanding the year range.")
            return

        results = rank_pitchers(zscores, raw_stats, selected_stats, weights, top_n)

    # Render results
    render_results(results, selected_stats, stat_defs, mode)

    # Footer with info about methodology
    with st.expander("How does the ranking work?"):
        st.markdown("""
        **Z-Score Normalization**: For each stat in each season, we compute a z-score:
        `z = (player_value - league_mean) / league_std_dev`. This tells us how many
        standard deviations above or below average a player was *for their era*.

        **PA/IP Weighting**: When aggregating across multiple seasons, z-scores are
        weighted by plate appearances (batters) or innings pitched (pitchers), so
        full seasons count more than partial ones.

        **Rating (100+ scale)**: Your selected stats are weighted according to the sliders
        above the results table. The weights are normalized to sum to 100%. The final
        rating uses a 100-based scale like OPS+ or ERA+: 100 = league average,
        150 = 50% better than average, 200 = twice as good as average.

        **Inverse Stats**: For stats where lower is better (ERA, WHIP, BB/9), the
        z-scores are inverted so that "better" always means a higher z-score.

        **Data Source**: [Lahman Baseball Database](https://sabr.org/lahman-database/)
        via the [Chadwick Bureau](https://github.com/chadwickbureau/baseballdatabank).
        """)


if __name__ == "__main__":
    main()
