from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .team_mapping import normalize_team, abbr
from .models import TeamSelection

LINE_RE = re.compile(r"^:?(?P<team_name>[^:]+):\s+(?P<abbr>[A-Z]{2,3})\s+[–-]\s+(?P<prob>[0-9]+\.?[0-9]*)%\s*(\|\s*Margin:\s*(?P<margin>-?[0-9]+\.?[0-9]*))?", re.IGNORECASE)


def parse_model_file(path: str | Path) -> List[TeamSelection]:
	selections: List[TeamSelection] = []
	for raw in Path(path).read_text(encoding="utf-8").splitlines():
		line = raw.strip()
		if not line:
			continue
		m = LINE_RE.match(line)
		if not m:
			continue
		name = m.group("team_name").strip()
		abbr_str = m.group("abbr").strip().upper()
		prob = float(m.group("prob")) / 100.0
		margin_str = m.group("margin")
		margin = float(margin_str) if margin_str else None
		team_full = normalize_team(abbr_str) or normalize_team(name) or name
		team_abbr = abbr(team_full) or abbr_str
		selections.append(
			TeamSelection(
				team_name=team_full,
				team_abbr=team_abbr,
				model_win_prob=prob,
				margin=margin,
			)
		)
	return selections


def parse_model_text(text: str) -> List[TeamSelection]:
	"""Parse selections from raw text, one selection per line.

	Accepts lines like:
	  ":Vikings: MIN – 60.1% | Margin: 4.2"
	  "Vikings: MIN - 60.1%"
	  "MIN 60.1%"
	  "Minnesota Vikings 60.1% margin 4.2"

	Abbreviation is optional; when present it improves mapping.
	"""
	selections: List[TeamSelection] = []
	for raw in text.splitlines():
		line = raw.strip()
		if not line:
			continue
		m = LINE_RE.match(line)
		if m:
			name = m.group("team_name").strip()
			abbr_str = m.group("abbr").strip().upper()
			prob = float(m.group("prob")) / 100.0
			margin_str = m.group("margin")
			margin = float(margin_str) if margin_str else None
			team_full = normalize_team(abbr_str) or normalize_team(name) or name
			team_abbr = abbr(team_full) or abbr_str
			selections.append(TeamSelection(team_name=team_full, team_abbr=team_abbr, model_win_prob=prob, margin=margin))
			continue
		# Loose fallback: extract tokens and a trailing percent
		percent_match = re.search(r"([0-9]+\.?[0-9]*)%", line)
		if not percent_match:
			continue
		prob = float(percent_match.group(1)) / 100.0
		line_wo_pct = line.replace(percent_match.group(0), "").strip()
		# Try 2-3 letter token as abbr
		abbr_match = re.search(r"\b([A-Z]{2,3})\b", line_wo_pct)
		abbr_str = abbr_match.group(1).upper() if abbr_match else ""
		name_tokens = line_wo_pct
		team_full = normalize_team(abbr_str) or normalize_team(name_tokens) or name_tokens
		team_abbr = abbr(team_full) or (abbr_str if abbr_str else abbr(team_full) or team_full[:3].upper())
		selections.append(TeamSelection(team_name=team_full, team_abbr=team_abbr, model_win_prob=prob, margin=None))
	return selections
