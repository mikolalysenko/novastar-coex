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


def test_screen_accepts_casing_variants_and_modes():
    a = Screen.from_dict({"screenID": "x", "screenName": "Wall", "workingMode": 1})
    b = Screen.from_dict({"screenId": "x", "name": "Wall", "workingMode": 3})  # manual-era scale
    c = Screen.from_dict({"id": 7})
    assert a.screen_id == b.screen_id == "x"
    assert a.working_mode is b.working_mode is WorkingMode.ALL_IN_ONE
    assert c.screen_id == "7" and c.name == "7" and c.working_mode is None


def test_screen_list_from_wrapper_or_list_and_empty():
    assert len(Screen.list_from({"screens": [{"screenID": "1"}, {"screenID": "2"}]})) == 2
    assert len(Screen.list_from([{"screenID": "1"}])) == 1
    assert Screen.list_from(None) == [] and Screen.list_from({}) == []


def test_screen_layers_pick_current_mode():
    s = Screen.from_dict(
        {
            "screenID": "s",
            "workingMode": 1,
            "layersInWorkingMode": [
                {"workingMode": 0, "layers": [{"id": 0, "source": 5}]},
                {"workingMode": 1, "layers": [{"id": 9, "source": 2}, {"id": 4, "source": 7}]},
            ],
        }
    )
    assert s.main_layer.id == 4 and s.current_source_group == 7


def test_preset_shapes():
    nested = Preset.list_from(
        {
            "screenPresets": [
                {
                    "screenID": "a",
                    "presets": [{"sequenceNumber": 3, "name": "Night", "state": True}],
                }
            ]
        }
    )
    assert nested[0].screen_id == "a" and nested[0].label == "3: Night" and nested[0].active
    alt = Preset.list_from(
        {
            "screenPresetList": [
                {"screenId": "b", "presetList": [{"sequenceNumber": 1, "name": "x"}]}
            ]
        }
    )
    assert alt[0].screen_id == "b"
    flat = Preset.list_from([{"sequenceNumber": 2, "name": "y"}, {"name": "no seq"}])
    assert [p.sequence_number for p in flat] == [2]
    assert Preset.list_from({}) == []


def test_input_source_tolerant():
    s = InputSource.from_dict({"id": 1, "type": 12, "name": "HDMI1", "groupId": 0})
    assert s.type_name == "HDMI2.1" and s.group_id == 0
    bad = InputSource.from_dict({"id": "x", "type": None, "groupId": "nope"})
    assert bad.id == -1 and bad.type == 0xFF and bad.group_id is None


def test_screen_output_raw_values_and_list_object():
    rows = ScreenOutput.list_from(
        {"list": {"screenId": 0, "brightness": 0.4, "colorTemperature": 6500, "gamma": 2.8}}
    )
    assert len(rows) == 1 and rows[0].screen_id == "0" and rows[0].brightness == 0.4
    rows = ScreenOutput.list_from({"list": [{"screenId": 0}, {"screenId": 1}]})
    assert [r.screen_id for r in rows] == ["0", "1"]
    assert ScreenOutput.from_dict({"screenId": "1", "brightness": "abc"}).brightness is None


def test_display_state_read_enum_and_canvas_join():
    st = DisplayState.from_dict(
        {
            "displayState": [{"canvasID": 0, "displayMode": 1}, {"canvasID": 1, "displayMode": 2}],
            "mappingState": [{"canvasID": 0, "enable": True}],
        }
    )
    assert st.modes == {0: DisplayMode.BLACKOUT, 1: DisplayMode.FREEZE}
    assert st.mode_for((0,)) is DisplayMode.BLACKOUT
    assert st.mode_for((0, 1)) is None  # canvases disagree
    assert st.mapping_for((0, 1)) is True and st.mapping_for((5,)) is None
    assert DisplayState.from_dict(None).mode_for(()) is None


def test_monitor_info():
    m = MonitorInfo.from_dict(
        {
            "name": "MX40",
            "temperatureInfos": [{"temperature": 30}, {"temperature": 35.5}],
            "mainBoardTemperature": {"value": 37},
            "fanInfos": [{"fanSpeed": 900}, {"speed": 1000}],
            "cabinets": [{}, {}],
        }
    )
    assert m.max_temperature == 37 and m.fan_speeds == [900, 1000] and m.cabinet_count == 2
    assert MonitorInfo.from_dict({}).max_temperature is None
