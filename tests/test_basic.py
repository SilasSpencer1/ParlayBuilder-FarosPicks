from __future__ import annotations

import json
from pathlib import Path

from ev_parlay.parser import parse_model_file
from ev_parlay.ev_math import single_ev, kelly_fraction
from ev_parlay.config import AppConfig
from ev_parlay.odds_api import get_best_moneyline
from ev_parlay.ev_math import attach_single_metrics
from ev_parlay.builder import greedy_beam_build, ilp_select


MOCK_ODDS = {
	"events": []
}

# The Odds API returns a list at top-level; build a tiny example inline
MOCK_LIST = [
	{
		"bookmakers": [
			{
				"key": "draftkings",
				"markets": [
					{
						"key": "h2h",
						"outcomes": [
							{"name": "Jacksonville Jaguars", "price": -150},
							{"name": "Green Bay Packers", "price": 120},
						]
					}
				]
			}
		]
	}
]


def test_parse_model(tmp_path: Path):
	p = tmp_path / "model.txt"
	p.write_text(":Jaguars: JAX – 78.6% | Margin: 13.2\n", encoding="utf-8")
	sel = parse_model_file(str(p))
	assert len(sel) == 1
	assert sel[0].team_abbr == "JAX"
	assert abs(sel[0].model_win_prob - 0.786) < 1e-6


def test_ev_math():
	# If p=0.6 and dec=2.0 (evens), EV = 0.6*1 - 0.4 = 0.2
	assert abs(single_ev(0.6, 2.0) - 0.2) < 1e-9
	# Kelly fraction with p=0.6, b=1 -> (0.6-0.4)/1 = 0.2
	assert abs(kelly_fraction(0.6, 2.0) - 0.2) < 1e-9


def test_builder_with_mock_odds(tmp_path: Path):
	config = AppConfig()
	config.sportsbooks = ["draftkings"]
	selections = parse_model_file(str(tmp_path / "model.txt")) if (tmp_path / "model.txt").exists() else []
	if not selections:
		# create two teams inline
		from ev_parlay.models import TeamSelection
		selections = [
			TeamSelection(team_name="Jacksonville Jaguars", team_abbr="JAX", model_win_prob=0.7),
			TeamSelection(team_name="Green Bay Packers", team_abbr="GB", model_win_prob=0.55),
		]
	odds_payload = MOCK_LIST
	for s in selections:
		od = get_best_moneyline(s.team_name, config, odds_payload)
		assert od is not None
		s.best_odds = od
		s = attach_single_metrics(s)
	with_odds = selections
	by_size = greedy_beam_build(with_odds, config)
	tickets = ilp_select(by_size, config)
	# With only two legs and default sizes 3..10, likely zero tickets
	assert isinstance(tickets, list)
