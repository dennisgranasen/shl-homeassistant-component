"""Opt-in live tests for TheSportsDB Team Tracker API."""
import os
from pathlib import Path

import aiohttp
import pytest
import pytest_socket
import yaml


SECRETS_PATH = Path(__file__).parents[1] / "secrets.yaml"


def _load_api_key() -> str:
    """Load the TheSportsDB API key without exposing it in test output."""
    secrets = yaml.safe_load(SECRETS_PATH.read_text(encoding="utf-8")) or {}
    try:
        return str(secrets["shlapikey"])
    except KeyError as error:
        raise AssertionError(f"Missing {error.args[0]} in secrets.yaml") from error


@pytest.mark.live_api
@pytest.mark.asyncio
async def test_shl_api_credentials_and_teams():
    """Verify credentials and a real authenticated SHL API request."""
    if os.getenv("RUN_SHL_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_SHL_LIVE_TESTS=1 to run live SHL API tests")
    pytest_socket._remove_restrictions()
    pytest_socket.enable_socket()
    api_key = _load_api_key()
    url = f"https://www.thesportsdb.com/api/v1/json/{api_key}/searchteams.php"
    connector = aiohttp.TCPConnector(
        resolver=aiohttp.resolver.ThreadedResolver(), force_close=True
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, params={"t": "HV71"}) as response:
            response_body = await response.text()
            assert response.status == 200, response_body[:200]
            payload = await response.json()

    teams = payload.get("teams") or []
    assert any(
        team.get("strTeam") == "HV71"
        and team.get("strSport") == "Ice Hockey"
        and team.get("strLeague") == "Swedish Hockey League"
        for team in teams
    )