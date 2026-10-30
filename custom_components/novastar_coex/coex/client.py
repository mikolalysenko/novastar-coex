"""Async HTTP client for the COEX API."""

from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import aiohttp

from .const import (
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    EP_BRIGHTNESS,
    EP_CABINET_MAPPING,
    EP_CABINETS,
    EP_COLOR_TEMPERATURE,
    EP_CONTROLLER_BEACON,
    EP_CONTROLLER_NAME,
    EP_DEVICE_IDENTIFY,
    EP_DEVICE_MODE,
    EP_DISPLAY_MODE,
    EP_DISPLAY_MODE_CANVAS,
    EP_DISPLAY_PARAMS,
    EP_DISPLAY_STATE,
    EP_GAMMA,
    EP_INPUT_HDR_MODE,
    EP_INPUT_SOURCES,
    EP_LAYER_INPUT,
    EP_MONITOR_INFO,
    EP_PRESET_APPLY,
    EP_PRESETS,
    EP_SCREEN_WORKING_MODE,
    EP_SCREENS,
    HDR_MODE_SETTABLE,
    SUCCESS_CODES,
    DisplayMode,
    HdrMode,
    WorkingMode,
)
from .errors import CoexApiError, CoexConnectionError, CoexDeviceLocked, CoexError
from .models import DisplayState, InputSource, MonitorInfo, Preset, Screen, ScreenOutput

_LOGGER = logging.getLogger(__name__)

BrightnessScale = Literal["auto", "ratio", "percent"]


@dataclass
class CoexStatus:
    """Everything the Home Assistant coordinator (and the CLI) wants in one poll."""

    screens: list[Screen] = field(default_factory=list)
    outputs: dict[str, ScreenOutput] = field(default_factory=dict)
    presets: list[Preset] = field(default_factory=list)
    sources: list[InputSource] = field(default_factory=list)
    display_state: DisplayState = field(default_factory=DisplayState)
    monitor: MonitorInfo | None = None
    brightness_scale: str = "ratio"

    def screen(self, screen_id: str) -> Screen | None:
        return next((s for s in self.screens if s.screen_id == screen_id), None)

    def output_for(self, screen_id: str) -> ScreenOutput | None:
        return self.outputs.get(screen_id)

    def presets_for(self, screen_id: str) -> list[Preset]:
        return [p for p in self.presets if p.screen_id in (None, screen_id)]

    def active_preset(self, screen_id: str | None = None) -> Preset | None:
        pool = self.presets_for(screen_id) if screen_id else self.presets
        return next((p for p in pool if p.active), None)

    def source_by_group(self, group_id: int | None) -> InputSource | None:
        if group_id is None:
            return None
        return next((s for s in self.sources if s.group_id == group_id), None)


