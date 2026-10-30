"""A fake COEX controller: an aiohttp app that speaks the JSON envelope.

Shapes follow NovaStar's live docs at api.coex.novastar.tech (fetched 2026-09-02) and,
where those are silent, the 2023 manual. Every place the live docs and NovaStar's own
npm client disagree is called out in docs/API.md. Core read and write shapes were
verified on MX40 Pro V1.5.0; unverified operations are listed in the hardware notes.
"""

from __future__ import annotations

import importlib.util
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from novastar_coex import CoexClient


def pytest_ignore_collect(collection_path, config):
    """The lightweight client suite does not require Home Assistant."""
    return collection_path.name == "ha" and importlib.util.find_spec("homeassistant") is None


@pytest.fixture(autouse=True)
def allow_fake_controller_sockets(request):
    """The optional HA harness blocks sockets; our fake uses loopback HTTP."""
    if importlib.util.find_spec("pytest_homeassistant_custom_component") is not None:
        request.getfixturevalue("socket_enabled")


# read-side displayMode mirrors the write value (verified on an MX40 Pro; the live doc is wrong)
READ_MODE = {0: 0, 1: 1, 2: 2}  # write value -> read value


@dataclass
class FakeState:
    screens: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "screenID": "screen-1",
                "screenName": "Video Wall",
                "workingMode": 0,  # live doc: 0 send-only, 1 all-in-one
                "lowLatency": False,
                "canvases": [{"canvasID": 0}, {"canvasID": 1}],
                "layersInWorkingMode": [
                    {"workingMode": 0, "layers": [{"id": 0, "layerIndex": 0, "source": 0}]},
                    {
                        "workingMode": 1,
                        "layers": [
                            {"id": 3, "layerIndex": 0, "source": 1},
                            {"id": 4, "layerIndex": 1, "source": 1},
                        ],
                    },
                ],
            }
        ]
    )
    display_mode: int = 0  # write-side value
    brightness_ratio: float = 0.8  # the device stores a 0..1 ratio
    brightness_unit: str = "ratio"  # what displayparams reports: "ratio" or "percent"
    color_temp: int = 6500
    gamma: float = 2.8
    mapping: bool = False
    presets: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"sequenceNumber": 1, "name": "Movie", "state": True},
            {"sequenceNumber": 2, "name": "Games", "state": False},
        ]
    )
    sources: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"id": 1, "type": 12, "name": "HDMI1", "groupId": 0, "usable": True},
            {"id": 2, "type": 12, "name": "HDMI2", "groupId": 1, "usable": False},
        ]
    )
    monitor: dict[str, Any] = field(
        default_factory=lambda: {
            "name": "MX40 Pro",
            "runtime": 3600,
            "totalRuntime": 86400,
            "mainBoardTemperature": {"value": 44.0, "status": 0},
            "temperatureInfos": [{"temperature": 41.5, "temperatureType": 0, "status": 0}],
            "fanInfos": [{"fanSpeed": 1200, "fanType": 0, "status": 0}],
            "voltageInfos": [{"voltage": 12.1, "voltageType": 0, "status": 0}],
            "cabinets": [{"CabinetID": 1}, {"CabinetID": 2}, {"CabinetID": 3}],
        }
    )
    cabinets: list[dict[str, Any]] = field(
        default_factory=lambda: [{"id": 101, "canvasID": 0}, {"id": 102, "canvasID": 0}]
    )
    locked: bool = False
    fail_code: int | None = None  # force every request to return this code
    fail_paths: dict[str, int] = field(default_factory=dict)  # path -> code
    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    def puts(self, path: str) -> list[Any]:
        return [c[2] for c in self.calls if c[0] in ("PUT", "POST") and c[1] == path]


def _ok(data: Any = None) -> web.Response:
    return web.json_response({"code": 0, "message": "Success", "data": data})


def _err(code: int, message: str) -> web.Response:
    return web.json_response({"code": code, "message": message, "data": None})


