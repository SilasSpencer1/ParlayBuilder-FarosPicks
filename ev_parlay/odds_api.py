from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from .config import AppConfig
from .logging_utils import get_logger
from .models import MoneylineOdds
from .team_mapping import normalize_team, abbr

logger = get_logger(__name__)

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"

BOOK_ALIASES = {
	"dk": "draftkings",
	"draftkings": "draftkings",
	"fanduel": "fanduel",
	"fd": "fanduel",
	"betmgm": "betmgm",
	"mgm": "betmgm",
	"caesars": "caesars",
	"williamhill_us": "caesars",
	"pointsbet": "pointsbetus",
	"pointsbetus": "pointsbetus",
	"barstool": "espnbet",
	"espnbet": "espnbet",
	"bet365": "bet365",
}


def normalize_book_key(key: str) -> str:
	return BOOK_ALIASES.get(key.strip().lower(), key.strip().lower())


def american_to_decimal(american: int) -> float:
	if american > 0:
		return 1.0 + american / 100.0
	else:
		return 1.0 + 100.0 / abs(american)


def implied_prob_from_american(american: int) -> float:
	if american > 0:
		return 100.0 / (american + 100.0)
	else:
		a = abs(american)
		return a / (a + 100.0)


def _cache_valid(path: Path, ttl_seconds: int) -> bool:
	if not path.exists():
		return False
	age = time.time() - path.stat().st_mtime
	return age <= ttl_seconds


def fetch_odds(config: AppConfig, cache_override: Optional[str] = None) -> Dict:
	cache_file = Path(cache_override or config.cache_file)
	if _cache_valid(cache_file, config.ttl_seconds):
		logger.info("Using cached odds from %s", cache_file)
		return json.loads(cache_file.read_text(encoding="utf-8"))

	params = {
		"apiKey": config.odds_api_key,
		"regions": config.region,
		"markets": config.market,
		"oddsFormat": "american",
	}
	if config.date:
		params["dateFormat"] = "iso"
		params["date"] = config.date
	if config.commence_from_iso:
		params["commenceTimeFrom"] = config.commence_from_iso
	if config.commence_to_iso:
		params["commenceTimeTo"] = config.commence_to_iso
	if not config.odds_api_key:
		raise RuntimeError("ODDS_API_KEY is not set. Set env var or config.")

	logger.info("Fetching odds from The Odds API ...")
	resp = requests.get(ODDS_API_BASE, params=params, timeout=20)
	resp.raise_for_status()
	data = resp.json()
	cache_file.write_text(json.dumps(data), encoding="utf-8")
	logger.info("Saved odds cache to %s", cache_file)
	return data


def build_game_index(odds_payload: Dict | List) -> Dict[str, Tuple[str, str]]:
	"""
	Return mapping: team_abbr -> (game_id, opponent_abbr)
	Prefer event home_team/away_team fields; fallback to outcomes aggregation.
	"""
	index: Dict[str, Tuple[str, str]] = {}
	for ev in odds_payload:
		game_id = ev.get("id") or ev.get("event_id") or ""
		home = ev.get("home_team") or ev.get("homeTeam")
		away = ev.get("away_team") or ev.get("awayTeam")
		pair_abbrs: List[str] = []
		if home and away:
			for t in (home, away):
				norm = normalize_team(t) or t
				ab = abbr(norm)
				if ab:
					pair_abbrs.append(ab)
		else:
			# Fallback: collect from outcomes
			teams: List[str] = []
			for bk in ev.get("bookmakers", []):
				for market in bk.get("markets", []):
					if market.get("key") != "h2h":
						continue
					for oc in market.get("outcomes", []):
						name = oc.get("name")
						if name:
							teams.append(name)
			abbrs = []
			for t in set(teams):
				norm = normalize_team(t) or t
				ab = abbr(norm)
				if ab:
					abbrs.append(ab)
			pair_abbrs = abbrs
		if len(pair_abbrs) == 2:
			a, b = pair_abbrs
			index[a] = (game_id, b)
			index[b] = (game_id, a)
	return index


def get_best_moneyline(team_full_name: str, config: AppConfig, odds_payload: Dict | List) -> Optional[MoneylineOdds]:
	team_norm = normalize_team(team_full_name) or team_full_name
	best: Optional[Tuple[str, int]] = None
	allowed_books = {normalize_book_key(b) for b in (config.sportsbooks or [])}
	# The Odds API top-level is a list of events
	for event in odds_payload:
		bookmakers = event.get("bookmakers", [])
		for bk in bookmakers:
			key = normalize_book_key(bk.get("key", ""))
			if allowed_books and key not in allowed_books:
				continue
			for market in bk.get("markets", []):
				if market.get("key") != config.market:
					continue
				for outcome in market.get("outcomes", []):
					name = outcome.get("name")
					if not name:
						continue
					if normalize_team(name) == team_norm or name == team_norm:
						try:
							price = int(outcome.get("price"))
						except Exception:
							continue
						if best is None:
							best = (key, price)
						else:
							_, cur_price = best
							if (price >= 0 and price > cur_price) or (price < 0 and price > cur_price):
								best = (key, price)
	if not best:
		return None
	book, price = best
	return MoneylineOdds(
		book=book,
		american=price,
		decimal=american_to_decimal(price),
		implied_prob=implied_prob_from_american(price),
	)
