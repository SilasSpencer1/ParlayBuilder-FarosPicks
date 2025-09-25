from __future__ import annotations

import logging
import os

try:
	from rich.logging import RichHandler  # type: ignore
	_USE_RICH = True
except Exception:
	_USE_RICH = False


def get_logger(name: str = "ev_parlay", level: int = logging.INFO) -> logging.Logger:
	logger = logging.getLogger(name)
	if logger.handlers:
		return logger
	logger.setLevel(level)
	handler: logging.Handler
	if _USE_RICH and os.getenv("NO_RICH") != "1":
		handler = RichHandler(rich_tracebacks=True)
	else:
		handler = logging.StreamHandler()
	formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	return logger