def make_app(state: FakeState) -> web.Application:
    app = web.Application()

    @web.middleware
    async def record(request: web.Request, handler):  # type: ignore[no-untyped-def]
        body = await request.json() if request.can_read_body else None
        state.calls.append((request.method, request.path, body))
        if state.locked:
            return _err(3, "device locked")
        if state.fail_code is not None:
            return _err(state.fail_code, "forced failure")
        if request.path in state.fail_paths:
            return _err(state.fail_paths[request.path], "forced failure")
        return await handler(request)

    app.middlewares.append(record)
    r = app.router

    def _screen_ids() -> set[str]:
        return {s["screenID"] for s in state.screens}

    async def screens(_: web.Request) -> web.Response:
        return _ok({"screens": state.screens, "screenGroups": []})

    async def display_state(_: web.Request) -> web.Response:
        canvases = [c["canvasID"] for s in state.screens for c in s["canvases"]]
        return _ok(
            {
                "mappingState": [{"canvasID": c, "enable": state.mapping} for c in canvases],
                "displayState": [
                    {"canvasID": c, "displayMode": READ_MODE[state.display_mode]} for c in canvases
                ],
            }
        )

    async def display_params(_: web.Request) -> web.Response:
        b = (
            state.brightness_ratio
            if state.brightness_unit == "ratio"
            else state.brightness_ratio * 100
        )
        # live doc renders `list` as a single object; real boxes may send a list. Emit
        # the object form for one screen and a list otherwise so both are exercised.
        rows = [
            {
                "screenId": i,
                "brightness": b,
                "colorTemperature": state.color_temp,
                "gamma": state.gamma,
            }
            for i, _ in enumerate(state.screens)
        ]
        return _ok({"list": rows[0] if len(rows) == 1 else rows})

    async def set_display_mode(req: web.Request) -> web.Response:
        body = await req.json()
        if "screenIdList" not in body or not isinstance(body["screenIdList"], list):
            return _err(1, "screenIdList required")
        if body.get("value") not in (0, 1, 2):
            return _err(1, "bad value")
        if any(s not in _screen_ids() for s in body["screenIdList"]):
            return _err(1, "unknown screen")
        state.display_mode = int(body["value"])
        return _ok()

    async def set_brightness(req: web.Request) -> web.Response:
        body = await req.json()
        if not isinstance(body.get("screenIdList"), list) or not body["screenIdList"]:
            return _err(1, "screenIdList required")
        b = body.get("brightness")
        if not isinstance(b, int | float) or not 0 <= b <= 1:
            return _err(1, "brightness must be 0..1")
        state.brightness_ratio = float(b)
        return _ok()

    async def set_color_temp(req: web.Request) -> web.Response:
        body = await req.json()
        if not isinstance(body.get("screenIdList"), list):
            return _err(1, "screenIdList required")
        v = body.get("colorTemperature")
        if not isinstance(v, int) or not 1700 <= v <= 15000:
            return _err(1, "colorTemperature out of range")
        state.color_temp = v
        return _ok()

    async def set_gamma(req: web.Request) -> web.Response:
        body = await req.json()
        if not isinstance(body.get("screenIdList"), list):
            return _err(1, "screenIdList required")
        v = body.get("gamma")
        if not isinstance(v, int | float) or not 1 <= v <= 4:
            return _err(1, "gamma out of range")
        state.gamma = float(v)
        return _ok()

    async def presets(_: web.Request) -> web.Response:
        return _ok(
            {
                "screenPresets": [
                    {"screenID": s["screenID"], "presets": state.presets} for s in state.screens
                ]
            }
        )

    async def apply_preset(req: web.Request) -> web.Response:
        body = await req.json()
        if body.get("screenID") not in _screen_ids():
            return _err(1, "unknown screenID")
        seq = body.get("sequenceNumber")
        if seq not in {p["sequenceNumber"] for p in state.presets}:
            return _err(1, "no such preset")
        for p in state.presets:
            p["state"] = p["sequenceNumber"] == seq
        return _ok()

    async def sources(_: web.Request) -> web.Response:
        return _ok(state.sources)

    async def layer_input(req: web.Request) -> web.Response:
        body = await req.json()
        if body.get("screenID") not in _screen_ids():
            return _err(1, "screenID required")
        layers = body.get("layers")
        if not isinstance(layers, list) or not layers:
            return _err(1, "layers required")
        screen = next(s for s in state.screens if s["screenID"] == body["screenID"])
        mode_layers = next(
            m["layers"]
            for m in screen["layersInWorkingMode"]
            if m["workingMode"] == screen["workingMode"]
        )
        for layer in layers:
            target = next((ml for ml in mode_layers if ml["id"] == layer.get("id")), None)
            if target is None:
                return _err(1, f"unknown layer {layer.get('id')}")
            if layer.get("source") not in {s["groupId"] for s in state.sources}:
                return _err(1, "unknown source group")
            target["source"] = layer["source"]
        return _ok()

    async def set_working_mode(req: web.Request) -> web.Response:
        body = await req.json()
        if body.get("screenID") not in _screen_ids():
            return _err(3, "screen not exist, screenID:")
        if body.get("workingMode") not in (0, 1):
            return _err(1, "workingMode must be 0 or 1")
        for s in state.screens:
            if s["screenID"] == body["screenID"]:
                s["workingMode"] = body["workingMode"]
        return _ok()

    async def set_device_mode(req: web.Request) -> web.Response:
        body = await req.json()
        if body.get("mode") not in (2, 3):
            return _err(1, "mode must be 2 or 3")
        return _ok()  # accepted, changes nothing — exactly what the MX40 Pro does

    async def monitor(_: web.Request) -> web.Response:
        return _ok(state.monitor)

    async def cabinets(_: web.Request) -> web.Response:
        return _ok(state.cabinets)

    async def cabinet_mapping(req: web.Request) -> web.Response:
        body = await req.json()
        if not isinstance(body.get("idList"), list) or not body["idList"]:
            return _err(1, "idList required")
        if not isinstance(body.get("enable"), bool):
            return _err(1, "enable required")
        state.mapping = body["enable"]
        return _ok()

    async def identify(req: web.Request) -> web.Response:
        body = await req.json()
        if not isinstance(body.get("enable"), bool):
            return _err(1, "enable required")
        return _ok()

    async def hdr(req: web.Request) -> web.Response:
        body = await req.json()
        if body.get("hdrMode") not in (0, 1, 2, 255):
            return _err(1, "bad hdrMode")
        return _ok()

    r.add_get("/api/v1/screen", screens)
    r.add_get("/api/v1/screen/output/display/state", display_state)
    r.add_get("/api/v1/screen/displayparams", display_params)
    r.add_put("/api/v1/screen/output/displaymode", set_display_mode)
    r.add_put("/api/v1/screen/brightness", set_brightness)
    r.add_put("/api/v1/screen/colortemperature", set_color_temp)
    r.add_put("/api/v1/screen/gamma", set_gamma)
    r.add_get("/api/v1/preset", presets)
    r.add_post("/api/v1/preset/current/update", apply_preset)
    r.add_get("/api/v1/device/input/sources", sources)
    r.add_put("/api/v1/screen/layer/input", layer_input)
    r.add_put("/api/v1/screen/mode", set_working_mode)
    r.add_put("/api/v1/device/hw/mode", set_device_mode)
    r.add_get("/api/v1/device/monitor/info", monitor)
    r.add_get("/api/v1/device/cabinet", cabinets)
    r.add_put("/api/v1/device/cabinet/mapping", cabinet_mapping)
    r.add_put("/api/v1/device/hw/mapping", identify)
    r.add_put("/api/v1/device/input/{id}/hdrmode", hdr)
    return app


@pytest.fixture
def state() -> FakeState:
    return FakeState()


@pytest.fixture
async def server(state: FakeState) -> AsyncIterator[TestServer]:
    srv = TestServer(make_app(state))
    await srv.start_server()
    try:
        yield srv
    finally:
        await srv.close()


@pytest.fixture
async def client(server: TestServer) -> AsyncIterator[CoexClient]:
    async with CoexClient(server.host, server.port, timeout=2.0) as c:
        yield c
