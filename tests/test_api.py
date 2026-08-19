"""Tests for TheSportsDB API."""
import asyncio
from datetime import date
from datetime import timedelta

import aiohttp
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.shl.api import (
    SportsDbApiClient,
    normalize_team_stats,
)
from custom_components.shl.sensor import flatten_event
from custom_components.shl.sensor import ShlSensor
from custom_components.shl.sensor import select_current_event



def test_normalize_team_stats_for_team_tracker_card():
    """Team stats should be normalized into a card-friendly payload."""
    payload = {
        "team": "HV71",
        "team_name": "HV71",
        "position": 1,
        "games_played": 30,
        "wins": 18,
        "ot_wins": 2,
        "losses": 6,
        "ot_losses": 1,
        "goals_for": 95,
        "goals_against": 62,
        "points": 41,
        "last_5": "WWLLW",
        "status": "Playing",
    }

    assert normalize_team_stats(payload) == {
        "team": "HV71",
        "team_name": "HV71",
        "position": 1,
        "games_played": 30,
        "wins": 18,
        "ot_wins": 2,
        "losses": 6,
        "ot_losses": 1,
        "goals_for": 95,
        "goals_against": 62,
        "goal_difference": 33,
        "points": 41,
        "last_5": "WWLLW",
        "status": "Playing",
    }


def test_sensor_exposes_team_tracker_card_attributes():
    """Expose the generic event and logo attributes consumed by the card."""
    class Coordinator:
        data = {
            "body": {
                "team": "HV71",
                "team_name": "HV71",
                "idTeam": "135142",
                "strTeam": "HV71",
                "strTeamShort": "HV71",
                "strSport": "Ice Hockey",
                "strLeague": "Swedish Hockey League",
                "strBadge": "https://example.test/hv71.png",
                "next_events": [
                    {
                        "idEvent": "2476494",
                        "strEvent": "HV71 vs Malmö Redhawks",
                        "idHomeTeam": "135142",
                        "idAwayTeam": "135487",
                        "strHomeTeam": "HV71",
                        "strAwayTeam": "Malmö Redhawks",
                        "strHomeTeamBadge": "https://example.test/hv71.png",
                        "strAwayTeamBadge": "https://example.test/malmo.png",
                        "strLeagueBadge": "https://example.test/shl.png",
                        "dateEvent": "2026-09-19",
                        "strTime": "13:15:00",
                        "strVenue": "Husqvarna Garden",
                        "strStatus": "NS",
                    }
                ],
            }
        }

    class ConfigEntry:
        entry_id = "test-entry"

    sensor = ShlSensor(Coordinator(), ConfigEntry(), "HV71")

    assert sensor.state == "PRE"
    assert sensor.extra_state_attributes["sport"] == "hockey"
    assert sensor.extra_state_attributes["team_abbr"] == "HV71"
    assert sensor.extra_state_attributes["team_logo"] == "https://example.test/hv71.png"
    assert sensor.extra_state_attributes["opponent_logo"] == "https://example.test/malmo.png"
    assert sensor.extra_state_attributes["opponent_abbr"] == "Mal"
    assert sensor.extra_state_attributes["league_logo"] == "https://example.test/shl.png"
    assert sensor.extra_state_attributes["team_homeaway"] == "home"
    assert sensor.extra_state_attributes["opponent_homeaway"] == "away"


