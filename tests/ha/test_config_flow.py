"""Exercise the UI flow and failures users encounter during installation."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.novastar_coex.coex import CoexApiError, CoexConnectionError
from custom_components.novastar_coex.const import DOMAIN


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_user_flow(hass, server):
    flow = await start(hass)
    assert flow["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {"host": f" {server.host} ", "port": server.port, "name": "  My Wall  "},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Wall"
    assert result["data"] == {"host": server.host, "port": server.port, "name": "My Wall"}
    assert result["result"].unique_id == f"{server.host}:{server.port}"


async def test_duplicate(hass, server, entry):
    flow = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": server.host, "port": server.port}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bracketed_ipv6_is_the_same_controller(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="2001:db8::1:8001",
        data={"host": "2001:db8::1", "port": 8001},
    )
    entry.add_to_hass(hass)
    flow = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": "[2001:db8::1]"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("case,error", [("locked", "device_locked"), ("empty", "no_screens")])
async def test_controller_not_ready(hass, server, state, case, error):
    if case == "locked":
        state.locked = True
    else:
        state.screens = []
    flow = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"host": server.host, "port": server.port}
    )
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize("host", ["http://controller.local", "controller.local:8001", "   "])
async def test_invalid_host(hass, host):
    flow = await start(hass)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {"host": host})
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.parametrize(
    "exc,error",
    [
        (CoexConnectionError("offline"), "cannot_connect"),
        (CoexApiError(6, "unsupported"), "api_error"),
    ],
)
async def test_errors(hass, exc, error):
    flow = await start(hass)
    with patch(
        "custom_components.novastar_coex.config_flow.CoexClient.get_screens",
        new=AsyncMock(side_effect=exc),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "controller.local"}
        )
    assert result["errors"] == {"base": error}
