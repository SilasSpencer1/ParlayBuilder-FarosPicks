from __future__ import annotations

from typing import Dict, Optional

# Map common abbreviations and names to canonical full team names
TEAM_ALIASES: Dict[str, str] = {
	# NFC West
	"ARI": "Arizona Cardinals",
	"ARZ": "Arizona Cardinals",
	"Cardinals": "Arizona Cardinals",
	"Arizona": "Arizona Cardinals",
	"SEA": "Seattle Seahawks",
	"Seahawks": "Seattle Seahawks",
	"Seattle": "Seattle Seahawks",
	"LAR": "Los Angeles Rams",
	"Rams": "Los Angeles Rams",
	"LA Rams": "Los Angeles Rams",
	"SF": "San Francisco 49ers",
	"SFO": "San Francisco 49ers",
	"49ers": "San Francisco 49ers",
	"Niners": "San Francisco 49ers",
	# NFC South
	"ATL": "Atlanta Falcons",
	"Falcons": "Atlanta Falcons",
	"Atlanta": "Atlanta Falcons",
	"CAR": "Carolina Panthers",
	"Panthers": "Carolina Panthers",
	"Carolina": "Carolina Panthers",
	"NO": "New Orleans Saints",
	"NOS": "New Orleans Saints",
	"Saints": "New Orleans Saints",
	"TB": "Tampa Bay Buccaneers",
	"TBB": "Tampa Bay Buccaneers",
	"Buccaneers": "Tampa Bay Buccaneers",
	"Bucs": "Tampa Bay Buccaneers",
	# NFC North
	"CHI": "Chicago Bears",
	"Bears": "Chicago Bears",
	"Chicago": "Chicago Bears",
	"DET": "Detroit Lions",
	"Lions": "Detroit Lions",
	"Detroit": "Detroit Lions",
	"GB": "Green Bay Packers",
	"Packers": "Green Bay Packers",
	"Green Bay": "Green Bay Packers",
	"MIN": "Minnesota Vikings",
	"Vikings": "Minnesota Vikings",
	"Minnesota": "Minnesota Vikings",
	# NFC East
	"DAL": "Dallas Cowboys",
	"Cowboys": "Dallas Cowboys",
	"Dallas": "Dallas Cowboys",
	"NYG": "New York Giants",
	"Giants": "New York Giants",
	"NY Giants": "New York Giants",
	"PHI": "Philadelphia Eagles",
	"Eagles": "Philadelphia Eagles",
	"Philadelphia": "Philadelphia Eagles",
	"WAS": "Washington Commanders",
	"Commanders": "Washington Commanders",
	"Washington": "Washington Commanders",
	# AFC West
	"DEN": "Denver Broncos",
	"Broncos": "Denver Broncos",
	"Denver": "Denver Broncos",
	"KC": "Kansas City Chiefs",
	"Chiefs": "Kansas City Chiefs",
	"Kansas City": "Kansas City Chiefs",
	"LAC": "Los Angeles Chargers",
	"Chargers": "Los Angeles Chargers",
	"LA Chargers": "Los Angeles Chargers",
	"LV": "Las Vegas Raiders",
	"LVR": "Las Vegas Raiders",
	"Raiders": "Las Vegas Raiders",
	# AFC South
	"HOU": "Houston Texans",
	"Texans": "Houston Texans",
	"Houston": "Houston Texans",
	"IND": "Indianapolis Colts",
	"Colts": "Indianapolis Colts",
	"Indianapolis": "Indianapolis Colts",
	"JAX": "Jacksonville Jaguars",
	"JAC": "Jacksonville Jaguars",
	"Jaguars": "Jacksonville Jaguars",
	"Jacksonville": "Jacksonville Jaguars",
	"TEN": "Tennessee Titans",
	"Titans": "Tennessee Titans",
	"Tennessee": "Tennessee Titans",
	# AFC North
	"BAL": "Baltimore Ravens",
	"Ravens": "Baltimore Ravens",
	"Baltimore": "Baltimore Ravens",
	"CIN": "Cincinnati Bengals",
	"Bengals": "Cincinnati Bengals",
	"Cincinnati": "Cincinnati Bengals",
	"CLE": "Cleveland Browns",
	"Browns": "Cleveland Browns",
	"Cleveland": "Cleveland Browns",
	"PIT": "Pittsburgh Steelers",
	"Steelers": "Pittsburgh Steelers",
	"Pittsburgh": "Pittsburgh Steelers",
	# AFC East
	"BUF": "Buffalo Bills",
	"Bills": "Buffalo Bills",
	"Buffalo": "Buffalo Bills",
	"MIA": "Miami Dolphins",
	"Dolphins": "Miami Dolphins",
	"Miami": "Miami Dolphins",
	"NE": "New England Patriots",
	"Patriots": "New England Patriots",
	"New England": "New England Patriots",
	"NYJ": "New York Jets",
	"Jets": "New York Jets",
	"NY Jets": "New York Jets",
}

# Canonical full name to primary abbreviation
TEAM_TO_ABBR: Dict[str, str] = {
	"Arizona Cardinals": "ARI",
	"Seattle Seahawks": "SEA",
	"Los Angeles Rams": "LAR",
	"San Francisco 49ers": "SF",
	"Atlanta Falcons": "ATL",
	"Carolina Panthers": "CAR",
	"New Orleans Saints": "NO",
	"Tampa Bay Buccaneers": "TB",
	"Chicago Bears": "CHI",
	"Detroit Lions": "DET",
	"Green Bay Packers": "GB",
	"Minnesota Vikings": "MIN",
	"Dallas Cowboys": "DAL",
	"New York Giants": "NYG",
	"Philadelphia Eagles": "PHI",
	"Washington Commanders": "WAS",
	"Denver Broncos": "DEN",
	"Kansas City Chiefs": "KC",
	"Los Angeles Chargers": "LAC",
	"Las Vegas Raiders": "LV",
	"Houston Texans": "HOU",
	"Indianapolis Colts": "IND",
	"Jacksonville Jaguars": "JAX",
	"Tennessee Titans": "TEN",
	"Baltimore Ravens": "BAL",
	"Cincinnati Bengals": "CIN",
	"Cleveland Browns": "CLE",
	"Pittsburgh Steelers": "PIT",
	"Buffalo Bills": "BUF",
	"Miami Dolphins": "MIA",
	"New England Patriots": "NE",
	"New York Jets": "NYJ",
}


def normalize_team(name_or_abbr: str) -> Optional[str]:
	key = name_or_abbr.strip()
	# If a canonical name is passed, return as-is
	if key in TEAM_TO_ABBR:
		return key
	# Otherwise map alias/abbr to canonical
	return TEAM_ALIASES.get(key)


def abbr(team_full_name: str) -> Optional[str]:
	return TEAM_TO_ABBR.get(team_full_name)
