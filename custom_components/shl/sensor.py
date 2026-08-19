"""Sensor platform for SHL."""
from datetime import date

from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .entity import ShlEntity


def short_name(name: str | None) -> str | None:
    """Return a compact name for Team Tracker attributes."""
    if not name:
        return None
    name = name.strip()
    return name[:3] if len(name) >= 5 else name


def flatten_event(team: dict, event: dict | None, prefix: str) -> dict:
    """Flatten one TheSportsDB event for Team Tracker-style consumers."""
    if not event:
        return {}

    team_id = str(team.get("idTeam", ""))
    home = str(event.get("idHomeTeam", "")) == team_id
    opponent = event.get("strAwayTeam") if home else event.get("strHomeTeam")
    opponent_id = event.get("idAwayTeam") if home else event.get("idHomeTeam")
    opponent_logo = (
        event.get("strAwayTeamBadge") if home else event.get("strHomeTeamBadge")
    )
    team_score = event.get("intHomeScore") if home else event.get("intAwayScore")
    opponent_score = event.get("intAwayScore") if home else event.get("intHomeScore")
    event_date = event.get("dateEventLocal") or event.get("dateEvent")
    event_time = event.get("strTimeLocal") or event.get("strTime")
    event_datetime = event.get("strTimestamp")
    if not event_datetime and event_date and event_time:
        event_datetime = f"{event_date}T{event_time}"
    return {
        prefix: event,
        f"{prefix}_id": event.get("idEvent"),
        f"{prefix}_name": event.get("strEvent"),
        f"{prefix}_league": event.get("strLeague"),
        f"{prefix}_opponent": opponent,
        f"{prefix}_opponent_id": opponent_id,
        f"{prefix}_opponent_logo": opponent_logo,
        f"{prefix}_homeaway": "home" if home else "away",
        f"{prefix}_date": event.get("dateEventLocal") or event.get("dateEvent"),
        f"{prefix}_time": event.get("strTimeLocal") or event.get("strTime"),
        f"{prefix}_timestamp": event_datetime,
        f"{prefix}_location": event.get("strVenue"),
        f"{prefix}_status": event.get("strStatus"),
        f"{prefix}_team_score": team_score,
        f"{prefix}_opponent_score": opponent_score,
    }


def _event_date(event: dict) -> date | None:
    """Return the local calendar date for an event."""
    value = event.get("dateEventLocal") or event.get("dateEvent")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def select_current_event(team: dict) -> tuple[dict, str]:
    """Select live, today's final, or the next event for the card."""
    live_events = team.get("live_events") or []
    if live_events:
        return live_events[0], "IN"

    previous_events = team.get("previous_events") or []
    if previous_events and _event_date(previous_events[0]) == date.today():
        return previous_events[0], "POST"

    next_events = team.get("next_events") or []
    if next_events:
        return next_events[0], "PRE"
    return {}, "NOT_FOUND"


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
                if isinstance(team, dict) and (
                    team.get("requested_team", "").casefold() == self._team_id.casefold()
                    or team.get("team", "").casefold() == self._team_id.casefold()
                ):
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
        _, state = select_current_event(team)
        return state

    @property
    def extra_state_attributes(self):
        """Return Team Tracker-friendly attributes."""
        team = self.team_data
        attrs = {
            "team": self._team_id,
            "team_name": team.get("team_name", self._team_id),
            "team_id": team.get("idTeam"),
            "team_abbr": short_name(team.get("team_name", self._team_id)),
            "league": team.get("strLeague"),
            "league_name": team.get("strLeague"),
            "sport": "hockey" if team.get("strSport") == "Ice Hockey" else team.get("strSport", "hockey"),
            "logo": team.get("strBadge") or team.get("strLogo"),
            "team_logo": team.get("strLogo"),
            "badge": team.get("strBadge"),
            "attribution": "Data provided by TheSportsDB",
            "integration": DOMAIN,
        }
        if team:
            next_events = team.get("next_events") or []
            previous_events = team.get("previous_events") or []
            event, _ = select_current_event(team)
            live_events = team.get("live_events") or []
            current_fields = flatten_event(team, event, "current_game")
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
                    "live_events": live_events,
                    "team_logo": team.get("strBadge") or team.get("strLogo"),
                    "team_long_name": team.get("strTeam", self._team_id),
                    "league_logo": event.get("strLeagueBadge")
                    or team.get("strLeagueBadge"),
                    "team_url": team.get("strWebsite"),
                    "opponent_name": current_fields.get("current_game_opponent"),
                    "opponent_long_name": current_fields.get("current_game_opponent"),
                    "opponent_abbr": short_name(
                        current_fields.get("current_game_opponent")
                    ),
                    "opponent_id": current_fields.get("current_game_opponent_id"),
                    "opponent_logo": current_fields.get("current_game_opponent_logo"),
                    "team_homeaway": current_fields.get("current_game_homeaway"),
                    "opponent_homeaway": (
                        "away"
                        if current_fields.get("current_game_homeaway") == "home"
                        else "home"
                    ),
                    "date": current_fields.get("current_game_timestamp")
                    or current_fields.get("current_game_date"),
                    "event_id": current_fields.get("current_game_id"),
                    "event_name": current_fields.get("current_game_name"),
                    "venue": current_fields.get("current_game_location"),
                    "location": event.get("strCity") or event.get("strCountry"),
                    "team_score": current_fields.get("current_game_team_score"),
                    "opponent_score": current_fields.get("current_game_opponent_score"),
                    "last_update": current_fields.get("current_game_timestamp"),
                }
            )
            attrs.update(flatten_event(team, next_events[0] if next_events else None, "next_game"))
            attrs.update(flatten_event(team, previous_events[0] if previous_events else None, "last_game"))
        return attrs

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return "shl__custom_device_class"
