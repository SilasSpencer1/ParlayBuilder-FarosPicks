from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import json
import pandas as pd

from .models import ParlayTicket, TeamSelection


@dataclass
class SlateSummary:
	count: int
	avg_size: float
	total_ev: float
	diversification_score: float
	exposure: Dict[str, float]


def print_console_report(selections: List[TeamSelection], tickets: List[ParlayTicket]) -> None:
	from rich.console import Console  # type: ignore
	from rich.table import Table  # type: ignore

	console = Console()
	console.rule("Singles (+EV)")
	t = Table("Team", "Edge %", "Market Imp %", "Model %", "Price (dec)", "EV $")
	for s in selections:
		if (s.expected_value or 0.0) <= 0 or not s.best_odds:
			continue
		implied = (s.implied_prob_market or 0.0) * 100
		modelp = s.model_win_prob * 100
		edge_pct = (s.edge or 0.0) * 100
		t.add_row(s.team_abbr, f"{edge_pct:.1f}", f"{implied:.1f}", f"{modelp:.1f}", f"{s.best_odds.decimal:.2f}", f"{s.expected_value:.2f}")
	console.print(t)

	console.rule("Parlays")
	t2 = Table("Size", "Teams", "Dec", "Prob %", "EV $", "Flat", "Kelly")
	for p in tickets:
		prob_pct = p.combined_probability * 100
		t2.add_row(str(p.size), ",".join(p.teams), f"{p.combined_decimal:.2f}", f"{prob_pct:.1f}", f"{p.expected_value:.2f}", f"{p.flat_stake:.2f}", f"{p.kelly_stake:.2f}")
	console.print(t2)


def write_artifacts(outdir: str | Path, tickets: List[ParlayTicket]) -> SlateSummary:
	Path(outdir).mkdir(parents=True, exist_ok=True)
	# CSV of parlays
	rows = []
	exposure_counts: Dict[str, int] = {}
	for t in tickets:
		for team in t.teams:
			exposure_counts[team] = exposure_counts.get(team, 0) + 1
		rows.append(
			{
				"size": t.size,
				"legs": ",".join(t.teams),
				"decimal_odds": round(t.combined_decimal, 4),
				"probability": round(t.combined_probability, 6),
				"EV_dollars": round(t.expected_value, 2),
				"flat_stake": round(t.flat_stake, 2),
				"kelly_stake": round(t.kelly_stake, 2),
			}
		)
	parlays_path = Path(outdir) / "parlays.csv"
	pd.DataFrame(rows).to_csv(parlays_path, index=False)

	# Exposure
	total_tickets = max(1, len(tickets))
	exposure = {team: cnt / total_tickets for team, cnt in exposure_counts.items()}
	exposure_rows = [{"team": k, "exposure": v} for k, v in sorted(exposure.items())]
	exposure_path = Path(outdir) / "exposure.csv"
	pd.DataFrame(exposure_rows).to_csv(exposure_path, index=False)

	# Summary JSON
	div_score = sum(v * v for v in exposure.values())
	summary = SlateSummary(
		count=len(tickets),
		avg_size=(sum(t.size for t in tickets) / len(tickets)) if tickets else 0.0,
		total_ev=sum(t.expected_value for t in tickets),
		diversification_score=div_score,
		exposure=exposure,
	)
	summary_path = Path(outdir) / "summary.json"
	summary_path.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")
	return summary
