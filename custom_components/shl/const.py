"""Constants for SHL."""
# Base component constants
NAME = "SHL"
DOMAIN = "shl"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"

ATTRIBUTION = "Data provided by http://openapi.shl.se/"
ISSUE_URL = "https://github.com/dennisgranasen/shl-homeassistant-component/issues"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Platforms
BINARY_SENSOR = "binary_sensor"
SENSOR = "sensor"
SWITCH = "switch"
PLATFORMS = [BINARY_SENSOR, SENSOR, SWITCH]


# Configuration and options
CONF_ENABLED = "enabled"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_TEAM_IDS = "team_ids"

# Defaults
DEFAULT_NAME = DOMAIN


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
