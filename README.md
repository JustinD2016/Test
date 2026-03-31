# Baseball Player Ranker

Compare historical baseball players across any era using the Lahman database. Rank players by configurable weighted stats with era-adjusted z-scores.

## Features

- **Batter and Pitcher rankings** with separate stat sets
- **Era-adjusted z-scores** so players from different eras are compared fairly
- **Configurable stat weights** - choose which stats matter and how much
- **Position filtering** for batters (C, 1B, 2B, 3B, SS, LF, CF, RF, OF, DH)
- **Year range selection** from 1871 to 2025
- **Minimum qualification thresholds** (plate appearances / innings pitched)

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Build the database (uses the CSV files already in the repo):
   ```bash
   python scripts/build_db.py
   ```

3. Run the app:
   ```bash
   streamlit run app.py
   ```

## How It Works

For each stat in each season, a z-score is computed: `z = (player_value - league_mean) / league_std_dev`. This normalizes stats across eras so a .300 BA in the dead-ball era is valued differently than in the steroid era.

When aggregating across seasons, z-scores are weighted by plate appearances (batters) or innings pitched (pitchers). The final composite score is a weighted average of selected z-scores based on user-configured weights.

## Data Source

[Lahman Baseball Database](https://sabr.org/lahman-database/) - complete batting, pitching, and fielding statistics from 1871 to 2025.

## Deployment

Deploy for free on [Streamlit Community Cloud](https://streamlit.io/cloud):
1. Push this repo to GitHub
2. Connect the repo in Streamlit Cloud
3. Set entry point to `app.py`
4. The build script runs automatically if configured as a setup command

## Tech Stack

- **Python** with **Streamlit** for the web UI
- **SQLite** for the database (built from Lahman CSVs)
- **pandas** for data manipulation and z-score computation
