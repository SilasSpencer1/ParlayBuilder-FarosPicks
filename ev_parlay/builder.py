from __future__ import annotations

from typing import Dict, List, Tuple

import math
from collections import Counter

import pulp  # type: ignore

from .config import AppConfig
from .ev_math import parlay_probability, parlay_decimal, kelly_fraction
from .models import ParlayTicket, TeamSelection


def _parlay_ev(legs: List[TeamSelection], rho: float) -> Tuple[float, float, float]:
	probs = [l.model_win_prob for l in legs]
	odds = [l.best_odds.decimal for l in legs if l.best_odds]
	if len(odds) != len(legs):
		return (0.0, 0.0, -math.inf)
	P = parlay_probability(probs, rho)
	Dec = parlay_decimal(odds)
	EV = P * (Dec - 1.0) - (1.0 - P)
	return P, Dec, EV


def greedy_beam_build(legs: List[TeamSelection], config: AppConfig) -> Dict[int, List[List[TeamSelection]]]:
	# Start with +EV singles sorted by edge
	candidates = [l for l in legs if (l.expected_value or 0.0) > 0.0]
	candidates.sort(key=lambda x: (x.edge or -1.0), reverse=True)
	if config.candidate_pool_size > 0:
		candidates = candidates[: config.candidate_pool_size]

	by_size: Dict[int, List[Tuple[List[TeamSelection], float]]] = {}

	for size in config.parlay_sizes:
		beam: List[Tuple[List[TeamSelection], float]] = []
		# initialize with single best legs
		for leg in candidates:
			seed = [leg]
			beam.append((seed, leg.edge or 0.0))
		# grow
		for _ in range(1, size):
			new_beam: List[Tuple[List[TeamSelection], float]] = []
			for combo, _score in beam:
				used_teams = {l.team_abbr for l in combo}
				used_games = {l.game_id for l in combo if l.game_id}
				for leg in candidates:
					if leg.team_abbr in used_teams:
						continue
					if leg.game_id and leg.game_id in used_games:
						continue  # one pick per game
					combo2 = combo + [leg]
					P, D, EV = _parlay_ev(combo2, config.correlation_rho)
					if EV <= 0:
						continue
					new_beam.append((combo2, EV))
			# keep top beam_width
			new_beam.sort(key=lambda x: x[1], reverse=True)
			beam = new_beam[: config.beam_width]
		# store final combos with correct size
		by_size[size] = [combo for combo, _ in beam]
	return by_size


def ilp_select(finalist_by_size: Dict[int, List[List[TeamSelection]]], config: AppConfig) -> List[ParlayTicket]:
	# Flatten candidate tickets
	candidates: List[Tuple[int, List[TeamSelection]]] = []
	for size, combos in finalist_by_size.items():
		for c in combos:
			candidates.append((size, c))
	# Compute EVs
	cand_evs: List[Tuple[int, List[TeamSelection], float, float, float]] = []
	for size, legs in candidates:
		P, D, EV = _parlay_ev(legs, config.correlation_rho)
		if math.isfinite(EV) and EV > 0:
			cand_evs.append((size, legs, P, D, EV))
	# If too many, keep top pool
	cand_evs.sort(key=lambda x: x[4], reverse=True)
	cand_evs = cand_evs[: max(config.max_tickets * 5, 50)]

	idx = list(range(len(cand_evs)))
	ev = {i: cand_evs[i][4] for i in idx}
	teams_of = {i: [l.team_abbr for l in cand_evs[i][1]] for i in idx}

	model = pulp.LpProblem("ParlaySelection", pulp.LpMaximize)
	x = pulp.LpVariable.dicts("x", idx, lowBound=0, upBound=1, cat=pulp.LpBinary)

	# Objective: maximize total EV
	model += pulp.lpSum(x[i] * ev[i] for i in idx)

	# Ticket count constraint
	desired = config.desired_num_tickets
	if desired is not None:
		model += pulp.lpSum(x[i] for i in idx) == desired
	else:
		model += pulp.lpSum(x[i] for i in idx) <= config.max_tickets

	# Exposure caps
	cap_count = math.floor(config.team_exposure_cap * (desired or config.max_tickets))
	if cap_count >= 0:
		all_teams = sorted({t for arr in teams_of.values() for t in arr})
		for t in all_teams:
			model += pulp.lpSum(x[i] for i in idx if t in teams_of[i]) <= cap_count

	# Solve
	model.solve(pulp.PULP_CBC_CMD(msg=False))
	chosen = [i for i in idx if x[i].value() == 1.0]

	tickets: List[ParlayTicket] = []
	for i in chosen:
		size, legs, P, D, EV = cand_evs[i]
		books = {l.team_abbr: (l.best_odds.book if l.best_odds else "") for l in legs}
		k = kelly_fraction(P, D)
		kelly_stake = config.bankroll * config.kelly_fraction * k
		tickets.append(
			ParlayTicket(
				size=size,
				legs=legs,
				combined_decimal=D,
				combined_probability=P,
				expected_value=EV,
				flat_stake=config.flat_stake,
				kelly_stake=round(kelly_stake, 2),
				books=books,
			)
		)

	# Remove duplicates by team set signature
	seen = set()
	unique: List[ParlayTicket] = []
	for t in tickets:
		sig = (t.size, tuple(sorted(t.teams)))
		if sig in seen:
			continue
		seen.add(sig)
		unique.append(t)

	# Sort by EV desc
	unique.sort(key=lambda t: t.expected_value, reverse=True)
	return unique


