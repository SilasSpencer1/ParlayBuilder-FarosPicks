from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import json
import sys
import typer

from .config import AppConfig
from .logging_utils import get_logger
from .parser import parse_model_file
from .odds_api import fetch_odds, get_best_moneyline, build_game_index
from .ev_math import attach_single_metrics
from .builder import greedy_beam_build, ilp_select, ilp_select_with_derivation
from .reporting import print_console_report, write_artifacts
from .simulate import simulate_slate
from .models import ParlayTicket
from .team_mapping import normalize_team, abbr

app = typer.Typer(help="NFL Moneyline EV Calculator + Parlay Builder")
logger = get_logger(__name__)


@app.command("fetch-odds")
def fetch_odds_cmd(
	config_path: Optional[str] = typer.Option(None, "--config", help="Path to config.yaml"),
	region: Optional[str] = typer.Option(None, "--region", help="Region/state code"),
	sportsbooks: Optional[str] = typer.Option(None, "--sportsbooks", help="Comma-separated book keys"),
	cache_file: Optional[str] = typer.Option(None, "--cache", help="Override cache file path"),
	commence_from: Optional[str] = typer.Option(None, "--from", help="Commence time from (ISO)"),
	commence_to: Optional[str] = typer.Option(None, "--to", help="Commence time to (ISO)"),
):
	config = AppConfig.load(config_path)
	if region:
		config.region = region
	if sportsbooks:
		config.sportsbooks = [s.strip().lower() for s in sportsbooks.split(",") if s.strip()]
	if cache_file:
		config.cache_file = cache_file
	if commence_from:
		config.commence_from_iso = commence_from
	if commence_to:
		config.commence_to_iso = commence_to
	_ = fetch_odds(config)
	logger.info("Odds fetched and cached at %s", config.cache_file)