class CoexClient:
    """Thin async wrapper around the controller's HTTP/JSON API.

    A ``aiohttp.ClientSession`` may be injected (Home Assistant shares one); otherwise a
    private session is created lazily and closed by :meth:`close`.

    ``brightness_scale`` controls the unit sent to ``PUT /api/v1/screen/brightness``.
    An MX40 Pro (2026-09-03) confirmed the live docs: 0..1 (``ratio``). NovaStar's own
    npm client sends 0..100 (``percent``), which may match other firmware. ``auto``
    (default) assumes ratio until a read of ``GET /api/v1/screen/displayparams`` reports
    a value above 1, which would prove a percent firmware.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        brightness_scale: BrightnessScale = "auto",
    ) -> None:
        host = host.strip().lower()
        try:
            address = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?\.?", host):
                raise ValueError(
                    "host must be an IP address or hostname, without a URL or port"
                ) from None
            url_host = host
        else:
            host = str(address)
            url_host = f"[{host}]" if address.version == 6 else host
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        self.host = host
        self.port = port
        self.base_url = f"http://{url_host}:{port}"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._owns_session = session is None
        self._brightness_scale: BrightnessScale = brightness_scale
        self._detected_scale: str | None = None

    # -- session plumbing ---------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        elif self._session.closed:
            if not self._owns_session:
                raise CoexConnectionError("injected aiohttp session is closed")
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> CoexClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- transport ----------------------------------------------------------

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        _LOGGER.debug("%s %s %s", method, url, json)
        try:
            async with session.request(method, url, json=json, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    raise CoexConnectionError(f"{method} {path}: HTTP {resp.status}")
                try:
                    payload = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise CoexConnectionError(f"{method} {path}: non-JSON reply") from err
        except (TimeoutError, aiohttp.ClientError, OSError) as err:
            raise CoexConnectionError(f"{method} {path}: {err}") from err

        if not isinstance(payload, dict) or "code" not in payload:
            raise CoexConnectionError(f"{method} {path}: missing COEX response envelope")
        raw_code = payload["code"]
        try:
            code = int(raw_code)
        except (TypeError, ValueError) as err:
            raise CoexConnectionError(f"{method} {path}: bad code {raw_code!r}") from err
        if code not in SUCCESS_CODES:
            message = str(payload.get("message", ""))
            if "locked" in message.lower():
                raise CoexDeviceLocked(code, message, path)
            raise CoexApiError(code, message, path)
        return payload.get("data")

    async def _get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def _put(self, path: str, body: dict[str, Any]) -> Any:
        return await self._request("PUT", path, body)

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        return await self._request("POST", path, body)

    # -- brightness scale ---------------------------------------------------

    @property
    def brightness_scale(self) -> str:
        """The unit actually used for brightness writes right now."""
        if self._brightness_scale != "auto":
            return self._brightness_scale
        return self._detected_scale or "ratio"

    def _learn_scale(self, outputs: list[ScreenOutput]) -> None:
        for out in outputs:
            if out.brightness is None:
                continue
            if out.brightness > 1.0:
                self._detected_scale = "percent"
                return
            if 0.0 < out.brightness < 1.0:
                self._detected_scale = "ratio"
                return
        # exactly 0 or 1 is ambiguous: keep whatever we knew

    def _to_pct(self, raw: float | None) -> float | None:
        if raw is None:
            return None
        return raw * 100.0 if self.brightness_scale == "ratio" else raw

    # -- reads --------------------------------------------------------------

    async def ping(self) -> bool:
        """True if the controller answers the screen list. Never raises."""
        try:
            await self.get_screens()
        except CoexApiError:
            return True  # reachable, just unhappy
        except CoexError:
            return False
        return True

    async def get_screens(self) -> list[Screen]:
        return Screen.list_from(await self._get(EP_SCREENS))

    async def get_display_params(self) -> list[ScreenOutput]:
        """Brightness / colour temperature / gamma per screen (raw values)."""
        outputs = ScreenOutput.list_from(await self._get(EP_DISPLAY_PARAMS))
        self._learn_scale(outputs)
        return outputs

    async def get_display_state(self) -> DisplayState:
        return DisplayState.from_dict(await self._get(EP_DISPLAY_STATE))

    async def get_presets(self) -> list[Preset]:
        return Preset.list_from(await self._get(EP_PRESETS))

    async def get_input_sources(self) -> list[InputSource]:
        return InputSource.list_from(await self._get(EP_INPUT_SOURCES))

    async def get_monitor_info(self) -> MonitorInfo:
        data = await self._get(EP_MONITOR_INFO)
        return MonitorInfo.from_dict(data if isinstance(data, dict) else {})

    async def get_cabinets(self) -> list[dict[str, Any]]:
        data = await self._get(EP_CABINETS)
        if isinstance(data, dict):
            data = data.get("cabinets") or data.get("list") or []
        return [x for x in (data or []) if isinstance(x, dict)] if isinstance(data, list) else []

    async def get_status(self, *, include_monitor: bool = True) -> CoexStatus:
        """One aggregated poll.

        ``get_screens`` failing raises (the controller is effectively down). Every other
        read is optional: an API or transport error there is logged and that part of the
        status is left empty, so one unsupported endpoint never takes the whole poll
        down. A VMP lock always propagates.
        """
        status = CoexStatus(screens=await self.get_screens())

        async def try_read(name: str, coro: Any) -> Any:
            try:
                return await coro
            except CoexDeviceLocked:
                raise
            except (CoexApiError, CoexConnectionError) as err:
                _LOGGER.debug("%s unavailable: %s", name, err)
                return None

        params: list[ScreenOutput] = (
            await try_read("display params", self.get_display_params()) or []
        )
        state: DisplayState = (
            await try_read("display state", self.get_display_state()) or DisplayState()
        )
        status.display_state = state
        status.brightness_scale = self.brightness_scale
        outputs: dict[str, ScreenOutput] = {}
        for screen in status.screens:
            base = next((p for p in params if p.screen_id == screen.screen_id), None)
            if base is None and len(params) == 1 and len(status.screens) == 1:
                base = params[0]  # single screen: the one row is ours whatever its id says
            out = base if base else ScreenOutput(screen_id=screen.screen_id)
            outputs[screen.screen_id] = replace(
                out,
                screen_id=screen.screen_id,
                brightness_pct=self._to_pct(out.brightness),
                display_mode=state.mode_for(screen.canvas_ids),
                mapping_enabled=state.mapping_for(screen.canvas_ids),
            )
        status.outputs = outputs
        status.presets = await try_read("presets", self.get_presets()) or []
        status.sources = await try_read("input sources", self.get_input_sources()) or []
        if include_monitor:
            status.monitor = await try_read("monitor info", self.get_monitor_info())
        return status

    # -- helpers ------------------------------------------------------------

    async def _resolve_screen_ids(self, screen_ids: list[str] | None) -> list[str]:
        if screen_ids:
            return [str(s) for s in screen_ids]
        ids = [s.screen_id for s in await self.get_screens() if s.screen_id]
        if not ids:
            raise CoexApiError(35, "No screens configured on the controller", EP_SCREENS)
        return ids

    async def _resolve_screen(self, screen_id: str | None) -> Screen:
        screens = await self.get_screens()
        if screen_id is not None:
            for s in screens:
                if s.screen_id == str(screen_id):
                    return s
            raise ValueError(f"unknown screen {screen_id!r}")
        if not screens:
            raise CoexApiError(35, "No screens configured on the controller", EP_SCREENS)
        return screens[0]

    # -- writes: display ----------------------------------------------------

    async def set_display_mode(
        self, mode: DisplayMode | int, screen_ids: list[str] | None = None
    ) -> None:
        """PUT /api/v1/screen/output/displaymode. An empty ``screenIdList`` means all screens."""
        await self._put(
            EP_DISPLAY_MODE,
            {"value": int(mode), "screenIdList": [str(s) for s in (screen_ids or [])]},
        )

    async def set_display_mode_canvases(
        self, mode: DisplayMode | int, canvas_ids: list[int]
    ) -> None:
        """PUT /api/v1/device/displaymode — the per-canvas variant of the same setting."""
        if not canvas_ids:
            raise ValueError("canvas_ids must not be empty")
        await self._put(EP_DISPLAY_MODE_CANVAS, {"value": int(mode), "canvasIDs": list(canvas_ids)})

    async def normal(self, screen_ids: list[str] | None = None) -> None:
        await self.set_display_mode(DisplayMode.NORMAL, screen_ids)

    async def blackout(self, screen_ids: list[str] | None = None) -> None:
        await self.set_display_mode(DisplayMode.BLACKOUT, screen_ids)

    async def freeze(self, screen_ids: list[str] | None = None) -> None:
        await self.set_display_mode(DisplayMode.FREEZE, screen_ids)

    async def set_brightness(self, percent: float, screen_ids: list[str] | None = None) -> None:
        """Set screen brightness. ``percent`` is always 0..100; the wire unit follows
        :attr:`brightness_scale`. Both list-key spellings are sent because NovaStar's
        docs (``screenIdList``) and client (``screenIds``) disagree; extra keys are
        ignored by the controller."""
        if not 0 <= percent <= 100:
            raise ValueError("brightness must be 0..100 percent")
        ids = await self._resolve_screen_ids(screen_ids)
        value = percent / 100.0 if self.brightness_scale == "ratio" else float(percent)
        await self._put(EP_BRIGHTNESS, {"brightness": value, "screenIdList": ids, "screenIds": ids})

    async def set_color_temperature(self, kelvin: int, screen_ids: list[str] | None = None) -> None:
        if not 1700 <= kelvin <= 15000:
            raise ValueError("colour temperature must be 1700..15000 K")
        ids = await self._resolve_screen_ids(screen_ids)
        await self._put(
            EP_COLOR_TEMPERATURE, {"colorTemperature": int(kelvin), "screenIdList": ids}
        )

    async def set_gamma(self, gamma: float, screen_ids: list[str] | None = None) -> None:
        if not 1.0 <= gamma <= 4.0:
            raise ValueError("gamma must be 1.0..4.0")
        ids = await self._resolve_screen_ids(screen_ids)
        await self._put(EP_GAMMA, {"gamma": float(gamma), "screenIdList": ids})

    # -- writes: working mode / presets / inputs ----------------------------

    async def set_working_mode(self, mode: WorkingMode | int, screen_id: str | None = None) -> None:
        """Switch a screen between Send-Only (raw pass-through) and All-In-One (scaler).

        ``PUT /api/v1/screen/mode {"screenID", "workingMode": 0|1}`` — verified on an
        MX40 Pro: takes effect within a couple of seconds and the screen's
        ``layersInWorkingMode`` entry for the new mode becomes active.
        """
        mode = WorkingMode(int(mode))
        screen = await self._resolve_screen(screen_id)
        await self._put(
            EP_SCREEN_WORKING_MODE, {"screenID": screen.screen_id, "workingMode": int(mode)}
        )

    async def set_device_mode(self, mode: int) -> None:
        """Legacy controller-level mode (manual §5.3, 2 send-only / 3 all-in-one).

        Accepted by the MX40 Pro but does not change a screen's working mode; kept for
        older firmware. Prefer :meth:`set_working_mode`.
        """
        await self._put(EP_DEVICE_MODE, {"mode": int(mode)})

    async def apply_preset(self, sequence_number: int, screen_id: str | None = None) -> None:
        if sequence_number < 1:
            raise ValueError("sequence_number must be >= 1")
        screen = await self._resolve_screen(screen_id)
        await self._post(
            EP_PRESET_APPLY, {"screenID": screen.screen_id, "sequenceNumber": int(sequence_number)}
        )

    def _match_source(self, sources: list[InputSource], source: int | str) -> InputSource:
        # exact name first, then group id (int or numeric string), never by connector id
        by_name = next((s for s in sources if s.name == str(source)), None)
        if by_name is not None:
            return by_name
        try:
            gid = int(source)
        except (TypeError, ValueError):
            gid = None
        if gid is not None:
            by_group = next((s for s in sources if s.group_id == gid), None)
            if by_group is not None:
                return by_group
        raise ValueError(f"unknown input source {source!r}")

    async def select_input(self, source: int | str, screen_id: str | None = None) -> InputSource:
        """Route an input source group onto a screen's main layer.

        Body: ``{"screenID", "layers": [{"id", "source"}]}`` (verified on an MX40 Pro;
        the ``{"groupId"}``-only form NovaStar's npm client sends is rejected with
        "screen not exist"). The layer id comes from the screen's current working mode
        (main = lowest id; 0 if the controller reported none).
        """
        sources = await self.get_input_sources()
        match = self._match_source(sources, source)
        if match.group_id is None:
            raise ValueError(f"input source {match.name!r} has no groupId")
        screen = await self._resolve_screen(screen_id)
        layer = screen.main_layer
        layer_id = layer.id if layer else 0
        await self._put(
            EP_LAYER_INPUT,
            {"screenID": screen.screen_id, "layers": [{"id": layer_id, "source": match.group_id}]},
        )
        return match

    async def switch_layer_source(self, screen_id: str, layers: list[dict[str, int]]) -> None:
        """Layer-level routing: ``layers=[{"id": <layer>, "source": <group>}]``."""
        await self._put(EP_LAYER_INPUT, {"screenID": str(screen_id), "layers": layers})

    async def set_hdr_mode(self, input_id: int, mode: HdrMode | int) -> None:
        mode = HdrMode(int(mode))
        if mode not in HDR_MODE_SETTABLE:
            raise ValueError(f"hdrMode {mode.name} cannot be set; use HDR10/HLG/SDR/AUTO")
        await self._put(EP_INPUT_HDR_MODE.format(id=int(input_id)), {"hdrMode": int(mode)})

    # -- writes: identify / misc --------------------------------------------

    async def set_cabinet_mapping(self, enable: bool, cabinet_ids: list[int] | None = None) -> None:
        """Paint cabinet numbers on the wall (PUT /api/v1/device/cabinet/mapping)."""
        ids = list(cabinet_ids or [])
        if not ids:
            ids = [c["id"] for c in await self.get_cabinets() if isinstance(c.get("id"), int)]
        if not ids:
            raise CoexApiError(35, "No cabinets reported by the controller", EP_CABINETS)
        await self._put(EP_CABINET_MAPPING, {"idList": ids, "enable": bool(enable)})

    async def identify_controller(self, enable: bool) -> None:
        """Controller-level identify (PUT /api/v1/device/hw/mapping {enable})."""
        await self._put(EP_DEVICE_IDENTIFY, {"enable": bool(enable)})

    async def controller_beacon(
        self, enable: bool, rgb: tuple[int, int, int] = (0, 255, 0)
    ) -> None:
        """Colour the controller's LCD to identify it (POST /api/v1/device/hw/colorBeacon)."""
        r, g, b = rgb
        if not all(0 <= c <= 255 for c in (r, g, b)):
            raise ValueError("rgb components must be 0..255")
        await self._post(
            EP_CONTROLLER_BEACON, {"enable": bool(enable), "color": {"r": r, "g": g, "b": b}}
        )

    async def set_controller_name(self, name: str) -> None:
        if len(name) > 255:
            raise ValueError("name must be at most 255 characters")
        await self._put(EP_CONTROLLER_NAME, {"customName": name})
