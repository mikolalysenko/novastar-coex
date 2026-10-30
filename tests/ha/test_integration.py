"""Verify entity state, service writes, recovery and lifecycle through Home Assistant."""

from copy import deepcopy
from dataclasses import replace

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def test_setup_and_unload(hass, setup_entry):
    assert setup_entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(er.async_get(hass), setup_entry.entry_id)
    assert len(entities) == 12
    expected = {
        "switch.video_wall_display": "on",
        "switch.video_wall_freeze": "off",
        "switch.video_wall_cabinet_mapping": "off",
        "number.video_wall_brightness": "80.0",
        "number.video_wall_color_temperature": "6500",
        "number.video_wall_gamma": "2.8",
        "select.video_wall_working_mode": "Send-Only",
        "select.video_wall_input": "HDMI1",
        "select.video_wall_preset": "1: Movie",
        "sensor.video_wall_temperature": "44.0",
        "sensor.video_wall_runtime": "3600",
        "sensor.video_wall_cabinets": "3",
    }
    for entity_id, value in expected.items():
        assert hass.states.get(entity_id).state == value
    coordinator = setup_entry.runtime_data
    shared_session = await coordinator.client._get_session()
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED
    assert coordinator._unsub_refresh is None
    assert not shared_session.closed


@pytest.mark.parametrize(
    "domain,service,entity,data,attribute,value",
    [
        ("switch", "turn_off", "display", {}, "display_mode", 1),
        ("switch", "turn_on", "freeze", {}, "display_mode", 2),
        ("switch", "turn_on", "cabinet_mapping", {}, "mapping", True),
        ("number", "set_value", "brightness", {"value": 37}, "brightness_ratio", 0.37),
        ("number", "set_value", "color_temperature", {"value": 7000}, "color_temp", 7000),
        ("number", "set_value", "gamma", {"value": 2.2}, "gamma", 2.2),
    ],
)
async def test_entity_writes(
    hass, setup_entry, state, domain, service, entity, data, attribute, value
):
    await hass.services.async_call(
        domain, service, {"entity_id": f"{domain}.video_wall_{entity}", **data}, blocking=True
    )
    assert getattr(state, attribute) == pytest.approx(value)


@pytest.mark.parametrize(
    "entity,option",
    [("working_mode", "All-in-One"), ("input", "HDMI2"), ("preset", "2: Games")],
)
async def test_select_writes(hass, setup_entry, state, entity, option):
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": f"select.video_wall_{entity}", "option": option},
        blocking=True,
    )
    assert hass.states.get(f"select.video_wall_{entity}").state == option
    if entity == "input":
        assert state.puts("/api/v1/screen/layer/input")[-1]["layers"] == [{"id": 0, "source": 1}]


async def test_locked_then_recovers(hass, setup_entry, state):
    state.locked = True
    coordinator = setup_entry.runtime_data
    await coordinator.async_refresh()
    assert hass.states.get("switch.video_wall_display").state == "unavailable"
    state.locked = False
    await coordinator.async_refresh()
    assert hass.states.get("switch.video_wall_display").state == "on"


async def test_failed_write_is_reported(hass, setup_entry, state):
    state.locked = True
    with pytest.raises(HomeAssistantError, match="locked"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": "switch.video_wall_display"}, blocking=True
        )
    assert state.display_mode == 0


async def test_setup_retries_when_offline(hass, entry, state):
    state.locked = True
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_optional_monitor_failure_does_not_leave_stale_values(hass, setup_entry, state):
    coordinator = setup_entry.runtime_data
    for _ in range(5):
        await coordinator.async_refresh()
    assert sum(path == "/api/v1/device/monitor/info" for _, path, _ in state.calls) == 1
    state.fail_paths["/api/v1/device/monitor/info"] = 6
    await coordinator.async_refresh()
    assert hass.states.get("sensor.video_wall_temperature").state == "unknown"
    assert hass.states.get("switch.video_wall_display").state == "on"
    state.fail_paths.clear()
    await coordinator.async_refresh()
    assert hass.states.get("sensor.video_wall_temperature").state == "44.0"


async def test_removed_screen_is_unavailable(hass, setup_entry):
    coordinator = setup_entry.runtime_data
    coordinator.async_set_updated_data(replace(coordinator.data, screens=[]))
    assert hass.states.get("number.video_wall_brightness").state == "unavailable"
    assert hass.states.get("sensor.video_wall_temperature").state == "44.0"


async def test_multiple_screens_and_reload_keep_unique_entities(hass, entry, state):
    second = deepcopy(state.screens[0])
    second.update(screenID="screen-2", screenName="Second Wall")
    state.screens.append(second)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    before = {
        entity.unique_id: entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert len(before) == 21  # nine controls per screen and three controller sensors
    assert hass.states.get("switch.video_wall_second_wall_display").state == "on"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = {
        entity.unique_id: entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert before == after
