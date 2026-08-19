"""Global fixtures for SHL integration."""
from unittest.mock import patch

import aiohttp
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name


@pytest.fixture(autouse=True)
def use_threaded_dns_resolver(monkeypatch):
    """Avoid the pycares shutdown thread in the legacy HA test plugin."""
    monkeypatch.setattr(
        "aiohttp.resolver.AsyncResolver",
        aiohttp.resolver.ThreadedResolver,
    )
    monkeypatch.setattr(
        "homeassistant.helpers.aiohttp_client.AsyncResolver",
        aiohttp.resolver.ThreadedResolver,
    )


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(autouse=True)
def enable_shl_custom_integration(enable_custom_integrations):
    """Allow Home Assistant to discover the custom SHL integration."""
    yield


# This fixture, when used, will result in calls to async_get_data to return None. To have the call
# return a value, we would add the `return_value=<VALUE_TO_RETURN>` parameter to the patch call.
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    with patch(
        "custom_components.shl.SportsDbApiClient.async_get_data",
        return_value={"body": []},
    ), patch(
        "custom_components.shl.SportsDbApiClient.async_connect",
        return_value={"sports": []},
    ):
        yield


# In this fixture, we are forcing calls to async_get_data to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.shl.SportsDbApiClient.async_get_data",
        side_effect=Exception,
    ), patch(
        "custom_components.shl.SportsDbApiClient.async_connect",
        side_effect=Exception,
    ):
        yield
