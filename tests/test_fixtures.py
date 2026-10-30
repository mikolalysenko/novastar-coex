"""Parse the JSON captured from a real MX40 Pro (tests/fixtures, 2026-09-03).

Captured with the wall relays OFF: the controller was up, the cabinets were not, so
`device/cabinet` and `displayparams.list` are empty. That is a real state the
integration has to survive.
"""

import json
from pathlib import Path

from novastar_coex import (
    DisplayMode,
    DisplayState,
    InputSource,
    MonitorInfo,
    Preset,
    Screen,
    ScreenOutput,
    WorkingMode,
)

FIX = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIX / name).read_text())["data"]


def test_real_screen():
    screens = Screen.list_from(load("screen.json"))
    assert len(screens) == 1
    s = screens[0]
    assert s.screen_id == "{00000000-0000-4000-8000-000000000001}"
    assert s.name == "Example Wall"
    assert s.working_mode is WorkingMode.SEND_ONLY and s.raw_working_mode == 0
    assert s.canvas_ids == (2048,)
    assert s.main_layer.id == 1 and s.current_source_group == 25
    assert [layer.id for layer in s.layers_by_mode[WorkingMode.ALL_IN_ONE]] == [65537, 65538]


def test_real_sources():
    sources = InputSource.list_from(load("device-input-sources.json"))
    by_name = {s.name: s for s in sources}
    assert by_name["HDMI2.0 1"].group_id == 25 and by_name["HDMI2.0 1"].type_name == "HDMI2.0"
    assert by_name["12G-SDI"].type_name == "SDI_12G"
    assert by_name["internal-source"].type == 0xE0 and by_name["internal-source"].group_id == 224
    assert all(s.usable for s in sources)


def test_real_display_state():
    st = DisplayState.from_dict(load("screen-output-display-state.json"))
    assert st.modes == {2048: DisplayMode.NORMAL} and st.mapping == {2048: False}
    assert st.mode_for((2048,)) is DisplayMode.NORMAL


def test_real_empty_displayparams_and_presets_and_cabinets():
    assert ScreenOutput.list_from(load("screen-displayparams.json")) == []
    assert Preset.list_from(load("preset.json")) == []
    assert load("device-cabinet.json") == []


def test_real_monitor():
    m = MonitorInfo.from_dict(load("device-monitor-info.json"))
    assert m.name.startswith("MX40 Pro")
    assert m.runtime == 300
    assert m.max_temperature == 36.0  # only the main board reports a temperature
    assert m.fan_speeds == [1311, 2861, 2792]
    assert m.cabinet_count is None  # cabinets unpowered


def test_real_displayparams_with_cabinets_on():
    rows = ScreenOutput.list_from(load("screen-displayparams-cabinets-on.json"))
    assert len(rows) == 1
    out = rows[0]
    assert out.screen_id == "{00000000-0000-4000-8000-000000000001}"  # GUID, same as screenID
    assert out.brightness == 1  # ratio: 1 == 100 %
    assert out.color_temperature == 7627 and out.gamma == 2.4


def test_real_cabinets_with_cabinets_on():
    cabinets = load("device-cabinet-cabinets-on.json")
    assert len(cabinets) == 36
    assert all(c["rvCardName"] == "A10s Pro" for c in cabinets)
    assert all(0 <= c["brightness"] <= 1 for c in cabinets)
