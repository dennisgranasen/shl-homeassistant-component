"""Constants for TheSportsDB Team Tracker tests."""
from custom_components.thesportsdb.const import CONF_API_KEY
from custom_components.thesportsdb.const import CONF_TEAM_ID
from custom_components.thesportsdb.const import CONF_SPORT
from custom_components.thesportsdb.const import CONF_LEAGUE_FILTER
from custom_components.thesportsdb.const import LEAGUE_FILTER_ALL


MOCK_CONFIG = {
    CONF_API_KEY: "123",
    CONF_TEAM_ID: "HV71",
    CONF_SPORT: "Hockey",
    CONF_LEAGUE_FILTER: LEAGUE_FILTER_ALL,
}
