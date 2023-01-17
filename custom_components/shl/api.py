"""Sample API Client."""
import asyncio
import logging
import socket

from datetime import datetime
import aiohttp
import async_timeout

from .const import NAME
from .const import VERSION

TIMEOUT = 10


_LOGGER: logging.Logger = logging.getLogger(__package__)

HEADERS = {"Content-type": "application/json; charset=UTF-8", "User-Agent": f"{NAME}/{VERSION}"}
BASE_URL = "https://openapi.shl.se"
AUTH = "/oauth2/token"


class ShlApiClient:
    """Access the OpenAPI for the Swedish national hockey league (SHL)"""

    def __init__(
        self, client_id: str, client_secret: str, team_ids: list[str],
        session: aiohttp.ClientSession
    ) -> None:
        """Sample API Client."""
        self._client_id = client_id
        self._client_secret = client_secret
        self._team_ids = team_ids
        self._session = session
        self._expires = datetime.min
        self._headers = None

    async def async_connect(self) -> None:
        """Authorize the client using supplied credentials."""
        form = {'client_id': self._client_id,
                'client_secret': self._client_secret,
                'grant_type': 'client_credentials'}
        headers = {'User-Agent': f"{NAME}/{VERSION}"}
        body = await self.api_wrapper("post", f"{BASE_URL}{AUTH}", data=form, headers=headers)
        self._expires = datetime.now() + int(body['expires_in'])
        self._headers = HEADERS.copy()
        self._headers['Authorization'] = "Bearer " + body['access_token']
        return body

    def is_connected(self) -> bool:
        """Check if authorization is valid."""
        return self._headers and self._expires > datetime.now()

    @staticmethod
    def generate_url(query: str, season: int = 0) -> str:
        """Generate the url for a specific query"""
        return f"{BASE_URL}/seasons/{season}/{query}" if season else f"{BASE_URL}/{query}"

    async def async_get_articles(self, team_ids: list[str]) -> dict:
        """Fetch the latest articles on the subscribed teams"""
        url = ShlApiClient.generate_url("articles")
        if team_ids:
            params = {'teamIds': ",".join(team_ids)}
            return await self.api_wrapper("get", url, params=params)
        return await self.api_wrapper("get", url)

    async def async_get_games(self, season: int, team_ids: list[str]) -> dict:
        """Fetch the latest matches from SHL"""
        url = ShlApiClient.generate_url("games", season)
        if team_ids:
            params = {'teamIds': ",".join(self._team_ids)}
            return await self.api_wrapper("get", url, params=params)
        return await self.api_wrapper("get", url)

    async def async_get_game(self, season: int, match_id: str) -> dict:
        """Fetch data from a particular SHL match"""
        url = ShlApiClient.generate_url(f"games/{match_id}.json", season)
        return await self.api_wrapper("get", url)

    async def async_get_player_stats(self, season: int, stat: str = "plusminus",  # pylint: disable=dangerous-default-value
                                     team_ids: list[str] = []):
        """Fetch top 10 players in a season according to stat.
        Stat may be assists, goals, points, pim, hits or plusminus."""
        params = {'sort': stat}
        if team_ids:
            params['team_ids'] = ",".join(team_ids)
        url = ShlApiClient.generate_url("statistics/players.json", season)
        return await self.api_wrapper("get", url, params=params)

    async def async_get_goalie_stats(self, season: int, stat: str = "savesPercent",  # pylint: disable=dangerous-default-value
                                     team_ids: list[str] = []):
        """Fetch top 10 goalies in a season according to stat.
        Stat may be saves, savesPercent, goalsAgainst, goalsAgainstAverage, won, tied, lost,
        shooutOuts (?) or minutesInPlay"""
        url = ShlApiClient.generate_url("statistics/goalkeepers.json", season)
        params = {'sort': stat}
        if team_ids:
            params['team_ids'] = ",".join(team_ids)
        return await self.api_wrapper("get", url, params=params)

    async def async_get_teams(self):
        """Fetch all current teams in SHL."""
        url = ShlApiClient.generate_url("teams.json")
        return await self.api_wrapper("get", url)

    async def async_get_team_stats(self, season: int, team_ids: list[str] = []):  # pylint: disable=dangerous-default-value
        """Fetch all team statistics in a season."""
        url = ShlApiClient.generate_url("statistics/teams/standings.json", season)
        if team_ids:
            return await self.api_wrapper("get", url, params={'team_ids': ",".join(team_ids)})
        return await self.api_wrapper("get", url)

    async def async_get_team_player_stats(self, team_code: str):
        """Fetch team information, including staff, players and team facts."""
        url = ShlApiClient.generate_url(f"teams/{team_code}.json")
        return await self.api_wrapper("get", url)

    async def async_get_videos(self, team_ids: list[str] = []):  # pylint: disable=dangerous-default-value
        """Fetch the latest videos from SHL."""
        url = ShlApiClient.generate_url("videos.json")
        if team_ids:
            return await self.api_wrapper("get", url, params={'team_ids': ",".join(team_ids)})
        return await self.api_wrapper("get", url)

    async def async_get_data(self, season: int, team_ids: list[str] = []):  # pylint: disable=dangerous-default-value
        """Update everything"""
        games = await self.async_get_games(season, team_ids)
        articles = await self.async_get_articles(team_ids)
        for _g in games:
            pass
        for _a in articles:
            pass

    async def api_wrapper(  # pylint: disable=dangerous-default-value,too-many-arguments
        self, method: str, url: str, data: dict = {}, headers: dict = {}, params: dict = {}
    ) -> dict:
        """Get information from the API."""
        if not headers and not self.is_connected:
            self.connect()
        try:
            async with async_timeout.timeout(TIMEOUT, loop=asyncio.get_event_loop()):  # pylint: disable=unexpected-keyword-arg
                if method == "get":
                    response = await self._session.get(url,
                                                       headers=headers or self._headers,
                                                       params=params)
                    return await response.json()

                if method == "put":
                    await self._session.put(url,
                                            headers=headers or self._headers,
                                            json=data,
                                            params=params)

                elif method == "patch":
                    await self._session.patch(url,
                                              headers=headers or self._headers,
                                              json=data,
                                              params=params)

                elif method == "post":
                    await self._session.post(url,
                                             headers=headers or self._headers,
                                             json=data,
                                             params=params)

        except asyncio.TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )

        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Something really wrong happened! - %s", exception)
