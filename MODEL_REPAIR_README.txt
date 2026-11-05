GRIDIRON SIMULATOR - MODEL REPAIR

WHAT WAS FIXED
1. Each simulation request now draws a fresh random sample rather than reusing a fixed seed.
2. Player box scores are explicitly labeled as one sampled game, NOT the average predicted score.
3. Overlapping player/defensive/matchup adjustments are reduced to limit double counting.
4. A LOW CONFIDENCE warning appears if either team has fewer than 3 completed games.
5. Missing or disabled roster refresh is disclosed.

LIMITATIONS
This does NOT prove predictive accuracy. Live ESPN responses and historical out-of-sample validation are still required. The existing historical tracker is not a full-model backtest. The current player statistics are illustrative, not trustworthy player prop forecasts.

INSTALL
Back up your GitHub repository first. Replace model.py, mobile_server.py and simulated_player_stats.py with these versions. Commit changes and wait for Render deployment. Keep your existing index.html and all other files unchanged if you prefer.
