"""Sample API Client."""
import asyncio
import logging
import socket

from datetime import datetime
from datetime import timedelta
import aiohttp
import async_timeout

from .const import NAME
from .const import VERSION

TIMEOUT = 10


_LOGGER: logging.Logger = logging.getLogger(__package__)

HEADERS = {"Content-type": "application/json; charset=UTF-8", "User-Agent": f"{NAME}/{VERSION}"}
BASE_URL = "https://openapi.shl.se"
AUTH = "/oauth2/token"


def normalize_team_stats(stats: dict) -> dict:
    """Normalize a team payload into a simple, card-friendly structure."""
    if not isinstance(stats, dict):
        return {}

    normalized = dict(stats)
    goals_for = normalized.get("goals_for")
    goals_against = normalized.get("goals_against")
    if goals_for is not None and goals_against is not None:
        normalized["goal_difference"] = int(goals_for) - int(goals_against)

    return normalized


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
        self._expires = datetime.now() + timedelta(seconds=int(body["expires_in"]))
        self._headers = HEADERS.copy()
        self._headers["Authorization"] = f"Bearer {body['access_token']}"
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
        url = ShlApiClient.generate_url("articles.json")
        if team_ids:
            params = {'teamIds': ",".join(team_ids)}
            return await self.api_wrapper("get", url, params=params)
        return await self.api_wrapper("get", url)

    async def async_get_games(self, season: int, team_ids: list[str]) -> dict:
        """Fetch the latest matches from SHL"""
        url = ShlApiClient.generate_url("games.json", season)
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

    async def async_get_data(self, season: int = 0, team_ids: list[str] = None):  # pylint: disable=dangerous-default-value
        """Fetch a lightweight team-tracker payload for the configured teams."""
        selected_teams = team_ids or self._team_ids or []
        teams = []

        for team_code in selected_teams:
            team_payload = await self.async_get_team_player_stats(team_code)
            team_data = team_payload.get("team") if isinstance(team_payload, dict) else {}
            if not isinstance(team_data, dict):
                team_data = {}
            team_data.setdefault("team", team_code)
            team_data.setdefault("team_name", team_code)
            teams.append(normalize_team_stats(team_data))

        if len(teams) == 1:
            return {"team": teams[0], "teams": teams, "body": teams[0]}

        return {"teams": teams, "body": teams}

    async def api_wrapper(  # pylint: disable=dangerous-default-value,too-many-arguments
        self, method: str, url: str, data: dict = {}, headers: dict = {}, params: dict = {}
    ) -> dict:
        """Get information from the API."""
        if not headers and not self.is_connected():
            await self.async_connect()
        try:
            async with async_timeout.timeout(TIMEOUT):
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
                    response = await self._session.post(
                        url,
                        headers=headers or self._headers,
                        json=data,
                        params=params,
                    )
                    return await response.json()

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


SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
SPORTSDB_V2_BASE_URL = "https://www.thesportsdb.com/api/v2/json"
TEAM_ALIASES = {
    "djurgården": "Djurgårdens IF",
    "skellefteå": "Skellefteå AIK",
    "växjö": "Växjö Lakers",
    "örebro": "Örebro HK",
}
SUPPORTED_LEAGUES = {"Swedish Hockey League", "Swedish Hockey Allsvenskan"}


def _event_sort_key(event: dict) -> str:
    """Return a sortable timestamp for a TheSportsDB event."""
    return event.get("strTimestamp") or (
        f"{event.get('dateEvent', '')}T{event.get('strTime', '')}"
    )


class SportsDbApiClient:
    """Access SHL team and schedule data from TheSportsDB v1 API."""

    def __init__(
        self, api_key: str, team_ids: list[str], session: aiohttp.ClientSession
    ) -> None:
        self._api_key = api_key
        self._team_ids = team_ids or []
        self._session = session

    def _url(self, endpoint: str) -> str:
        return f"{SPORTSDB_BASE_URL}/{self._api_key}/{endpoint}"

    async def _request(self, endpoint: str, params: dict | None = None) -> dict:
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.get(self._url(endpoint), params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def async_get_live_scores(self) -> list[dict]:
        """Return current ice hockey scores from the Premium v2 API."""
        url = f"{SPORTSDB_V2_BASE_URL}/livescore/Ice%20Hockey"
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.get(
                url, headers={"X-API-KEY": self._api_key}
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        return payload.get("livescore") or []

    async def async_connect(self) -> dict:
        """Validate the configured key with a lightweight API request."""
        return await self._request("all_sports.php")

    async def async_get_team(self, team_name: str) -> dict:
        """Find a team by name."""
        search_names = [team_name]
        alias = TEAM_ALIASES.get(team_name.casefold())
        if alias:
            search_names.append(alias)
        if not alias:
            search_names.append(f"{team_name} IF")

        for search_name in search_names:
            payload = await self._request("searchteams.php", {"t": search_name})
            teams = payload.get("teams") or []
            shl_teams = [
                team
                for team in teams
                if team.get("strLeague") in SUPPORTED_LEAGUES
            ]
            for team in shl_teams:
                if team.get("strTeam", "").casefold() == search_name.casefold():
                    return team
            if shl_teams:
                return shl_teams[0]
        return {}

    async def async_get_next_events(self, team_id: str) -> list[dict]:
        """Return the next five events for a team."""
        payload = await self._request("eventsnext.php", {"id": team_id})
        events = payload.get("eventsnext") or payload.get("events") or []
        return sorted(events, key=_event_sort_key)

    async def async_get_previous_events(self, team_id: str) -> list[dict]:
        """Return the previous five events for a team."""
        payload = await self._request("eventslast.php", {"id": team_id})
        events = payload.get("results") or payload.get("events") or []
        return sorted(events, key=_event_sort_key, reverse=True)

    async def async_get_data(self) -> dict:
        """Fetch Team Tracker-compatible data for configured teams."""
        try:
            live_scores = await self.async_get_live_scores()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            live_scores = []

        teams = []
        for team_name in self._team_ids:
            team = await self.async_get_team(team_name)
            if not team:
                continue
            team_id = team.get("idTeam")
            next_events = await self.async_get_next_events(team_id) if team_id else []
            previous_events = (
                await self.async_get_previous_events(team_id) if team_id else []
            )
            live_events = [
                event
                for event in live_scores
                if str(event.get("idHomeTeam")) == str(team_id)
                or str(event.get("idAwayTeam")) == str(team_id)
            ]
            teams.append(
                {
                    **team,
                    "requested_team": team_name,
                    "team": team.get("strTeam", team_name),
                    "team_name": team.get("strTeam", team_name),
                    "next_events": next_events,
                    "previous_events": previous_events,
                    "live_events": live_events,
                    "status": next_events[0].get("strStatus") if next_events else None,
                }
            )

        if len(teams) == 1:
            return {"team": teams[0], "teams": teams, "body": teams[0]}
        return {"teams": teams, "body": teams}
