"""Config flow for TheSportsDB integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SportsDbApiClient
from .const import (
    CONF_API_KEY,
    CONF_IS_NATIONAL_TEAM,
    CONF_LEAGUE_FILTER,
    CONF_SPECIFIC_LEAGUE,
    CONF_SPORT,
    CONF_TEAM_ID,
    DOMAIN,
    LEAGUE_FILTER_ALL,
    LEAGUE_FILTER_NATIONAL,
    LEAGUE_FILTER_SPECIFIC,
    PLATFORMS,
)


class SportsDbFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TheSportsDB integration."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._errors = {}
        self._api_key: str = ""

        self._team_name: str = ""
        self._team_candidates: list = []
        self._selected_team: dict = {}

        self._selected_sport: str = ""
        self._selected_country: str = ""
        self._selected_league: dict = {}

        self._sports: list = []
        self._countries: list = []
        self._leagues: list = []
        self._teams: list = []

    # ------------------------------------------------------------------
    # Step 1 – API key
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input=None):
        """Enter API key."""
        self._errors = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()

            session = async_get_clientsession(self.hass)
            client = SportsDbApiClient(self._api_key, [], session)

            try:
                await client.async_connect()
            except Exception:  # pylint: disable=broad-except
                self._errors["base"] = "auth"
            else:
                return await self.async_step_method()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY,
                        default=(user_input or {}).get(CONF_API_KEY, ""),
                    ): str,
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Step 2 – choose search or browse
    # ------------------------------------------------------------------

    async def async_step_method(self, user_input=None):
        """Choose how to find the team."""
        if user_input is not None:
            method = user_input["method"]

            if method == "search":
                return await self.async_step_search()

            return await self.async_step_browse_sport()

        return self.async_show_form(
            step_id="method",
            data_schema=vol.Schema(
                {
                    vol.Required("method"): vol.In(
                        {
                            "search": "Search for team",
                            "browse": "Browse by sport and league",
                        }
                    )
                }
            ),
        )

    # ------------------------------------------------------------------
    # Search path
    # ------------------------------------------------------------------

    async def async_step_search(self, user_input=None):
        """Search for a team by name."""
        self._errors = {}

        if user_input is not None:
            self._team_name = user_input["team_name"].strip()

            session = async_get_clientsession(self.hass)
            client = SportsDbApiClient(self._api_key, [], session)

            try:
                candidates = await client.async_search_teams(self._team_name)
            except Exception:  # pylint: disable=broad-except
                candidates = []

            if not candidates:
                self._errors["base"] = "team_not_found"
            else:
                # Free API search may only return one result.
                # Keep the list structure in case that changes.
                self._team_candidates = candidates
                self._selected_team = candidates[0]

                return await self.async_step_confirm_team()

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "team_name",
                        default=(user_input or {}).get("team_name", ""),
                    ): str,
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Confirm search result
    # ------------------------------------------------------------------

    async def async_step_confirm_team(self, user_input=None):
        """Confirm that the search result is the desired team."""
        if user_input is not None:
            if user_input["correct_team"]:
                return await self.async_step_league()

            # Wrong result: let the user choose another lookup method.
            return await self.async_step_method()

        return self.async_show_form(
            step_id="confirm_team",
            data_schema=vol.Schema(
                {
                    vol.Required("correct_team", default=True): bool,
                }
            ),
            description_placeholders={
                "team": self._selected_team.get("strTeam", "Unknown"),
                "sport": self._selected_team.get("strSport", "Unknown"),
                "league": self._selected_team.get("strLeague", "Unknown"),
            },
        )

    # ------------------------------------------------------------------
    # Browse path – sport
    # ------------------------------------------------------------------

    async def async_step_browse_sport(self, user_input=None):
        """Choose sport."""
        self._errors = {}

        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)

        if user_input is not None:
            self._selected_sport = user_input["sport"]
            return await self.async_step_browse_country()

        try:
            self._sports = await client.async_get_sports()
        except Exception:  # pylint: disable=broad-except
            self._sports = []

        if not self._sports:
            self._errors["base"] = "cannot_load_sports"

        return self.async_show_form(
            step_id="browse_sport",
            data_schema=vol.Schema(
                {
                    vol.Required("sport"): vol.In(self._sports),
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Browse path – country
    # ------------------------------------------------------------------

    async def async_step_browse_country(self, user_input=None):
        """Choose country."""
        self._errors = {}

        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)

        if user_input is not None:
            self._selected_country = user_input["country"]
            return await self.async_step_browse_league()

        try:
            self._countries = await client.async_get_countries()
        except Exception:  # pylint: disable=broad-except
            self._countries = []

        if not self._countries:
            self._errors["base"] = "cannot_load_countries"

        return self.async_show_form(
            step_id="browse_country",
            data_schema=vol.Schema(
                {
                    vol.Required("country"): vol.In(self._countries),
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Browse path – league
    # ------------------------------------------------------------------

    async def async_step_browse_league(self, user_input=None):
        """Choose league."""
        self._errors = {}

        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)

        if user_input is not None:
            league_id = user_input["league"]

            for league in self._leagues:
                if str(league.get("idLeague")) == league_id:
                    self._selected_league = league
                    break

            return await self.async_step_browse_team()

        try:
            self._leagues = await client.async_get_leagues(
                sport=self._selected_sport,
                country=self._selected_country,
            )
        except Exception:  # pylint: disable=broad-except
            self._leagues = []

        if not self._leagues:
            self._errors["base"] = "cannot_load_leagues"

        league_choices = {
            str(league["idLeague"]): league.get("strLeague", "Unknown")
            for league in self._leagues
            if league.get("idLeague")
        }

        return self.async_show_form(
            step_id="browse_league",
            data_schema=vol.Schema(
                {
                    vol.Required("league"): vol.In(league_choices),
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # Browse path – team
    # ------------------------------------------------------------------

    async def async_step_browse_team(self, user_input=None):
        """Choose team."""
        self._errors = {}

        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)

        if user_input is not None:
            team_id = user_input["team"]

            for team in self._teams:
                if str(team.get("idTeam")) == team_id:
                    self._selected_team = team
                    break

            return await self.async_step_league()

        league_id = self._selected_league.get("idLeague")

        try:
            self._teams = await client.async_get_teams_for_league(league_id)
        except Exception:  # pylint: disable=broad-except
            self._teams = []

        if not self._teams:
            self._errors["base"] = "cannot_load_teams"

        team_choices = {
            str(team["idTeam"]): team.get("strTeam", "Unknown")
            for team in sorted(
                self._teams,
                key=lambda team: (team.get("strTeam") or "").casefold(),
            )
            if team.get("idTeam")
        }

        return self.async_show_form(
            step_id="browse_team",
            data_schema=vol.Schema(
                {
                    vol.Required("team"): vol.In(team_choices),
                }
            ),
            errors=self._errors,
        )

    # ------------------------------------------------------------------
    # League filtering
    # ------------------------------------------------------------------

    async def async_step_league(self, user_input=None):
        """Choose league filtering for the selected team."""
        self._errors = {}

        is_national = _is_national_team(self._selected_team)

        if user_input is not None:
            league_filter = user_input[CONF_LEAGUE_FILTER]
            specific_league = user_input.get(CONF_SPECIFIC_LEAGUE) or None

            team_name = self._selected_team.get("strTeam", self._team_name)
            team_id = self._selected_team.get("idTeam")
            sport = self._selected_team.get("strSport")

            if not team_id:
                self._errors["base"] = "team_not_found"
            else:
                data = {
                    CONF_API_KEY: self._api_key,

                    # Store the real TheSportsDB team ID.
                    CONF_TEAM_ID: str(team_id),

                    CONF_SPORT: sport,
                    CONF_LEAGUE_FILTER: league_filter,
                    CONF_SPECIFIC_LEAGUE: specific_league,
                    CONF_IS_NATIONAL_TEAM: is_national,
                }

                return self.async_create_entry(
                    title=team_name,
                    data=data,
                )

        session = async_get_clientsession(self.hass)
        client = SportsDbApiClient(self._api_key, [], session)

        team_id = self._selected_team.get("idTeam")

        leagues = []

        if team_id:
            try:
                leagues = await client.async_get_leagues_for_team(team_id)
            except Exception:  # pylint: disable=broad-except
                leagues = []

        filter_options = {
            LEAGUE_FILTER_ALL: "All leagues (including international)",
        }

        if not is_national:
            filter_options[LEAGUE_FILTER_NATIONAL] = (
                "National leagues and cups only"
            )

        if leagues:
            filter_options[LEAGUE_FILTER_SPECIFIC] = "Specific league"

        schema_dict = {
            vol.Required(
                CONF_LEAGUE_FILTER,
                default=LEAGUE_FILTER_ALL,
            ): vol.In(filter_options),
        }

        if leagues:
            schema_dict[vol.Optional(CONF_SPECIFIC_LEAGUE)] = vol.In(
                [""] + leagues
            )

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
        """Return options flow."""
        return SportsDbOptionsFlowHandler(config_entry)


class SportsDbOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        platform,
                        default=self.options.get(platform, True),
                    ): bool
                    for platform in sorted(PLATFORMS)
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(
            title=self.config_entry.title,
            data=self.options,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_national_team(team: dict) -> bool:
    """Return True if the team is a national team."""
    if (team.get("strType") or "").casefold() == "national":
        return True

    national_keywords = (
        "world championship",
        "olympic",
        "nations league",
        "world cup",
    )

    league = (team.get("strLeague") or "").casefold()

    return any(keyword in league for keyword in national_keywords)