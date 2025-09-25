from __future__ import annotations

from typing import List, Optional, Dict
from pydantic import BaseModel


class MoneylineOdds(BaseModel):
	book: str
	american: int
	decimal: float
	implied_prob: float


class TeamSelection(BaseModel):
	team_name: str
	team_abbr: str
	game_id: Optional[str] = None
	opponent_name: Optional[str] = None
	opponent_abbr: Optional[str] = None
	model_win_prob: float
	margin: Optional[float] = None
	best_odds: Optional[MoneylineOdds] = None
	implied_prob_market: Optional[float] = None
	edge: Optional[float] = None
	expected_value: Optional[float] = None


class ParlayTicket(BaseModel):
	size: int
	legs: List[TeamSelection]
	combined_decimal: float
	combined_probability: float
	expected_value: float
	flat_stake: float
	kelly_stake: float
	books: Dict[str, str]

	@property
	def teams(self) -> List[str]:
		return [l.team_abbr for l in self.legs]