@app.command()
def build_parlays(
	model: str = typer.Option(..., "--model", help="Path to model.txt"),
	config_path: Optional[str] = typer.Option(None, "--config", help="Path to config.yaml"),
	region: Optional[str] = typer.Option(None, "--region", help="Region/state code"),
	sportsbooks: Optional[str] = typer.Option(None, "--sportsbooks", help="Comma-separated book keys"),
	max_tickets: Optional[int] = typer.Option(None, "--max-tickets", help="Max number of parlays"),
	num_parlays: Optional[int] = typer.Option(None, "--num-parlays", help="Exact number of parlays to build"),
	parlay_sizes: Optional[List[int]] = typer.Option(None, "--parlay-sizes", help="Parlay sizes"),
	team_exposure_cap: Optional[float] = typer.Option(None, "--team-exposure-cap", help="Max fraction per team"),
	bankroll: Optional[float] = typer.Option(None, "--bankroll", help="Bankroll for Kelly"),
	budget: Optional[float] = typer.Option(None, "--budget", help="Total budget for this run (overrides flat/kelly stakes)"),
	beam_width: Optional[int] = typer.Option(None, "--beam-width", help="Beam width for greedy expansion"),
	candidate_pool_size: Optional[int] = typer.Option(None, "--candidate-pool-size", help="Top N singles to consider"),
	min_edge: Optional[float] = typer.Option(None, "--min-edge", help="Minimum single-leg edge to include"),
	min_parlay_ev: Optional[float] = typer.Option(None, "--min-parlay-ev", help="Minimum parlay EV to keep"),
	odds_file: Optional[str] = typer.Option(None, "--odds-file", help="Read odds JSON from this file instead of API"),
	commence_from: Optional[str] = typer.Option(None, "--from", help="Commence time from (ISO)"),
	commence_to: Optional[str] = typer.Option(None, "--to", help="Commence time to (ISO)"),
	outdir: str = typer.Option("outputs", "--outdir", help="Output directory"),
):
	config = AppConfig.load(config_path)
	if region:
		config.region = region
	if sportsbooks:
		config.sportsbooks = [s.strip().lower() for s in sportsbooks.split(",") if s.strip()]
	if max_tickets is not None:
		config.max_tickets = max_tickets
	if num_parlays is not None:
		config.desired_num_tickets = num_parlays
	if parlay_sizes:
		config.parlay_sizes = list(parlay_sizes)
	if team_exposure_cap is not None:
		config.team_exposure_cap = team_exposure_cap
	if bankroll is not None:
		config.bankroll = bankroll
	if budget is not None:
		config.run_budget = budget
	if beam_width is not None:
		config.beam_width = beam_width
	if candidate_pool_size is not None:
		config.candidate_pool_size = candidate_pool_size
	if min_edge is not None:
		config.min_edge = min_edge
	if min_parlay_ev is not None:
		config.min_parlay_ev = min_parlay_ev
	if commence_from:
		config.commence_from_iso = commence_from
	if commence_to:
		config.commence_to_iso = commence_to

	# Load inputs
	selections = parse_model_file(model)
	if odds_file:
		odds_payload = json.loads(Path(odds_file).read_text(encoding="utf-8"))
	else:
		odds_payload = fetch_odds(config)

	# Build game index for this slate and validate model picks
	game_index = build_game_index(odds_payload)
	validated = []
	seen_games = set()
	missing_from_slate: List[str] = []
	for s in selections:
		norm = normalize_team(s.team_name) or s.team_name
		team_ab = abbr(norm) or s.team_abbr
		if team_ab not in game_index:
			missing_from_slate.append(team_ab)
			continue
		gid, opp_ab = game_index[team_ab]
		# Resolve same-game conflicts by keeping only higher model prob
		if gid in seen_games:
			for i, prev in enumerate(validated):
				if prev.game_id == gid:
					if s.model_win_prob > prev.model_win_prob:
						validated[i] = s
					logger.info("Resolved same-game conflict for %s vs %s", team_ab, prev.team_abbr)
					break
			continue
		s.game_id = gid
		s.opponent_abbr = opp_ab
		validated.append(s)
		seen_games.add(gid)

	# If any picks are missing from slate, prompt user to update model and exit gracefully
	if missing_from_slate:
		msg = (
			"Some teams in model.txt are not in the current slate: "
			+ ", ".join(sorted(set(missing_from_slate)))
			+ ". Please update model.txt to match the week’s games (one pick per game)."
		)
		logger.error(msg)
		print(msg)
		return

	# Attach best odds and metrics; collect any missing odds as a soft failure
	with_odds = []
	missing_odds: List[str] = []
	for s in validated:
		od = get_best_moneyline(s.team_name, config, odds_payload)
		if od is None:
			missing_odds.append(s.team_abbr)
			continue
		s.best_odds = od
		s = attach_single_metrics(s)
		# Filter by min_edge if set
		if config.min_edge is not None and (s.edge or -1.0) < config.min_edge:
			pass
		else:
			with_odds.append(s)

	if missing_odds:
		msg = (
			"Some teams have no available odds from the selected books: "
			+ ", ".join(sorted(set(missing_odds)))
			+ ". Consider adjusting --sportsbooks or the date window."
		)
		logger.warning(msg)
		print(msg)

	# Greedy beam (one-per-game enforced) then ILP selection (+ derivation)
	by_size = greedy_beam_build(with_odds, config)
	tickets = ilp_select_with_derivation(by_size, config)
	if config.min_parlay_ev is not None and config.min_parlay_ev > 0:
		tickets = [t for t in tickets if t.expected_value >= config.min_parlay_ev]

	# Budget allocation
	if config.run_budget is not None and tickets:
		budget = config.run_budget
		n = config.desired_num_tickets or min(config.max_tickets, len(tickets))
		selected = tickets[:n]
		# Weighting methods
		if config.stake_method == "equal":
			weights = [1.0] * len(selected)
		elif config.stake_method == "ev_sqrt":
			weights = [max(0.0, (t.expected_value + 1e-9)) ** 0.5 for t in selected]
		else:  # kelly_norm default
			weights = [max(0.0, t.kelly_stake) for t in selected]
		if sum(weights) <= 0:
			weights = [1.0] * len(selected)
		# Normalize and apply caps/mins
		ws = [w / sum(weights) for w in weights]
		max_cap = config.max_stake_pct * budget if config.max_stake_pct else budget
		remaining = budget
		stakes = [0.0] * len(selected)
		# First pass proportional
		for i, w in enumerate(ws):
			stakes[i] = round(min(max_cap, max(config.min_stake, budget * w)), 2)
			remaining -= stakes[i]
		# Distribute any leftover equally respecting cap
		idx = 0
		while remaining > 0.01 and any(s < max_cap for s in stakes):
			if stakes[idx] < max_cap:
				add = min(max_cap - stakes[idx], remaining, 0.01 * round(remaining / 0.01))
				if add <= 0:
					idx = (idx + 1) % len(stakes)
					continue
				stakes[idx] = round(stakes[idx] + add, 2)
				remaining = round(remaining - add, 2)
			idx = (idx + 1) % len(stakes)
		for t, stake in zip(selected, stakes):
			t.flat_stake = stake
			t.kelly_stake = stake
		if config.desired_num_tickets is not None:
			tickets = selected

	print_console_report(with_odds, tickets)
	_ = write_artifacts(outdir, tickets)


@app.command()
def simulate(
	parlays_csv: str = typer.Option("outputs/parlays.csv", "--parlays", help="Path to parlays.csv"),
	trials: int = typer.Option(50000, "--trials", help="Monte-Carlo trials"),
	out_image: Optional[str] = typer.Option(None, "--out-image", help="Save histogram PNG to this path"),
	save_samples: Optional[str] = typer.Option(None, "--save-samples", help="Optional CSV of profit samples"),
):
	import pandas as pd
	from .simulate import simulate_slate, simulate_slate_samples, save_histogram

	df = pd.read_csv(parlays_csv)
	tickets = []
	for _, row in df.iterrows():
		teams = str(row["legs"]).split(",")
		tickets.append(
			ParlayTicket(
				size=int(row["size"]),
				legs=[],
				combined_decimal=float(row["decimal_odds"]),
				combined_probability=float(row["probability"]),
				expected_value=float(row["EV_dollars"]),
				flat_stake=float(row["flat_stake"]),
				kelly_stake=float(row["kelly_stake"]),
				books={t: "" for t in teams},
			)
		)
	stats = simulate_slate(tickets, trials=trials)
	print(json.dumps(stats, indent=2))
	if out_image or save_samples:
		profits = simulate_slate_samples(tickets, trials=trials)
		if out_image:
			path = save_histogram(profits, out_image)
			if path:
				print(f"Saved histogram to {path}")
			else:
				print("matplotlib not available; cannot save histogram")
		if save_samples:
			import pandas as pd
			pd.DataFrame({"profit": profits}).to_csv(save_samples, index=False)
			print(f"Saved samples to {save_samples}")


def main():
	app()


if __name__ == "__main__":
	main()
