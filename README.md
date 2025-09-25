# EV Parlay: NFL Moneyline EV Calculator + Parlay Builder

A Python 3.11+ toolkit that:
- Parses your model’s per-team win probabilities
- Fetches and caches live moneyline odds (The Odds API)
- Computes single-leg and parlay EV
- Builds diversified tickets via greedy beam search + ILP, with size-derivation when needed
- Allocates stakes (flat, Kelly-normalized, or balanced) under a total budget
- Exports CSV/JSON and prints a readable console report
- Optional Monte Carlo simulation on your slate

## Install
```bash
# Python 3.11+ is required
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Set your API key (The Odds API):
```bash
export ODDS_API_KEY=YOUR_KEY_HERE
```

## Model input format
- File: `model.txt` (one pick per line)
- You provide the model’s preferred team and win probability (margins are optional)
- Example (see `examples/model.txt`):
```
:Jaguars: JAX – 78.6% | Margin: 13.2
:Packers: GB – 74.6% | Margin: 11.1
```
Guidelines:
- One pick per game for the target week. If both sides of the same game are listed, the CLI keeps only the higher model probability for that game.
- Team aliases/abbreviations are normalized (e.g., LAR, GB, NE, BUF, JAX). If a team is not found in the week’s slate, the CLI prints a clear message and exits.

## Terminology: books and aliases
Pass sportsbook keys as a comma-separated list. Recognized aliases include:
- DK/draftkings → `draftkings`
- FanDuel/fanduel/FD → `fanduel`
- BetMGM/MGM → `betmgm`
- Caesars/WilliamHill_US → `caesars`
- Bet365 → `bet365`
- PointsBet/PointsBetUS → `pointsbetus`

## CLI overview
Show help:
```bash
python -m ev_parlay.cli --help
```

Commands:
- `fetch-odds`: Fetch and cache odds from The Odds API
- `build-parlays`: Build diversified parlays from your model + odds
- `simulate`: Monte Carlo simulate profit distribution for a generated slate

---

## Step 1: Fetch odds for a specific week
The Odds API returns upcoming games. Use `--from`/`--to` (ISO timestamps) to filter a specific week window and optionally write to a separate cache file.

Examples:
```bash
# Week 4 window (example)
python -m ev_parlay.cli fetch-odds \
  --region us \
  --sportsbooks DK,FanDuel \
  --from 2025-09-24T00:00:00Z \
  --to   2025-10-01T23:59:59Z \
  --cache .odds_cache_week4.json

# Include more books for better prices
python -m ev_parlay.cli fetch-odds \
  --region us \
  --sportsbooks DK,FanDuel,BetMGM,Caesars,Bet365,PointsBetUS \
  --from 2025-09-24T00:00:00Z \
  --to   2025-10-01T23:59:59Z \
  --cache .odds_cache_week4_all.json
```

Notes:
- If you omit `--from/--to`, the API returns the next upcoming set of games.
- Use `--cache FILE` to avoid overwriting the default cache.

---

## Step 2: Build parlays
Point at your model file and either pass `--odds-file` (cached JSON) or let the CLI fetch odds live.

Core example (Week 4 cache, 8 tickets, $75 budget):
```bash
python -m ev_parlay.cli build-parlays \
  --model examples/model.txt \
  --odds-file .odds_cache_week4_all.json \
  --sportsbooks DK,FanDuel,BetMGM,Caesars,Bet365,PointsBetUS \
  --num-parlays 8 \
  --budget 75 \
  --outdir outputs_week4
```

Important flags:
- `--num-parlays N`: exact number of tickets to produce (ILP enforces this; if distinct +EV combos are limited, the tool derives smaller tickets by dropping legs)
- `--budget X`: total dollars to spread across the selected tickets
- `--team-exposure-cap C`: maximum fraction of tickets any team can appear in (e.g., `0.35`)
- `--parlay-sizes ...`: allowed parlay sizes (defaults to 3..10)
- `--beam-width N`: beam search width (defaults to 50). Increase to explore more combos
- `--candidate-pool-size N`: top N single-leg candidates by edge (defaults to 50)
- `--min-edge E`: minimum single-leg edge to include (allow small negatives to broaden the pool, e.g., `-0.02`)
- `--min-parlay-ev E`: minimum EV for a parlay to keep (can be slightly negative to ensure enough tickets)
- `--from/--to`: use these on `build-parlays` if you want the CLI to fetch the week’s odds live instead of `--odds-file`

Behavior details:
- Validation: the CLI maps every team in `model.txt` to a `game_id` and opponent from the odds payload. If a team isn’t in the slate, it prints the exact teams to fix and exits.
- Same-game conflicts: if both sides appear in `model.txt`, the CLI keeps the side with the higher model probability.
- One pick per game: enforced for each individual ticket (no parlay contains both sides of the same game).
- Derivation: if we can’t hit `--num-parlays` with distinct +EV tickets, we derive smaller tickets (e.g., 7-leg base → 6/5/4/3-leg) to diversify exposure while keeping EV reasonable.

Budget allocation (stakes):
- Controlled in `config.yaml` (see below). Default method is Kelly-normalized weighting with a per-ticket cap and optional minimum.
- Final stake printed in the console table (`Flat`, `Kelly`) and saved to CSV.

Outputs:
- `parlays.csv`: columns `size,legs,decimal_odds,probability,EV_dollars,flat_stake,kelly_stake`
- `exposure.csv`: per-team exposure across the selected tickets
- `summary.json`: slate summary and a diversification score
- Console table: singles (+EV) and final tickets

Example to broaden and diversify aggressively:
```bash
python -m ev_parlay.cli build-parlays \
  --model examples/model.txt \
  --odds-file .odds_cache_week4_all.json \
  --sportsbooks DK,FanDuel,BetMGM,Caesars,Bet365,PointsBetUS \
  --num-parlays 8 \
  --budget 75 \
  --beam-width 500 \
  --candidate-pool-size 500 \
  --min-edge -0.02 \
  --min-parlay-ev -0.10 \
  --team-exposure-cap 0.60 \
  --outdir outputs_week4_diverse
