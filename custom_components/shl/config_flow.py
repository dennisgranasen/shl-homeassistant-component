"""Adds config flow for SHL."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SportsDbApiClient
from .const import CONF_API_KEY
from .const import CONF_TEAM_IDS
from .const import DOMAIN
from .const import PLATFORMS


class ShlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for shl."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_API_KEY], user_input.get(CONF_TEAM_IDS, [])
            )
            if valid:
                return self.async_create_entry(
                    title="TheSportsDB SHL", data=user_input
                )
            else:
                self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ShlOptionsFlowHandler(config_entry)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_TEAM_IDS): [str],
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, api_key, team_ids):
        """Return true if credentials is valid."""
        try:
            session = async_get_clientsession(self.hass)
            client = SportsDbApiClient(api_key, team_ids, session)
            await client.async_connect()
            return True
        except Exception:  # pylint: disable=broad-except
            pass
        return False


class ShlOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for shl."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
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
            title="TheSportsDB SHL", data=self.options
        )
