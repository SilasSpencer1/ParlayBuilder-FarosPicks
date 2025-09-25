from __future__ import annotations

from typing import List

from .models import TeamSelection


def single_ev(p_model: float, decimal_odds: float) -> float:
	# EV for $1 stake
	return p_model * (decimal_odds - 1.0) - (1.0 - p_model)


def parlay_probability(probs: List[float], rho: float = 0.0) -> float:
	p_independent = 1.0
	for p in probs:
		p_independent *= p
	if not probs:
		return 0.0
	if rho == 0.0:
		return p_independent
	min_p = min(probs)
	return p_independent * (1.0 - rho) + rho * min_p


def parlay_decimal(odds: List[float]) -> float:
	d = 1.0
	for o in odds:
		d *= o
	return d


def kelly_fraction(p: float, dec: float) -> float:
	b = dec - 1.0
	# k = (p*b - (1-p)) / b
	k = (p * b - (1.0 - p)) / b if b > 0 else 0.0
	return max(0.0, k)


def attach_single_metrics(sel: TeamSelection) -> TeamSelection:
	if sel.best_odds is None:
		return sel
	sel.implied_prob_market = sel.best_odds.implied_prob
	sel.edge = sel.model_win_prob - sel.implied_prob_market
	sel.expected_value = single_ev(sel.model_win_prob, sel.best_odds.decimal)
	return sel
