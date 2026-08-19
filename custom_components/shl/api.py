"""API clients for the SHL / multi-sport Home Assistant integration."""
import asyncio
import logging
import socket

from datetime import datetime
from datetime import timedelta
import aiohttp
import async_timeout

from .const import NAME
from .const import VERSION
from .const import BLOCKED_LEAGUES
from .const import INTERNATIONAL_LEAGUES
from .const import LEAGUE_FILTER_ALL
from .const import LEAGUE_FILTER_NATIONAL
from .const import LEAGUE_FILTER_SPECIFIC

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
    """Access the OpenAPI for the Swedish national hockey league (SHL)."""

    def __init__(
        self, client_id: str, client_secret: str, team_ids: list,
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
        self._headers["Authorization"] = "Bearer " + body["access_token"]
        return body

    def is_connected(self) -> bool:
        """Check if authorization is valid."""
        return self._headers and self._expires > datetime.now()

    @staticmethod
    def generate_url(query: str, season: int = 0) -> str:
        """Generate the url for a specific query."""
        return f"{BASE_URL}/seasons/{season}/{query}" if season else f"{BASE_URL}/{query}"

    async def async_get_team_player_stats(self, team_code: str):
        """Fetch team information, including staff, players and team facts."""
        url = ShlApiClient.generate_url(f"teams/{team_code}.json")
        return await self.api_wrapper("get", url)

    async def async_get_data(self, season: int = 0, team_ids: list = None):
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


# ---------------------------------------------------------------------------
# TheSportsDB client
# ---------------------------------------------------------------------------

SPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
SPORTSDB_V2_BASE_URL = "https://www.thesportsdb.com/api/v2/json"


def _event_sort_key(event: dict) -> str:
    """Return a sortable timestamp for a TheSportsDB event."""
    return event.get("strTimestamp") or (
        f"{event.get('dateEvent', '')}T{event.get('strTime', '')}"
    )


def _is_blocked(league: str) -> bool:
    """Return True if the league name matches a blocked (RU/BY) league."""
    return league in BLOCKED_LEAGUES


def _is_international(league: str) -> bool:
    """Return True if the league is an international competition."""
    return league in INTERNATIONAL_LEAGUES


def _filter_events(
    events: list,
    league_filter: str,
    specific_league,
) -> list:
    """Apply league filtering to a list of TheSportsDB events."""
    result = []
    for event in events:
        league = event.get("strLeague") or ""
        if _is_blocked(league):
            continue
        if league_filter == LEAGUE_FILTER_NATIONAL and _is_international(league):
            continue
        if league_filter == LEAGUE_FILTER_SPECIFIC and specific_league:
            if league.casefold() != specific_league.casefold():
                continue
        result.append(event)
    return result


class SportsDbApiClient:
    """Access team and schedule data from TheSportsDB v1/v2 API.

    Supports any sport available on TheSportsDB.  League filtering lets users
    choose between all leagues, national-only (no international cups), or a
    single specific league.  Russian and Belarusian leagues are always excluded.
    """

    def __init__(
        self,
        api_key: str,
        team_ids: list,
        session: aiohttp.ClientSession,
        sport=None,
        league_filter: str = LEAGUE_FILTER_ALL,
        specific_league=None,
    ) -> None:
        self._api_key = api_key
        self._team_ids = team_ids or []
        self._session = session
        self._sport = sport            # e.g. "Ice Hockey", "Soccer"; None = any sport
        self._league_filter = league_filter
        self._specific_league = specific_league

    def _url(self, endpoint: str) -> str:
        return f"{SPORTSDB_BASE_URL}/{self._api_key}/{endpoint}"

    async def _request(self, endpoint: str, params=None) -> dict:
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.get(self._url(endpoint), params=params) as response:
                response.raise_for_status()
                return await response.json()

    async def async_get_live_scores(self) -> list:
        """Return current live scores from the Premium v2 API for the configured sport."""
        sport = self._sport or "Ice Hockey"
        url = f"{SPORTSDB_V2_BASE_URL}/livescore/{sport.replace(' ', '%20')}"
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

    async def async_search_teams(self, team_name: str) -> list:
        """Search for teams by name, excluding blocked leagues.

        Returns all matching TheSportsDB team dicts regardless of sport or
        league, except for teams in blocked (Russian/Belarusian) leagues.
        """
        payload = await self._request("searchteams.php", {"t": team_name})
        teams = payload.get("teams") or []
        return [
            team for team in teams
            if not _is_blocked(team.get("strLeague") or "")
        ]

    async def async_get_team(self, team_name: str, sport=None) -> dict:
        """Find the best matching team by name, optionally filtered by sport.

        1. Search TheSportsDB by name.
        2. Filter to the requested sport (if provided or configured).
        3. Prefer an exact name match; otherwise return the first result.
        """
        target_sport = sport or self._sport
        teams = await self.async_search_teams(team_name)
        if not teams:
            return {}

        if target_sport:
            sport_teams = [
                t for t in teams
                if (t.get("strSport") or "").casefold() == target_sport.casefold()
            ]
            if sport_teams:
                teams = sport_teams

        for team in teams:
            if team.get("strTeam", "").casefold() == team_name.casefold():
                return team
        return teams[0]

    async def async_get_leagues_for_team(self, team_id: str) -> list:
        """Return distinct non-blocked league names from the team's recent events."""
        next_events = await self.async_get_next_events(team_id, apply_filter=False)
        prev_events = await self.async_get_previous_events(team_id, apply_filter=False)
        leagues = []
        seen: set = set()
        for event in next_events + prev_events:
            league = event.get("strLeague") or ""
            if league and league not in seen and not _is_blocked(league):
                seen.add(league)
                leagues.append(league)
        return leagues

    async def async_get_next_events(self, team_id: str, apply_filter: bool = True) -> list:
        """Return upcoming events for a team with optional league filtering."""
        payload = await self._request("eventsnext.php", {"id": team_id})
        events = payload.get("eventsnext") or payload.get("events") or []
        events = sorted(events, key=_event_sort_key)
        if apply_filter:
            events = _filter_events(events, self._league_filter, self._specific_league)
        return events

    async def async_get_previous_events(self, team_id: str, apply_filter: bool = True) -> list:
        """Return past events for a team with optional league filtering."""
        payload = await self._request("eventslast.php", {"id": team_id})
        events = payload.get("results") or payload.get("events") or []
        events = sorted(events, key=_event_sort_key, reverse=True)
        if apply_filter:
            events = _filter_events(events, self._league_filter, self._specific_league)
        return events

    def _apply_live_score_filter(self, live_scores: list) -> list:
        """Remove blocked/filtered leagues from live scores."""
        result = [e for e in live_scores if not _is_blocked(e.get("strLeague") or "")]
        if self._league_filter == LEAGUE_FILTER_NATIONAL:
            result = [e for e in result if not _is_international(e.get("strLeague") or "")]
        elif self._league_filter == LEAGUE_FILTER_SPECIFIC and self._specific_league:
            result = [
                e for e in result
                if (e.get("strLeague") or "").casefold() == self._specific_league.casefold()
            ]
        return result

    async def async_get_data(self) -> dict:
        """Fetch Team Tracker-compatible data for all configured teams."""
        try:
            live_scores = await self.async_get_live_scores()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            live_scores = []

        live_scores = self._apply_live_score_filter(live_scores)

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
