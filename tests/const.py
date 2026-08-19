"""Constants for TheSportsDB Team Tracker tests."""
from custom_components.shl.const import CONF_API_KEY
from custom_components.shl.const import CONF_TEAM_IDS
from custom_components.shl.const import CONF_SPORT
from custom_components.shl.const import CONF_LEAGUE_FILTER
from custom_components.shl.const import LEAGUE_FILTER_ALL


MOCK_CONFIG = {
    CONF_API_KEY: "123",
    CONF_TEAM_IDS: ["HV71"],
    CONF_SPORT: "Hockey",
    CONF_LEAGUE_FILTER: LEAGUE_FILTER_ALL,
}
