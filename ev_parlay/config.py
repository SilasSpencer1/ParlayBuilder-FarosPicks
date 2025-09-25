from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import os
import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
	# Odds API and filtering
	odds_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ODDS_API_KEY"))
	sportsbooks: List[str] = Field(default_factory=lambda: ["draftkings", "fanduel", "betmgm"])
	region: str = "us"
	market: str = "h2h"
	min_edge: float = 0.0
	min_parlay_ev: float = 0.0
	date: Optional[str] = None
	commence_from_iso: Optional[str] = None
	commence_to_iso: Optional[str] = None
	candidate_pool_size: int = 50
	# Caching
	ttl_seconds: int = 300
	cache_file: str = ".odds_cache.json"
	# Parlays
	parlay_sizes: List[int] = Field(default_factory=lambda: list(range(3, 11)))
	beam_width: int = 50
	max_tickets: int = 8
	desired_num_tickets: Optional[int] = None
	team_exposure_cap: float = 0.35
	avoid_same_game: bool = True
	correlation_rho: float = 0.0
	# Duplication/derivation controls
	allow_duplicate_across_tickets: bool = True
	derivation_sizes: List[int] = Field(default_factory=lambda: [6, 5, 4, 3])
	derivation_limit_per_size: int = 20
	size_diversify: bool = True
	# Bankroll / stakes
	bankroll: float = 1000.0
	kelly_fraction: float = 0.5
	run_budget: Optional[float] = None
	flat_stake: float = 10.0
	stake_method: str = "kelly_norm"  # options: kelly_norm, equal, ev_sqrt
	max_stake_pct: float = 0.4
	min_stake: float = 0.0

	@staticmethod
	def load(config_path: Optional[str] = None) -> "AppConfig":
		data = {}
		if config_path and Path(config_path).exists():
			with open(config_path, "r", encoding="utf-8") as f:
				data = yaml.safe_load(f) or {}
		return AppConfig(**data)
