"""Tests for SHL api."""
import asyncio

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from custom_components.shl.api import (
    ShlApiClient,
)


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
        json={"expires_in": 1800, "access_token": 0xDEADBEEF}
    )
    assert not api.is_connected()
    assert await api.async_connect() == {"expires_in": 1800, "access_token": 0xDEADBEEF}
    assert api.is_connected()

    aioclient_mock.get(
        "https://openapi.shl.se/articles.json",
        json=[{"article_id": "a1", "title": "SM-guld", "team_code": "HV71"}]
    )
    assert api.async_get_articles(["HV71"]) == [{"article_id": "a1",
                                                 "title": "SM-guld",
                                                 "team_code": "HV71"}]

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/games.json",
        json={"test": "me"}
    )
    assert api.async_get_games(2022, ["HV71"]) == {"test": "me"}

    aioclient_mock.get(
        "https://openapi.shl.se/seasons/2022/games/m1234.json",
        json={"try": "me2"}
    )
    assert api.async_get_game(2022, "m1234") == {"try": "me2"}

    assert api.async_get_goalie_stats(2022)
    assert api.async_get_goalie_stats(2022, team_ids=["HV71"])
    assert api.async_get_player_stats(2022)
    assert api.async_get_player_stats(2022, team_ids=["HV71"])
    assert api.async_get_team_player_stats("HV71")
    assert api.async_get_team_stats(2022)
    assert api.async_get_team_stats(2022, ["HV71"])
    assert api.async_get_teams()
    assert api.async_get_videos()
    assert api.async_get_videos(["HV71"])

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
