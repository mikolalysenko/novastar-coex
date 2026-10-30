import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from novastar_coex import (
    CoexApiError,
    CoexClient,
    CoexConnectionError,
    CoexDeviceLocked,
    DisplayMode,
    WorkingMode,
)


async def test_get_screens(client):
    screens = await client.get_screens()
    assert [s.screen_id for s in screens] == ["screen-1"]
    s = screens[0]
    assert s.name == "Video Wall"
    assert s.working_mode is WorkingMode.SEND_ONLY
    assert s.canvas_ids == (0, 1)
    assert s.main_layer is not None and s.main_layer.id == 0
    assert s.current_source_group == 0


async def test_display_state_uses_read_enum(client, state):
    assert (await client.get_display_state()).mode_for((0, 1)) is DisplayMode.NORMAL
    await client.blackout(["screen-1"])
    assert state.display_mode == 1
    assert (await client.get_display_state()).mode_for((0, 1)) is DisplayMode.BLACKOUT
    await client.freeze(["screen-1"])
    assert (await client.get_display_state()).mode_for((0, 1)) is DisplayMode.FREEZE
    await client.normal()  # empty list = all screens
    assert state.puts("/api/v1/screen/output/displaymode") == [
        {"value": 1, "screenIdList": ["screen-1"]},
        {"value": 2, "screenIdList": ["screen-1"]},
        {"value": 0, "screenIdList": []},
    ]


async def test_brightness_ratio_wire_format(client, state):
    await client.set_brightness(42, ["screen-1"])
    put = state.puts("/api/v1/screen/brightness")[0]
    assert put["screenIdList"] == ["screen-1"] and put["screenIds"] == ["screen-1"]
    assert put["brightness"] == pytest.approx(0.42)
    assert state.brightness_ratio == pytest.approx(0.42)
    status = await client.get_status()
    assert status.output_for("screen-1").brightness_pct == pytest.approx(42)
    assert status.brightness_scale == "ratio"


async def test_brightness_scale_autodetects_percent(server, state):
    state.brightness_unit = "percent"
    async with CoexClient(server.host, server.port) as c:
        status = await c.get_status()  # displayparams reports 80 -> percent firmware
        assert status.brightness_scale == "percent"
        assert status.output_for("screen-1").brightness_pct == pytest.approx(80)
        # the fake only accepts ratio, so the percent write is rejected: proves the
        # client really switched units rather than silently rescaling
        with pytest.raises(CoexApiError):
            await c.set_brightness(30)


async def test_brightness_scale_forced(server, state):
    async with CoexClient(server.host, server.port, brightness_scale="percent") as c:
        with pytest.raises(CoexApiError):
            await c.set_brightness(30)
    async with CoexClient(server.host, server.port, brightness_scale="ratio") as c:
        await c.set_brightness(30)
        assert state.brightness_ratio == pytest.approx(0.3)


async def test_brightness_validates_range(client):
    with pytest.raises(ValueError):
        await client.set_brightness(101)


async def test_color_temperature_and_gamma(client, state):
    await client.set_color_temperature(9300)
    await client.set_gamma(2.2)
    assert state.puts("/api/v1/screen/colortemperature") == [
        {"colorTemperature": 9300, "screenIdList": ["screen-1"]}
    ]
    assert state.puts("/api/v1/screen/gamma") == [{"gamma": 2.2, "screenIdList": ["screen-1"]}]
    with pytest.raises(ValueError):
        await client.set_color_temperature(1000)
    with pytest.raises(ValueError):
        await client.set_gamma(5)


async def test_presets_nested_per_screen(client, state):
    presets = await client.get_presets()
    assert [(p.sequence_number, p.name, p.active, p.screen_id) for p in presets] == [
        (1, "Movie", True, "screen-1"),
        (2, "Games", False, "screen-1"),
    ]
    await client.apply_preset(2)
    assert state.puts("/api/v1/preset/current/update") == [
        {"screenID": "screen-1", "sequenceNumber": 2}
    ]
    status = await client.get_status()
    assert status.active_preset("screen-1").name == "Games"
    with pytest.raises(ValueError):
        await client.apply_preset(0)


async def test_apply_missing_preset_raises_api_error(client):
    with pytest.raises(CoexApiError) as exc:
        await client.apply_preset(9)
    assert exc.value.code == 1
    assert "InvalidParam" in str(exc.value)


async def test_select_input_routes_main_layer(client, state):
    src = await client.select_input("HDMI2")
    assert src.group_id == 1
    body = state.puts("/api/v1/screen/layer/input")[0]
    assert body["screenID"] == "screen-1"
    assert body == {"screenID": "screen-1", "layers": [{"id": 0, "source": 1}]}
    status = await client.get_status()
    assert status.screen("screen-1").current_source_group == 1
    # numeric group id, as int or string; unknown name fails locally
    await client.select_input(0)
    await client.select_input("0")
    with pytest.raises(ValueError):
        await client.select_input("DisplayPort")


