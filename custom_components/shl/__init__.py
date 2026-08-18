"""
Custom integration to integrate SHL with Home Assistant.

For more details about this integration, please refer to
https://github.com/dennisgranasen/shl-homeassistant-component
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import SportsDbApiClient
from .const import CONF_API_KEY
from .const import CONF_TEAM_IDS
from .const import DOMAIN
from .const import PLATFORMS
from .const import STARTUP_MESSAGE

SCAN_INTERVAL = timedelta(seconds=30)

ShlApiClient = SportsDbApiClient

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):  # pylint: disable=unused-argument
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    api_key = entry.data.get(CONF_API_KEY) or entry.data.get("client_secret") or entry.data.get("client_id")
    team_ids = entry.data.get(CONF_TEAM_IDS)
    if isinstance(team_ids, str):
        team_ids = [team.strip() for team in team_ids.split(",") if team.strip()]

    session = async_get_clientsession(hass)
    client = ShlApiClient(api_key, team_ids, session)

    coordinator = ShlDataUpdateCoordinator(hass, client=client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    platforms = [platform for platform in PLATFORMS if entry.options.get(platform, True)]
    coordinator.platforms = platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


class ShlDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SportsDbApiClient,
    ) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        try:
            return await self.api.async_get_data()
        except Exception as exception:
            raise UpdateFailed() from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is None:
        return True

    unloaded = await hass.config_entries.async_unload_platforms(entry, coordinator.platforms)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
