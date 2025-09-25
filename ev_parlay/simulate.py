from __future__ import annotations

from typing import List, Dict

import numpy as np

from .models import ParlayTicket


def simulate_slate(tickets: List[ParlayTicket], trials: int = 50000, random_seed: int = 42) -> Dict[str, float]:
	rng = np.random.default_rng(random_seed)
	profits = np.zeros(trials)
	for t in tickets:
		p = t.combined_probability
		dec = t.combined_decimal
		stake = t.kelly_stake if t.kelly_stake > 0 else t.flat_stake
		wins = rng.random(trials) < p
		profits += wins * (stake * (dec - 1.0)) - (~wins) * stake
	return {
		"mean": float(np.mean(profits)),
		"median": float(np.median(profits)),
		"p05": float(np.percentile(profits, 5)),
		"p95": float(np.percentile(profits, 95)),
	}
