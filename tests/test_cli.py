from __future__ import annotations

from typer.testing import CliRunner

from ev_parlay.cli import app


def test_cli_help():
	runner = CliRunner()
	result = runner.invoke(app, ["--help"])
	assert result.exit_code == 0
	assert "Parlay Builder" in result.stdout
