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
