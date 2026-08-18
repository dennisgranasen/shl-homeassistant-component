"""Tests for SHL api."""
import asyncio

import aiohttp
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.shl.api import (
    SportsDbApiClient,
    ShlApiClient,
    normalize_team_stats,
)
from custom_components.shl.sensor import flatten_event


@pytest.mark.skip(reason="Legacy SHL OAuth API is no longer used")
async def test_api(hass, aioclient_mock, caplog):
    """Test API calls."""

    # To test the api submodule, we first create an instance of our API client
    api = ShlApiClient("test", "test", ["HV71"], async_get_clientsession(hass))

    # Use aioclient_mock which is provided by `pytest_homeassistant_custom_components`
    # to mock responses to aiohttp requests. In this case we are telling the mock to
    # return {"test": "test"} when a `GET` call is made to the specified URL. We then
    # call `async_get_data` which will make that `GET` request.
    aioclient_mock.post(
        "https://openapi.shl.se/oauth2/token",
        json={"expires_in": 1800, "access_token": 0xDEADBEEF},
    )
    assert not api.is_connected()
    assert await api.async_connect() == {"expires_in": 1800, "access_token": 0xDEADBEEF}
    assert api.is_connected()

    aioclient_mock.get(
        "https://openapi.shl.se/articles.json",
        json=[{"article_id": "a1", "title": "SM-guld", "team_code": "HV71"}],
    )
    assert await api.async_get_articles(["HV71"]) == [
        {"article_id": "a1", "title": "SM-guld", "team_code": "HV71"}
    ]

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/games.json", json={"test": "me"}
    )
    assert await api.async_get_games(2022, ["HV71"]) == {"test": "me"}

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/games/m1234.json", json={"try": "me2"}
    )
    assert await api.async_get_game(2022, "m1234") == {"try": "me2"}

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/statistics/players.json",
        json={"player": {"no": 21, "name": "Peter Forsberg"}},
    )
    assert await api.async_get_player_stats(2022) == {
        "player": {"no": 21, "name": "Peter Forsberg"}
    }
    assert await api.async_get_player_stats(2022, team_ids=["Modo"]) == {
        "player": {"no": 21, "name": "Peter Forsberg"}
    }

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/statistics/goalkeepers.json",
        json={"Legend": "Stefan Liv"},
    )
    assert await api.async_get_goalie_stats(2022) == {"Legend": "Stefan Liv"}
    assert await api.async_get_goalie_stats(2022, team_ids=["HV71"]) == {
        "Legend": "Stefan Liv"
    }

    aioclient_mock.get("https://openapi.shl.se/teams/HV71.json", json={"hv": 71})
    assert await api.async_get_team_player_stats("HV71") == {"hv": 71}

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/statistics/teams/standings.json",
        json={"hv71": 1},
    )
    assert await api.async_get_team_stats(2022) == {"hv71": 1}
    assert await api.async_get_team_stats(2022, ["HV71"]) == {"hv71": 1}
    aioclient_mock.get(
        "https://openapi.shl.se/teams.json", json=[{"team_code": "HV71"}]
    )
    assert await api.async_get_teams() == [{"team_code": "HV71"}]

    aioclient_mock.get(
        "https://openapi.shl.se/videos.json", json={"video": "killed the radio star"}
    )
    assert await api.async_get_videos() == {"video": "killed the radio star"}
    assert await api.async_get_videos(["HV71"]) == {"video": "killed the radio star"}

    # We do the same for `async_set_title`. Note the difference in the mock call
    # between the previous step and this one. We use `patch` here instead of `get`
    # because we know that `async_set_title` calls `api_wrapper` with `patch` as the
    # first parameter

    # aioclient_mock.patch("https://jsonplaceholder.typicode.com/posts/1")
    # assert await api.async_set_title("test") is None

    # In order to get 100% coverage, we need to test `api_wrapper` to test the code
    # that isn't already called by `async_get_data` and `async_set_title`. Because the
    # only logic that lives inside `api_wrapper` that is not being handled by a third
    # party library (aiohttp) is the exception handling, we also want to simulate
    # raising the exceptions to ensure that the function handles them as expected.
    # The caplog fixture allows access to log messages in tests. This is particularly
    # useful during exception handling testing since often the only action as part of
    # exception handling is a logging statement

    # TODO: Define more tests
    # assert await api.async_get_articles()

    caplog.clear()
    aioclient_mock.put(
        "https://jsonplaceholder.typicode.com/posts/1", exc=asyncio.TimeoutError
    )
    assert (
        await api.api_wrapper("put", "https://jsonplaceholder.typicode.com/posts/1")
        is None
    )
    assert (
        len(caplog.record_tuples) == 1
        and "Timeout error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post(
        "https://jsonplaceholder.typicode.com/posts/1", exc=aiohttp.ClientError
    )
    assert (
        await api.api_wrapper("post", "https://jsonplaceholder.typicode.com/posts/1")
        is None
    )
    assert (
        len(caplog.record_tuples) == 1
        and "Error fetching information from" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post("https://jsonplaceholder.typicode.com/posts/2", exc=Exception)
    assert (
        await api.api_wrapper("post", "https://jsonplaceholder.typicode.com/posts/2")
        is None
    )
    assert (
        len(caplog.record_tuples) == 1
        and "Something really wrong happened!" in caplog.record_tuples[0][2]
    )

    caplog.clear()
    aioclient_mock.post("https://jsonplaceholder.typicode.com/posts/3", exc=TypeError)
    assert (
        await api.api_wrapper("post", "https://jsonplaceholder.typicode.com/posts/3")
        is None
    )
    assert (
        len(caplog.record_tuples) == 1
        and "Error parsing information from" in caplog.record_tuples[0][2]
    )


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
                return Response({"eventsnext": [{"strStatus": "Not Started"}]})
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
