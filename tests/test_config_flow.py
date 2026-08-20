"""Test TheSportsDB config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thesportsdb.const import (
    CONF_API_KEY,
    CONF_IS_NATIONAL_TEAM,
    CONF_LEAGUE_FILTER,
    CONF_SPORT,
    CONF_TEAM_ID,
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
}

FAKE_NATIONAL_TEAM = {
    "idTeam": "5678",
    "strTeam": "Sweden",
    "strSport": "Hockey",
    "strLeague": "IIHF World Championship",
    "strType": "National",
}


async def _start_search_flow(hass):
    """Start the flow and select team search."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "123"}
    )
    assert result["step_id"] == "method"

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"method": "search"}
    )


async def test_successful_config_flow_search(hass):
    """Create an entry after searching for and confirming a team."""
    with patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[FAKE_TEAM],
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_get_leagues_for_team",
        return_value=["Swedish Hockey League", "Champions Hockey League"],
    ):
        result = await _start_search_flow(hass)
        assert result["step_id"] == "search"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"team_name": "HV71"}
        )
        assert result["step_id"] == "confirm_team"
        assert result["description_placeholders"]["team"] == "HV71"
        assert result["description_placeholders"]["leagues"] == (
            "Swedish Hockey League, Champions Hockey League"
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"correct_team": True}
        )

    assert result["step_id"] == "league"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_LEAGUE_FILTER: LEAGUE_FILTER_ALL}
    )

    assert result["type"] == CREATE_ENTRY
    assert result["title"] == "HV71"
    assert result["data"][CONF_TEAM_ID] == "1234"
    assert result["data"][CONF_SPORT] == "Hockey"
    assert result["data"][CONF_LEAGUE_FILTER] == LEAGUE_FILTER_ALL
    assert result["data"][CONF_IS_NATIONAL_TEAM] is False


async def test_config_flow_national_team_hides_national_filter(hass):
    """Hide the national-only filter when the selected team is national."""
    with patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[FAKE_NATIONAL_TEAM],
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_get_leagues_for_team",
        return_value=["IIHF World Championship"],
    ):
        result = await _start_search_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"team_name": "Sweden"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"correct_team": True}
        )

    league_filter_key = next(
        key
        for key in result["data_schema"].schema
        if getattr(key, "schema", None) == CONF_LEAGUE_FILTER
    )
    allowed_values = result["data_schema"].schema[league_filter_key].container
    assert LEAGUE_FILTER_NATIONAL not in allowed_values


async def test_failed_config_flow_bad_key(hass):
    """Show an authentication error when the API key cannot be verified."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_connect",
        side_effect=Exception("bad key"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "bad"}
        )

    assert result["type"] == FORM
    assert result["errors"] == {"base": "auth"}


async def test_failed_config_flow_team_not_found(hass):
    """Show a search error when no team matches the entered name."""
    with patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_search_teams",
        return_value=[],
    ):
        result = await _start_search_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"team_name": "NonExistentTeamXYZ"}
        )

    assert result["type"] == FORM
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "team_not_found"}


async def test_browse_flow_accepts_user_entered_country(hass):
    """Use a typed country together with the selected sport to load leagues."""
    leagues = [{"idLeague": "4380", "strLeague": "Swedish Hockey League"}]

    with patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_connect",
        return_value={},
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_get_sports",
        return_value=["Ice Hockey"],
    ), patch(
        "custom_components.thesportsdb.config_flow.SportsDbApiClient.async_get_leagues",
        return_value=leagues,
    ) as get_leagues:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "123"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"method": "browse"}
        )
        assert result["step_id"] == "browse_sport"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"sport": "Ice Hockey", "country": " Sweden "},
        )

    assert result["step_id"] == "browse_league"
    get_leagues.assert_awaited_once_with(sport="Ice Hockey", country="Sweden")


async def test_options_flow(hass):
    """Save platform settings through the options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={platform: platform != SENSOR for platform in PLATFORMS},
    )

    assert result["type"] == CREATE_ENTRY
    assert entry.options == {SENSOR: False}
