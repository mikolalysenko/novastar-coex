"""Run the real integration against an in-process fake controller."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.novastar_coex.const import DOMAIN


@pytest.fixture(autouse=True)
def integration_enabled(enable_custom_integrations, socket_enabled):
    """Enable custom components and loopback HTTP for the fake controller."""


@pytest.fixture
def entry(hass, server):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Video Wall",
        unique_id=f"{server.host}:{server.port}",
        data={"host": server.host, "port": server.port, "name": "Video Wall"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_entry(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
