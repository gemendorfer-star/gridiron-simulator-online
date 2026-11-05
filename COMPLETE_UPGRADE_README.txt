GRIDIRON SIMULATOR — CONSOLIDATED DATA / MODEL UPGRADE

WHAT IS INCLUDED
- All code from the prior App Edition, Model Repair and Historical Engine packages.
- ESPN historical game collector (collect_history.py) for NFL and college football.
- Historical CSV validation and chronological, leakage-aware Elo evaluation.
- Data quality warnings when roster, injuries, history or Elo snapshots are missing.
- Explicit labeling of the old accuracy tracker as a simple baseline.
- Preserved home/simulation/results/games/accuracy pages.

WHAT IS NOT YET PROVEN
- No real historical seasons were downloaded or evaluated in this environment.
- ESPN scoreboard is unofficial; college collection targets FBS group 80 and
  may not cover all games. Verify team/game coverage and duplicates.
- This is NOT a calibrated possession or player-level prediction model.
- Live predictions stay experimental until verified CSVs and recent Elo snapshots
  are produced and installed. Do not market as verified accuracy.

HOW TO COLLECT AND EVALUATE DATA (on your computer, Python installed)
  python collect_history.py --league NFL --seasons 2022 2023 2024 2025 --output nfl_games.csv
  python collect_history.py --league "College Football" --seasons 2022 2023 2024 2025 --output college_games.csv
Review totals, error files and game coverage first. Do not train on partial seasons.
  python historical_engine.py nfl_games.csv --league NFL --train-through 2024 --test-season 2025 --output nfl_report.json
  python historical_engine.py college_games.csv --league "College Football" --train-through 2024 --test-season 2025 --output college_report.json
After verifying the results, collect current-season games and generate current snapshots.
See HISTORICAL_ENGINE_README.txt for the snapshot command and limitations.

INSTALLATION
Back up your GitHub repo first. Upload the .py files and index.html from this
folder to your GitHub repo root; retain your existing Render service configuration.
Only .py and index.html are needed to deploy the base app. Snapshot JSONs are
optional and must be generated from verified historical data.
No access to your GitHub or Render account is available from this ZIP; uploading
these files does NOT automatically deploy them.

RUN TESTS
  python -m unittest discover -p "test_*.py" -v
  python -m py_compile *.py