async def test_sportsdb_client_returns_team_tracker_data():
    """The TheSportsDB client should normalize team and schedule data."""
    class Response:
        def __init__(self, payload):
            self.payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        async def json(self):
            return self.payload

    class Session:
        def get(self, url, params=None, **_kwargs):
            if url.endswith("searchteams.php"):
                return Response(
                    {
                        "teams": [
                            {
                                "idTeam": "135142",
                                "strTeam": "HV71",
                                "strSport": "Ice Hockey",
                                "strLeague": "Swedish Hockey League",
                            }
                        ]
                    }
                )
            if url.endswith("eventsnext.php"):
                return Response({"events": [{"strStatus": "Not Started"}]})
            return Response({"results": [{"strStatus": "Match Finished"}]})

    client = SportsDbApiClient("123", ["HV71"], Session())

    result = await client.async_get_data()

    assert result["team"]["team"] == "HV71"
    assert result["team"]["idTeam"] == "135142"
    assert result["team"]["status"] == "Not Started"
    assert result["team"]["previous_events"] == [
        {"strStatus": "Match Finished"}
    ]


async def test_sportsdb_client_prefers_djurgarden_hockey_team():
    """Prefer the SHL team when TheSportsDB returns a football namesake."""
    class Response:
        def __init__(self, payload):
            self.payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        async def json(self):
            return self.payload

    class Session:
        def get(self, _url, params=None, **_kwargs):
            if params["t"] == "Djurgården":
                return Response(
                    {
                        "teams": [
                            {"strTeam": "Djurgården", "strSport": "Soccer"}
                        ]
                    }
                )
            return Response(
                {
                    "teams": [
                        {
                            "idTeam": "135139",
                            "strTeam": "Djurgårdens IF",
                            "strSport": "Ice Hockey",
                            "strLeague": "Swedish Hockey League",
                        }
                    ]
                }
            )

    client = SportsDbApiClient("123", [], Session())

    team = await client.async_get_team("Djurgården")

    assert team["idTeam"] == "135139"
    assert team["strLeague"] == "Swedish Hockey League"


async def test_sportsdb_client_supports_hockeyallsvenskan():
    """Accept teams from Swedish Hockey Allsvenskan."""
    class Response:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        async def json(self):
            return {
                "teams": [
                    {
                        "idTeam": "137304",
                        "strTeam": "Leksands IF",
                        "strSport": "Ice Hockey",
                        "strLeague": "Swedish Hockey Allsvenskan",
                    }
                ]
            }

    class Session:
        def get(self, _url, params=None):
            return Response()

    team = await SportsDbApiClient("123", [], Session()).async_get_team("Leksand")

    assert team["idTeam"] == "137304"
    assert team["strLeague"] == "Swedish Hockey Allsvenskan"


def test_flatten_event_exposes_team_tracker_fields():
    """Flattened events should expose opponent, time, and score fields."""
    event = {
        "idEvent": "1",
        "strEvent": "HV71 vs Djurgårdens IF",
        "idHomeTeam": "135142",
        "strHomeTeam": "HV71",
        "idAwayTeam": "135139",
        "strAwayTeam": "Djurgårdens IF",
        "intHomeScore": "4",
        "intAwayScore": "2",
        "dateEvent": "2026-09-20",
        "strTime": "18:00:00",
        "strVenue": "Husqvarna Garden",
    }

    flattened = flatten_event({"idTeam": "135142"}, event, "next_game")

    assert flattened["next_game_opponent"] == "Djurgårdens IF"
    assert flattened["next_game_team_score"] == "4"
    assert flattened["next_game_opponent_score"] == "2"
    assert flattened["next_game_date"] == "2026-09-20"


def test_select_current_event_keeps_today_final_visible():
    """Today's final takes precedence over a future upcoming event."""
    event, state = select_current_event(
        {
            "previous_events": [{"idEvent": "final", "dateEvent": date.today().isoformat()}],
            "next_events": [{"idEvent": "next", "dateEvent": (date.today() + timedelta(days=1)).isoformat()}],
        }
    )

    assert event["idEvent"] == "final"
    assert state == "POST"


def test_select_current_event_prioritizes_live_game():
    """A live event takes precedence over both scheduled lists."""
    event, state = select_current_event(
        {
            "live_events": [{"idEvent": "live"}],
            "next_events": [{"idEvent": "next"}],
        }
    )

    assert event["idEvent"] == "live"
    assert state == "IN"
