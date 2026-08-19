"""Config flow for the multi-sport SHL/TheSportsDB integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SportsDbApiClient
from .const import (
    CONF_API_KEY,
    CONF_IS_NATIONAL_TEAM,
    CONF_TEAM_IDS,
    CONF_SPORT,
    CONF_LEAGUE_FILTER,
    CONF_SPECIFIC_LEAGUE,
    DOMAIN,
    LEAGUE_FILTER_ALL,
    LEAGUE_FILTER_NATIONAL,
    LEAGUE_FILTER_SPECIFIC,
    PLATFORMS,
)


class ShlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the multi-sport integration."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._api_key: str = ""
        self._team_name: str = ""
        self._team_candidates: list = []
        self._selected_team: dict = {}
        self._leagues: list = []

    # ------------------------------------------------------------------
    # Step 1 – enter API key and team name
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        """Handle the initial user step: enter API key and team name."""
        self._errors = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            self._team_name = user_input["team_name"].strip()

            session = async_get_clientsession(self.hass)
            client = SportsDbApiClient(self._api_key, [], session)

            # Validate the API key first
            try:
                await client.async_connect()
            except Exception:  # pylint: disable=broad-except
                self._errors["base"] = "auth"
                return await self._show_user_form(user_input)

            # Search for the team
            try:
                candidates = await client.async_search_teams(self._team_name)
            except Exception:  # pylint: disable=broad-except
                candidates = []

            if not candidates:
                self._errors["base"] = "team_not_found"
                return await self._show_user_form(user_input)

            self._team_candidates = candidates

            # If only one result, skip the selection step
            if len(candidates) == 1:
                self._selected_team = candidates[0]
                return await self.async_step_league(None)

            # Multiple results – check whether they span multiple sports
            sports = {(t.get("strSport") or "") for t in candidates}
            if len(sports) > 1:
                return await self.async_step_pick_sport()
            # Same sport but multiple teams
            return await self.async_step_pick_team()

        return await self._show_user_form(user_input)

    async def _show_user_form(self, user_input):
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=(user_input or {}).get(CONF_API_KEY, "")): str,
                    vol.Required("team_name", default=(user_input or {}).get("team_name", "")): str,
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Step 2a – pick sport (when candidates span multiple sports)
    # ------------------------------------------------------------------

    async def async_step_pick_sport(self, user_input=None):
        """Let the user choose a sport when the team name is ambiguous."""
        if user_input is not None:
            chosen_sport = user_input["sport"]
            filtered = [
                t for t in self._team_candidates
                if (t.get("strSport") or "") == chosen_sport
            ]
            if len(filtered) == 1:
                self._selected_team = filtered[0]
                return await self.async_step_league(None)
            self._team_candidates = filtered
            return await self.async_step_pick_team()

        sports = sorted({(t.get("strSport") or "Unknown") for t in self._team_candidates})
        return self.async_show_form(
            step_id="pick_sport",
            data_schema=vol.Schema(
                {vol.Required("sport"): vol.In(sports)}
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Step 2b – pick team from a list
    # ------------------------------------------------------------------

    async def async_step_pick_team(self, user_input=None):
        """Let the user choose the exact team when several candidates exist."""
        if user_input is not None:
            chosen_label = user_input["team"]
            for candidate in self._team_candidates:
                label = _team_label(candidate)
                if label == chosen_label:
                    self._selected_team = candidate
                    break
            else:
                self._selected_team = self._team_candidates[0]
            return await self.async_step_league(None)

        team_choices = [_team_label(t) for t in self._team_candidates]
        return self.async_show_form(
            step_id="pick_team",
            data_schema=vol.Schema(
                {vol.Required("team"): vol.In(team_choices)}
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Step 3 – pick league filter
    # ------------------------------------------------------------------

    async def async_step_league(self, user_input=None):
        """Let the user choose a league filter for the team."""
        is_national = _is_national_team(self._selected_team)

        if user_input is not None:
            league_filter = user_input[CONF_LEAGUE_FILTER]
            specific_league = user_input.get(CONF_SPECIFIC_LEAGUE) or None

            team_name = self._selected_team.get("strTeam", self._team_name)
            sport = self._selected_team.get("strSport")

            data = {
                CONF_API_KEY: self._api_key,
                CONF_TEAM_IDS: [team_name],
                CONF_SPORT: sport,
                CONF_LEAGUE_FILTER: league_filter,
                CONF_SPECIFIC_LEAGUE: specific_league,
                CONF_IS_NATIONAL_TEAM: is_national,
            }
            return self.async_create_entry(title=team_name, data=data)

        # Fetch leagues for the team to populate the specific-league dropdown
        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)
        team_id = self._selected_team.get("idTeam")
        leagues: list = []
        if team_id:
            try:
                leagues = await client.async_get_leagues_for_team(team_id)
            except Exception:  # pylint: disable=broad-except
                leagues = []

        self._leagues = leagues

        filter_options = {
            LEAGUE_FILTER_ALL: "All leagues (including international)",
        }
        # National teams only compete internationally – hiding "national leagues only"
        # prevents a confusing option that would show nothing for e.g. Tre Kronor.
        if not is_national:
            filter_options[LEAGUE_FILTER_NATIONAL] = "National leagues and cups only"
        if leagues:
            filter_options[LEAGUE_FILTER_SPECIFIC] = "Specific league"

        schema_dict = {
            vol.Required(CONF_LEAGUE_FILTER, default=LEAGUE_FILTER_ALL): vol.In(filter_options),
        }
        if leagues:
            schema_dict[vol.Optional(CONF_SPECIFIC_LEAGUE)] = vol.In([""] + leagues)

        return self.async_show_form(
            step_id="league",
            data_schema=vol.Schema(schema_dict),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShlOptionsFlowHandler(config_entry)


class ShlOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(x, default=self.options.get(x, True)): bool
                    for x in sorted(PLATFORMS)
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.title, data=self.options
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _team_label(team: dict) -> str:
    """Return a human-readable label for a team candidate."""
    name = team.get("strTeam") or "Unknown"
    sport = team.get("strSport") or ""
    league = team.get("strLeague") or ""
    parts = [p for p in [sport, league] if p]
    suffix = f" ({', '.join(parts)})" if parts else ""
    return f"{name}{suffix}"


def _is_national_team(team: dict) -> bool:
    """Return True if the team is a national team.

    TheSportsDB marks national teams with ``strType`` equal to ``"National"``.
    As a fallback the league name is also checked for common national-team
    competitions so that the detection works even when ``strType`` is absent.
    """
    if (team.get("strType") or "").casefold() == "national":
        return True
    national_keywords = ("world championship", "olympic", "nations league", "world cup")
    league = (team.get("strLeague") or "").casefold()
    return any(kw in league for kw in national_keywords)
