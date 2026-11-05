GRIDIRON SIMULATOR — HISTORICAL ENGINE (FIRST STAGE)

WHAT IS IMPLEMENTED
- historical_engine.py: import completed games from CSV, calculate Elo ratings
  using only games before kickoff, fit a probability scale on earlier seasons,
  and report accuracy, Brier score and log loss on a later held-out season.
- elo_live.py: optional integration with the existing web app.
- mobile_server.py: uses an Elo snapshot ONLY when current, correctly matched,
  and each team has >=3 historical games. Otherwise it keeps the existing
  experimental heuristic and explicitly warns about missing/stale data.
- No player stats are invented or presented as historically validated.

IMPORTANT LIMITATION
No actual historical dataset is bundled. No real backtest has been run.
This is evaluation infrastructure, NOT proof of improved prediction accuracy.
The app's drive simulation is still a heuristic. The optional Elo snapshot
only affects the strength difference; score calibration remains unverified.

CSV REQUIRED COLUMNS
league,season,date,away_id,home_id,away_score,home_score
NFL,2023,2023-09-07T20:20:00-04:00,example-away,example-home,20,21
(Example row is illustrative; do not use it as real training data.)
Use stable ESPN team IDs in both the CSV and the app, not team names.
Provide full season coverage. Don't mix future or incomplete games.

TRAIN/TEST COMMANDS (Windows, inside the extracted folder):
python historical_engine.py historical_games.csv --league NFL --train-through 2024 --test-season 2025 --output nfl_report.json
python historical_engine.py historical_games.csv --league "College Football" --train-through 2024 --test-season 2025 --output college_report.json

Once verified historical games are collected, you can create an OPTIONAL
current-season Elo snapshot with:
python historical_engine.py historical_games.csv --league NFL --train-through 2024 --test-season 2025 --snapshot-as-of 2026-11-04T23:59:00Z --output nfl_report.json

That produces elo_snapshot_nfl.json beside the report. Put the snapshot in
GitHub repo root with elo_live.py and updated mobile_server.py.
Snapshots are accepted for 14 days and only for current-year simulations.
Regenerate regularly with completed games; a stale snapshot is ignored.
For college use --league "College Football" and it produces
elo_snapshot_college.json.

Data acquisition is NOT automated here. The existing ESPN feeds may be
incomplete or change structure; historical CSV must be checked for coverage,
correct teams, scores, and dates. Do not train on game-day roster data
retrieved after the game. Avoid marketing this as betting-grade.

INSTALL
Upload historical_engine.py and elo_live.py; replace mobile_server.py.
The rest of the app, including index.html and your Windows V18 app, stays
unchanged. Without snapshot JSON, predictions remain the old heuristic.
