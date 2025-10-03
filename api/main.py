from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import json

from ev_parlay.config import AppConfig
from ev_parlay.parser import parse_model_file, parse_model_text
from ev_parlay.odds_api import fetch_odds, get_best_moneyline, build_game_index
from ev_parlay.ev_math import attach_single_metrics
from ev_parlay.builder import greedy_beam_build, ilp_select_with_derivation
from ev_parlay.models import ParlayTicket
from ev_parlay.simulate import simulate_slate, simulate_slate_samples, save_histogram
from ev_parlay.team_mapping import normalize_team, abbr

app = FastAPI(title="EV Parlay API")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Mount static UI at /ui and redirect / -> /ui/
static_dir = Path(__file__).parent.parent / "web"
if static_dir.exists():
	app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="static")

@app.get("/")
async def root():
	return RedirectResponse(url="/ui/")


@app.get("/api/example_model")
def api_example_model():
	p = Path(__file__).parent.parent / "examples" / "model.txt"
	try:
		text = p.read_text(encoding="utf-8")
	except Exception:
		text = ""
	return {"text": text}


class BuildRequest(BaseModel):
	model_path: Optional[str] = None
	model_text: Optional[str] = None
	region: str = "us"
	sportsbooks: List[str] = ["draftkings", "fanduel"]
	odds_file: Optional[str] = None
	from_iso: Optional[str] = None
	to_iso: Optional[str] = None
	week: Optional[int] = None
	parlay_sizes: List[int] = [2, 3, 4, 5]
	team_exposure_cap: float = 0.4
	beam_width: int = 200
	candidate_pool_size: int = 200
	min_edge: float = 0.0
	min_parlay_ev: float = 0.0
	desired_num_tickets: int = 8
	budget: float = 100.0
	stake_method: str = "kelly_norm"
	max_stake_pct: float = 0.4
	min_stake: float = 0.0
	correlation_rho: float = 0.0


class BuildResponse(BaseModel):
	parlays: List[dict]
	singles: List[dict]


@app.post("/api/build", response_model=BuildResponse)
def api_build(req: BuildRequest):
	config = AppConfig()
	config.region = req.region
	config.sportsbooks = [s.lower() for s in req.sportsbooks]
	config.parlay_sizes = req.parlay_sizes
	config.team_exposure_cap = req.team_exposure_cap
	config.beam_width = req.beam_width
	config.candidate_pool_size = req.candidate_pool_size
	config.min_edge = req.min_edge
	config.min_parlay_ev = req.min_parlay_ev
	config.desired_num_tickets = req.desired_num_tickets
	config.run_budget = req.budget
	config.stake_method = req.stake_method
	config.max_stake_pct = req.max_stake_pct
	config.min_stake = req.min_stake
	config.correlation_rho = req.correlation_rho
	if req.from_iso:
		config.commence_from_iso = req.from_iso
	if req.to_iso:
		config.commence_to_iso = req.to_iso
	# If week provided, prefer week-specific cache filename and ignore incoming odds_file
	cache_file = None
	if req.week:
		cache_file = Path(f".odds_cache_week{req.week}_all.json")

	# Parse from text if provided, else from file
	if req.model_text and req.model_text.strip():
		selections = parse_model_text(req.model_text)
	elif req.model_path:
		selections = parse_model_file(req.model_path)
	else:
		raise HTTPException(status_code=400, detail={"error": "Provide model_text or model_path"})
	# Load odds from week cache if exists; else fetch and write cache
	odds_payload = None
	if cache_file and cache_file.exists():
		odds_payload = json.loads(cache_file.read_text(encoding="utf-8"))
	else:
		try:
			odds_payload = fetch_odds(config)
			if cache_file:
				cache_file.write_text(json.dumps(odds_payload), encoding="utf-8")
		except Exception as e:
			raise HTTPException(status_code=400, detail={
				"code": "no_odds_for_week",
				"message": "No cached odds for this week and live fetch failed (missing ODDS_API_KEY?).",
				"week": req.week,
				"cache_file": str(cache_file) if cache_file else None,
				"error": str(e),
			})

	game_index = build_game_index(odds_payload)
	validated = []
	seen_games = set()
	seen_teams = set()
	missing = []
	for s in selections:
		norm = normalize_team(s.team_name) or s.team_name
		team_ab = abbr(norm) or s.team_abbr
		if team_ab not in game_index:
			missing.append({"team": s.team_name, "abbr": team_ab, "reason": "not in current slate"})
			continue
		gid, opp_ab = game_index[team_ab]
		if gid in seen_games:
			for i, prev in enumerate(validated):
				if prev.game_id == gid:
					# Keep the higher-probability side
					chosen = s if s.model_win_prob > prev.model_win_prob else prev
					chosen.game_id = gid
					chosen.opponent_abbr = opp_ab
					validated[i] = chosen
					break
			continue
		s.game_id = gid
		s.opponent_abbr = opp_ab
		validated.append(s)
		seen_games.add(gid)
	if missing:
		raise HTTPException(status_code=400, detail={"missing": missing, "hint": "Update model text to only include teams playing this week; one pick per game."})

	with_odds = []
	for s in validated:
		od = get_best_moneyline(s.team_name, config, odds_payload)
		if not od:
			continue
		s.best_odds = od
		s = attach_single_metrics(s)
		if s.edge is not None and s.edge < config.min_edge:
			continue
		with_odds.append(s)

	by_size = greedy_beam_build(with_odds, config)
	tickets = ilp_select_with_derivation(by_size, config)

	# Allocate budget
	if config.run_budget is not None and tickets:
		budget = config.run_budget
		n = config.desired_num_tickets or len(tickets)
		selected = tickets[:n]
		weights = [max(0.0, t.kelly_stake) for t in selected] or [1.0] * len(selected)
		total = sum(weights)
		ws = [w / total for w in weights]
		for t, w in zip(selected, ws):
			stake = round(budget * w, 2)
			t.flat_stake = stake
			t.kelly_stake = stake
			tickets = selected

	return BuildResponse(
		parlays=[t.model_dump() for t in tickets],
		singles=[{
			"team": s.team_abbr,
			"model_p": s.model_win_prob,
			"implied_p": s.implied_prob_market,
			"edge": s.edge,
			"dec": s.best_odds.decimal if s.best_odds else None,
			"ev": s.expected_value,
		} for s in with_odds],
	)


class SimRequest(BaseModel):
	parlays: List[ParlayTicket]
	trials: int = 50000
	out_image: Optional[str] = None


@app.post("/api/simulate")
def api_simulate(req: SimRequest):
	print(f"[DEBUG] Simulating {len(req.parlays)} parlays with {req.trials} trials")
	stats = simulate_slate(req.parlays, trials=req.trials)
	image_url = None
	if req.out_image:
		print(f"[DEBUG] Generating plot: {req.out_image}")
		profits = simulate_slate_samples(req.parlays, trials=req.trials)
		p = Path(req.out_image)
		# Save under static UI dir if not absolute
		if not p.is_absolute():
			p = static_dir / p.name
		p.parent.mkdir(parents=True, exist_ok=True)
		print(f"[DEBUG] Saving histogram to: {p}")
		save_histogram(profits, str(p))
		image_url = f"/ui/{p.name}"
		print(f"[DEBUG] Image URL: {image_url}")
	return {"stats": stats, "image": image_url}
