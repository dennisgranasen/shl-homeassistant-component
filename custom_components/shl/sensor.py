"""Sensor platform for SHL."""
from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .entity import ShlEntity


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up one sensor per configured SHL team."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    team_ids = entry.data.get("team_ids", [])
    sensors = [ShlSensor(coordinator, entry, team_id) for team_id in team_ids]
    async_add_devices(sensors)


class ShlSensor(ShlEntity):
    """SHL team sensor for a Team Tracker-like dashboard."""

    def __init__(self, coordinator, config_entry, team_id):
        super().__init__(coordinator, config_entry)
        self._team_id = team_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME}_{self._team_id}_{SENSOR}"

    @property
    def unique_id(self):
        """Return a stable unique ID for this team's sensor."""
        return f"{self.config_entry.entry_id}_{self._team_id}"

    @property
    def team_data(self):
        """Return the current data for this sensor's team."""
        body = self.coordinator.data.get("body", [])
        if isinstance(body, list):
            for team in body:
                if isinstance(team, dict) and team.get("team") == self._team_id:
                    return team
            return body[0] if body else {}
        if isinstance(body, dict):
            if body.get("team") == self._team_id or body.get("team_name") == self._team_id:
                return body
        return {}

    @property
    def state(self):
        """Return a compact state value for the team."""
        team = self.team_data
        if not team:
            return "unknown"
        return str(team.get("points", team.get("status", self._team_id)))

    @property
    def extra_state_attributes(self):
        """Return Team Tracker-friendly attributes."""
        team = self.team_data
        attrs = {
            "team": self._team_id,
            "team_name": team.get("team_name", self._team_id),
            "team_id": team.get("idTeam"),
            "team_abbr": team.get("strTeamShort", self._team_id),
            "league": team.get("strLeague"),
            "sport": team.get("strSport", "Ice Hockey"),
            "logo": team.get("strBadge") or team.get("strLogo"),
            "team_logo": team.get("strLogo"),
            "badge": team.get("strBadge"),
            "attribution": "Data provided by TheSportsDB",
            "integration": DOMAIN,
        }
        if team:
            attrs.update(
                {
                    "position": team.get("position"),
                    "games_played": team.get("games_played"),
                    "wins": team.get("wins"),
                    "losses": team.get("losses"),
                    "ot_wins": team.get("ot_wins"),
                    "ot_losses": team.get("ot_losses"),
                    "goals_for": team.get("goals_for"),
                    "goals_against": team.get("goals_against"),
                    "goal_difference": team.get("goal_difference"),
                    "points": team.get("points"),
                    "last_5": team.get("last_5"),
                    "status": team.get("status"),
                }
            )
        return attrs

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return "shl__custom_device_class"