def _derive_from_base_tickets(base: List[ParlayTicket], config: AppConfig) -> List[ParlayTicket]:
	derived_by_size: Dict[int, List[ParlayTicket]] = {}
	for t in base:
		for new_size in config.derivation_sizes:
			if new_size >= t.size:
				continue
			bucket = derived_by_size.setdefault(new_size, [])
			if len(bucket) >= config.derivation_limit_per_size:
				continue
			# Generate single-drop variants; rotate drop index to vary teams
			for i in range(len(t.legs)):
				legs2 = t.legs[:i] + t.legs[i + 1 :]
				if len(legs2) != new_size:
					continue
				P, D, EV = _parlay_ev(legs2, config.correlation_rho)
				if EV < config.min_parlay_ev:
					continue
				k = kelly_fraction(P, D)
				bucket.append(
					ParlayTicket(
						size=new_size,
						legs=legs2,
						combined_decimal=D,
						combined_probability=P,
						expected_value=EV,
						flat_stake=0.0,
						kelly_stake=0.0 if k <= 0 else k,
						books={l.team_abbr: (l.best_odds.book if l.best_odds else "") for l in legs2},
					)
				)
				if len(bucket) >= config.derivation_limit_per_size:
					break
	# Flatten with size diversification preference
	if config.size_diversify:
		# Round-robin merge by size to mix sizes
		sizes = sorted(derived_by_size.keys(), reverse=True)
		merged: List[ParlayTicket] = []
		cursor = {s: 0 for s in sizes}
		remaining = True
		while remaining:
			remaining = False
			for s in sizes:
				arr = derived_by_size.get(s, [])
				i = cursor[s]
				if i < len(arr):
					merged.append(arr[i])
					cursor[s] += 1
					remaining = True
		return merged
	# Else just sort each size by EV and flatten
	flat: List[ParlayTicket] = []
	for s, arr in derived_by_size.items():
		arr.sort(key=lambda t: t.expected_value, reverse=True)
		flat.extend(arr)
	return flat


def ilp_select_with_derivation(finalist_by_size: Dict[int, List[List[TeamSelection]]], config: AppConfig) -> List[ParlayTicket]:
	primary = ilp_select(finalist_by_size, config)
	if config.desired_num_tickets is None:
		return primary
	need = config.desired_num_tickets - len(primary)
	if need <= 0:
		return primary
	# Derive additional tickets from best primary tickets
	extra = _derive_from_base_tickets(primary, config)
	# Merge and de-duplicate by team set and size unless duplicates allowed
	combined = primary + extra
	if not config.allow_duplicate_across_tickets:
		seen = set()
		uniq = []
		for t in combined:
			sig = (t.size, tuple(sorted(t.teams)))
			if sig in seen:
				continue
			seen.add(sig)
			uniq.append(t)
		combined = uniq
	# Sort by EV desc and take top desired count
	combined.sort(key=lambda t: t.expected_value, reverse=True)
	return combined[: config.desired_num_tickets]
