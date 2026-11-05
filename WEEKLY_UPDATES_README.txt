GRIDIRON SIMULATOR — WEEKLY AUTO UPDATE

WHAT IT DOES
- On opening the website and changing leagues, requests ESPN current scoreboard information.
- Displays ESPN season/week metadata when available, recent completed scores, upcoming games, and available team records.
- Rechecks at most once an hour while the service runs; users can press the update button.
- Running a simulation with the data checkbox enabled fetches recent team games, player history, available injury reports and depth charts using the existing code.
- Existing historical accuracy tester remains available but is NOT an automatically accumulated weekly prediction record.

LIMITATIONS
- Free Render services sleep. No background job runs while sleeping. The next visitor triggers a fresh scoreboard request.
- ESPN public endpoints can be unavailable or incomplete; no live data access was verified during packaging.
- This is not a persistent weekly prediction-accuracy log. Accurate forward-looking weekly evaluation requires storing predictions before kickoff in a persistent database and checking results later.
- This does not change the original Windows V18 app.

INSTALL
Upload/replace ALL files from this folder in the same GitHub repository, including the new weekly_updates.py. Commit changes and wait for Render to deploy.
