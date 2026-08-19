"""Constants for SportsDb Team Tracker."""
# Base component constants
NAME = "SportsDB Team Tracker"
DOMAIN = "teamtracker"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "2026.8.0"

ATTRIBUTION = "Data provided by http://www.thesportsdb.com/"
ISSUE_URL = "https://github.com/dennisgranasen/shl-homeassistant-component/issues"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]


# Configuration and options
CONF_ENABLED = "enabled"
CONF_API_KEY = "api_key"
CONF_TEAM_IDS = "team_ids"
CONF_SPORT = "sport"
CONF_LEAGUE_FILTER = "league_filter"
CONF_SPECIFIC_LEAGUE = "specific_league"
CONF_IS_NATIONAL_TEAM = "is_national_team"

# League filter values
LEAGUE_FILTER_ALL = "all"
LEAGUE_FILTER_NATIONAL = "national"
LEAGUE_FILTER_SPECIFIC = "specific"

# Defaults
DEFAULT_NAME = DOMAIN


# Always block sports from those who bully Ukraine 
BLOCKED_LEAGUES: set[str] = {
    "KHL",
    "Kontinental Hockey League",
    "VHL",
    "Russian Hockey League",
    "MHL",
    "Molodiozhnaya Hockey League",
    "Belarus Extraleague",
    "Belarusian Extraleague",
    "Extraleague Belarus",
}

# International/European-level competitions (filtered out when LEAGUE_FILTER_NATIONAL is chosen)
INTERNATIONAL_LEAGUES: set[str] = {
    # Hockey
    "Champions Hockey League",
    "CHL",
    "IIHF World Championship",
    "IIHF World Junior Championship",
    "IIHF Women's World Championship",
    "Olympic Games",
    "Winter Olympics",
    # Football
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Conference League",
    "FIFA World Cup",
    "UEFA European Championship",
    "UEFA Nations League",
    "FIFA World Cup Qualification",
    "UEFA Euro Qualification",
    "Copa America",
    "CONCACAF Gold Cup",
    "AFC Asian Cup",
    "Africa Cup of Nations",
    # Basketball
    "EuroLeague",
    "EuroCup Basketball",
    "FIBA Basketball World Cup",
    "EuroBasket",
    # Handball
    "EHF Champions League",
    "EHF European League",
    "IHF World Men's Handball Championship",
    "IHF World Women's Handball Championship",
    # Volleyball
    "CEV Champions League",
    "CEV EuroVolley",
    "FIVB Volleyball World Championship",
}


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
