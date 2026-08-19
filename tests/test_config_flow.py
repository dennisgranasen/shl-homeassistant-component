"""Test TheSportsDB config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant import data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thesportsdb.const import (
    CONF_API_KEY,
    CONF_IS_NATIONAL_TEAM,
    CONF_TEAM_IDS,
    CONF_SPORT,
    CONF_LEAGUE_FILTER,
    CONF_SPECIFIC_LEAGUE,
    DOMAIN,
    LEAGUE_FILTER_ALL,
    LEAGUE_FILTER_NATIONAL,
    PLATFORMS,
    SENSOR,
)

from .const import MOCK_CONFIG


FORM = data_entry_flow.FlowResultType.FORM
CREATE_ENTRY = data_entry_flow.FlowResultType.CREATE_ENTRY

FAKE_TEAM = {
    "idTeam": "1234",
    "strTeam": "HV71",
    "strSport": "Hockey",
    "strLeague": "Swedish Hockey League",
    "strBadge": None,
}

FAKE_NATIONAL_TEAM = {
    "idTeam": "5678",
    "strTeam": "Sweden",
    "strSport": "Hockey",
    "strLeague": "IIHF World Championship",
    "strType": "National",
    "strBadge": None,
}


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch("custom_components.shl.async_setup", return_value=True), patch(
        "custom_components.shl.async_setup_entry", return_value=True
    ):
        yield


# ---------------------------------------------------------------------------
# Happy-path: single team, single sport -> skip to league step
# ---------------------------------------------------------------------------

async def test_successful_config_flow_single_team(hass, bypass_get_data):
    """Test a successful flow when the search returns exactly one team."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[FAKE_TEAM],
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_get_leagues_for_team",
        return_value=["Swedish Hockey League", "Champions Hockey League"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "123", "team_name": "HV71"},
        )

    # Should jump straight to the league step
    assert result["type"] == FORM
    assert result["step_id"] == "league"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LEAGUE_FILTER: LEAGUE_FILTER_ALL},
    )

    assert result["type"] == CREATE_ENTRY
    assert result["title"] == "HV71"
    assert result["data"][CONF_TEAM_IDS] == ["HV71"]
    assert result["data"][CONF_SPORT] == "Hockey"
    assert result["data"][CONF_LEAGUE_FILTER] == LEAGUE_FILTER_ALL
    assert result["data"][CONF_IS_NATIONAL_TEAM] is False


# ---------------------------------------------------------------------------
# Multi-sport ambiguity -> pick_sport -> league
# ---------------------------------------------------------------------------

async def test_config_flow_multi_sport(hass, bypass_get_data):
    """Test flow when team name matches multiple sports."""
    hockey_team = {**FAKE_TEAM}
    soccer_team = {
        "idTeam": "5678",
        "strTeam": "HV71",
        "strSport": "Soccer", # It's funny because HV71 is a hockey team, but let's pretend it's also a soccer team for this test
        "strLeague": "Swedish Allsvenskan",
        "strBadge": None,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[hockey_team, soccer_team],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "123", "team_name": "HV71"},
        )

    assert result["type"] == FORM
    assert result["step_id"] == "pick_sport"

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_get_leagues_for_team",
        return_value=["Swedish Hockey League"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"sport": "Hockey"},
        )

    # Only one team left after sport filter -> goes to league step
    assert result["type"] == FORM
    assert result["step_id"] == "league"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LEAGUE_FILTER: LEAGUE_FILTER_NATIONAL},
    )

    assert result["type"] == CREATE_ENTRY
    assert result["data"][CONF_LEAGUE_FILTER] == LEAGUE_FILTER_NATIONAL


# ---------------------------------------------------------------------------
# National team: LEAGUE_FILTER_NATIONAL must not be an available option
# ---------------------------------------------------------------------------

async def test_config_flow_national_team_hides_national_filter(hass, bypass_get_data):
    """Test that the national-leagues-only filter is hidden for national teams."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[FAKE_NATIONAL_TEAM],
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_get_leagues_for_team",
        return_value=["IIHF World Championship"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "123", "team_name": "Sweden"},
        )

    assert result["type"] == FORM
    assert result["step_id"] == "league"

    # The schema must not contain LEAGUE_FILTER_NATIONAL as a valid choice
    schema_keys = {
        str(k): v
        for k, v in result["data_schema"].schema.items()
    }
    league_filter_key = next(
        k for k in result["data_schema"].schema
        if getattr(k, "schema", None) == CONF_LEAGUE_FILTER or str(k) == CONF_LEAGUE_FILTER
    )
    allowed_values = result["data_schema"].schema[league_filter_key].container
    assert LEAGUE_FILTER_NATIONAL not in allowed_values

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LEAGUE_FILTER: LEAGUE_FILTER_ALL},
    )

    assert result["type"] == CREATE_ENTRY
    assert result["data"][CONF_IS_NATIONAL_TEAM] is True
    assert result["data"][CONF_LEAGUE_FILTER] == LEAGUE_FILTER_ALL


# ---------------------------------------------------------------------------
# Bad credentials
# ---------------------------------------------------------------------------

async def test_failed_config_flow_bad_key(hass, bypass_get_data):
    """Test flow failure when API key is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_connect",
        side_effect=Exception("bad key"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "bad", "team_name": "HV71"},
        )

    assert result["type"] == FORM
    assert result["errors"] == {"base": "auth"}


# ---------------------------------------------------------------------------
# Team not found
# ---------------------------------------------------------------------------

async def test_failed_config_flow_team_not_found(hass, bypass_get_data):
    """Test flow failure when team name is not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.shl.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "123", "team_name": "NonExistentTeamXYZ"},
        )

    assert result["type"] == FORM
    assert result["errors"] == {"base": "team_not_found"}


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

async def test_options_flow(hass):
    """Test the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={platform: platform != SENSOR for platform in PLATFORMS},
    )

    assert result["type"] == CREATE_ENTRY
    assert entry.options == {SENSOR: False}