async def test_working_mode_round_trip(client, state):
    await client.set_working_mode(WorkingMode.ALL_IN_ONE)
    assert state.puts("/api/v1/screen/mode") == [{"screenID": "screen-1", "workingMode": 1}]
    screen = (await client.get_screens())[0]
    assert screen.working_mode is WorkingMode.ALL_IN_ONE
    # in all-in-one the main layer is the lowest id of that mode's layers
    assert screen.main_layer.id == 3 and screen.current_source_group == 1
    await client.select_input("HDMI1")
    assert state.puts("/api/v1/screen/layer/input")[-1]["layers"] == [{"id": 3, "source": 0}]
    await client.set_working_mode(0)
    assert (await client.get_screens())[0].working_mode is WorkingMode.SEND_ONLY
    await client.set_device_mode(3)  # legacy controller-level call still accepted
    assert state.puts("/api/v1/device/hw/mode") == [{"mode": 3}]


async def test_status_aggregate(client):
    status = await client.get_status()
    assert status.screens[0].screen_id == "screen-1"
    out = status.output_for("screen-1")
    assert out.brightness_pct == pytest.approx(80)
    assert out.color_temperature == 6500 and out.gamma == 2.8
    assert out.display_mode is DisplayMode.NORMAL
    assert out.mapping_enabled is False
    assert [s.name for s in status.sources] == ["HDMI1", "HDMI2"]
    m = status.monitor
    assert m.max_temperature == 44.0  # main board included
    assert m.fan_speeds == [1200] and m.runtime == 3600 and m.cabinet_count == 3


async def test_status_survives_partial_api_errors(client, state):
    state.fail_paths["/api/v1/preset"] = 6
    state.fail_paths["/api/v1/device/monitor/info"] = 36
    state.fail_paths["/api/v1/screen/output/display/state"] = 36
    status = await client.get_status()
    assert status.screens and status.presets == [] and status.monitor is None
    out = status.output_for("screen-1")
    assert out.brightness_pct == pytest.approx(80) and out.display_mode is None


async def test_status_propagates_lock_from_optional_read(client, state):
    # lock appearing mid-poll must surface, not degrade into an empty status
    await client.get_screens()
    state.locked = True
    with pytest.raises(CoexDeviceLocked):
        await client.get_status()


async def test_cabinet_mapping_and_identify(client, state):
    await client.set_cabinet_mapping(True)
    assert state.puts("/api/v1/device/cabinet/mapping") == [{"idList": [101, 102], "enable": True}]
    assert (await client.get_status()).output_for("screen-1").mapping_enabled is True
    await client.identify_controller(False)
    assert state.puts("/api/v1/device/hw/mapping") == [{"enable": False}]


async def test_hdr_mode_validation(client, state):
    await client.set_hdr_mode(1, 255)
    assert ("PUT", "/api/v1/device/input/1/hdrmode", {"hdrMode": 255}) in state.calls
    with pytest.raises(ValueError):
        await client.set_hdr_mode(1, 3)  # DCI is read-only


async def test_device_locked(client, state):
    state.locked = True
    with pytest.raises(CoexDeviceLocked):
        await client.get_screens()


async def test_forced_error_code(client, state):
    state.fail_code = 5
    with pytest.raises(CoexApiError) as exc:
        await client.get_screens()
    assert exc.value.code == 5
    assert "Busying" in str(exc.value)


async def test_connection_error_and_ping():
    async with CoexClient("127.0.0.1", 1, timeout=0.5) as c:
        with pytest.raises(CoexConnectionError):
            await c.get_screens()
        assert await c.ping() is False


async def test_injected_closed_session_is_an_error(server):
    session = aiohttp.ClientSession()
    await session.close()
    c = CoexClient(server.host, server.port, session=session)
    with pytest.raises(CoexConnectionError):
        await c.get_screens()


async def test_http_error_and_bad_envelope(server, state):
    async with CoexClient(server.host, server.port) as c:
        with pytest.raises(CoexConnectionError):  # 404 from the fake router
            await c._get("/api/v1/nope")


@pytest.mark.parametrize("payload", [{"data": []}, [], {"code": None}, {"code": "oops"}])
async def test_malformed_response_is_not_a_success(payload):
    async def response(request):
        return web.json_response(payload)

    app = web.Application()
    app.router.add_get("/api/v1/screen", response)
    async with TestServer(app) as server:
        async with CoexClient(server.host, server.port) as client:
            with pytest.raises(CoexConnectionError):
                await client.get_screens()


@pytest.mark.parametrize("host", ["", "http://wall.local", "wall.local:8001", "wall.local/path"])
def test_invalid_hosts_rejected(host):
    with pytest.raises(ValueError, match="host"):
        CoexClient(host)


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_invalid_ports_rejected(port):
    with pytest.raises(ValueError, match="port"):
        CoexClient("controller.local", port)


def test_host_normalization_and_ipv6_urls():
    assert CoexClient("  WALL.local ").base_url == "http://wall.local:8001"
    assert CoexClient("2001:db8::1").base_url == "http://[2001:db8::1]:8001"
    assert CoexClient("[2001:db8::1]").host == "2001:db8::1"