```

---

## Step 3: Simulate
Run a Monte Carlo over the generated parlays to view distributional outcomes:
```bash
python -m ev_parlay.cli simulate --parlays outputs_week4/parlays.csv --trials 50000
```

---

## Config file (config.yaml)
You can set defaults here and omit flags. Example:
```yaml
# Odds / filtering
sportsbooks: ["draftkings", "fanduel", "betmgm", "caesars", "bet365", "pointsbetus"]
region: us
min_edge: -0.02
min_parlay_ev: -0.10
beam_width: 500
candidate_pool_size: 500
team_exposure_cap: 0.6
parlay_sizes: [3,4,5,6,7]
# Derivation / duplication
allow_duplicate_across_tickets: true
size_diversify: true
derivation_sizes: [6,5,4,3]
derivation_limit_per_size: 20
# Budget / stakes
bankroll: 1000
kelly_fraction: 0.5
run_budget: 75
stake_method: kelly_norm   # or: equal, ev_sqrt
max_stake_pct: 0.4         # cap per ticket as % of budget
min_stake: 0.0             # enforce a minimum stake per ticket
# Caching
ttl_seconds: 300
```

Place the file anywhere and point to it:
```bash
python -m ev_parlay.cli build-parlays --config config.yaml --model model.txt --odds-file .odds_cache_week4.json
```

---

## Troubleshooting
- “Some teams in model.txt are not in the current slate…”: Your model picks don’t match the fetched week’s schedule. Fix `model.txt` for the same week, or fetch a different week via `--from/--to`, or pass a week-specific `--odds-file`.
- “Zero events” in cache: The window didn’t include upcoming games; widen `--from/--to` or check your region.
- Only a few tickets produced: Increase `--beam-width` and `--candidate-pool-size`, lower `--min-edge`, allow more books, and/or relax `--team-exposure-cap`.
- One ticket takes most of the budget: Adjust stake settings in `config.yaml` (e.g., `stake_method: equal`, `max_stake_pct: 0.25`).
- Wrong week: Always pin a week via `fetch-odds --from/--to --cache FILE` and then use `--odds-file FILE` during build.

---

## Notes & limitations
- Independence assumption for parlay probability; optional shrinkage parameter `correlation_rho` (default 0).
- Market odds can drift; re-fetch odds near bet time.
- Derivation introduces tickets that share many legs (by design) to diversify against single-point failure while still prioritizing high-EV structures. Use exposure caps and stake caps to control concentration.

---

## Quick start (copy/paste)
```bash
# 1) Activate venv and set API key (once per shell)
python3.11 -m venv .venv && source .venv/bin/activate
export ODDS_API_KEY=YOUR_KEY

# 2) Install
pip install -e .[dev]

# 3) Fetch Week 4 odds into a named cache
python -m ev_parlay.cli fetch-odds \
  --region us \
  --sportsbooks DK,FanDuel,BetMGM,Caesars,Bet365,PointsBetUS \
  --from 2025-09-24T00:00:00Z --to 2025-10-01T23:59:59Z \
  --cache .odds_cache_week4_all.json

# 4) Build 8 diversified tickets on a $75 budget
python -m ev_parlay.cli build-parlays \
  --model examples/model.txt \
  --odds-file .odds_cache_week4_all.json \
  --num-parlays 8 --budget 75 \
  --beam-width 500 --candidate-pool-size 500 \
  --min-edge -0.02 --min-parlay-ev -0.10 \
  --team-exposure-cap 0.60 \
  --outdir outputs_week4

# 5) Simulate the slate
python -m ev_parlay.cli simulate --parlays outputs_week4/parlays.csv --trials 50000
```
