"""Typed views over the JSON the controller returns.

Parsing is deliberately tolerant and never raises on a malformed field: NovaStar's field
casing drifts between firmware versions and documents (``screenID`` vs ``screenId``), and
several read endpoints have never been observed on real hardware. Every model keeps the
raw dict under ``raw`` so nothing is lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import (
    DISPLAY_STATE_MODES,
    INPUT_TYPES,
    DisplayMode,
    WorkingMode,
    working_mode_from_screen,
)


def _pick(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _int(value: Any, default: int | None = None) -> int | None:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return None


def _as_list(data: Any, *container_keys: str) -> list[dict[str, Any]]:
    """Return a list of dicts from ``data`` whether it is a list or a wrapper dict.

    A wrapper dict is unwrapped through the first container key found; a container that
    holds a single dict (the live docs render ``displayparams.list`` that way) is wrapped
    into a one-element list. An empty dict yields an empty list, never a phantom record.
    """
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in container_keys:
            inner = data.get(key)
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
            if isinstance(inner, dict):
                return [inner]
        return [data] if data else []
    return []


@dataclass(frozen=True)
class Layer:
    id: int
    source: int | None


@dataclass(frozen=True)
class Screen:
    """One logical screen (a wall) configured on the controller."""

    screen_id: str
    name: str
    working_mode: WorkingMode | None = None
    raw_working_mode: int | None = None
    low_latency: bool | None = None
    canvas_ids: tuple[int, ...] = ()
    # layers per working mode, from ``layersInWorkingMode[]`` (keyed by that entry's
    # raw workingMode value mapped through working_mode_from_screen)
    layers_by_mode: dict[WorkingMode, tuple[Layer, ...]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def layers(self) -> tuple[Layer, ...]:
        """Layers of the current working mode (empty if unknown)."""
        if self.working_mode is not None and self.working_mode in self.layers_by_mode:
            return self.layers_by_mode[self.working_mode]
        # single entry regardless of mode → use it
        if len(self.layers_by_mode) == 1:
            return next(iter(self.layers_by_mode.values()))
        return ()

    @property
    def main_layer(self) -> Layer | None:
        """The primary layer: lowest layer id in the current working mode."""
        layers = self.layers
        return min(layers, key=lambda layer: layer.id) if layers else None

    @property
    def current_source_group(self) -> int | None:
        layer = self.main_layer
        return layer.source if layer else None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Screen:
        sid = _pick(d, "screenID", "screenId", "screen_id", "id")
        raw_mode = _int(_pick(d, "workingMode"))
        canvases_raw = d.get("canvases")
        canvases: list[Any] = canvases_raw if isinstance(canvases_raw, list) else []
        canvas_ids = tuple(
            cid
            for cid in (
                _int(_pick(c, "canvasID", "canvasId", "id"))
                for c in canvases
                if isinstance(c, dict)
            )
            if cid is not None
        )
        layers_by_mode: dict[WorkingMode, tuple[Layer, ...]] = {}
        for entry in d.get("layersInWorkingMode") or []:
            if not isinstance(entry, dict):
                continue
            mode = working_mode_from_screen(_int(entry.get("workingMode")))
            layers = tuple(
                Layer(id=lid, source=_int(layer.get("source")))
                for layer in (entry.get("layers") or [])
                if isinstance(layer, dict)
                for lid in [_int(_pick(layer, "id", "layerIndex"))]
                if lid is not None
            )
            if mode is not None:
                layers_by_mode[mode] = layers
        return cls(
            screen_id=str(sid) if sid is not None else "",
            name=str(_pick(d, "screenName", "name", default=sid if sid is not None else "Screen")),
            working_mode=working_mode_from_screen(raw_mode),
            raw_working_mode=raw_mode,
            low_latency=_bool(_pick(d, "lowLatency")),
            canvas_ids=canvas_ids,
            layers_by_mode=layers_by_mode,
            raw=d,
        )

    @classmethod
    def list_from(cls, data: Any) -> list[Screen]:
        return [cls.from_dict(x) for x in _as_list(data, "screens", "list")]


@dataclass(frozen=True)
class Preset:
    """A saved preset slot on the controller (scoped to one screen)."""

    sequence_number: int
    name: str
    active: bool = False
    screen_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def label(self) -> str:
        return f"{self.sequence_number}: {self.name}" if self.name else str(self.sequence_number)

    @classmethod
    def from_dict(cls, d: dict[str, Any], screen_id: str | None = None) -> Preset | None:
        seq = _int(_pick(d, "sequenceNumber", "sequence_number", "id"))
        if seq is None:
            return None
        return cls(
            sequence_number=seq,
            name=str(_pick(d, "name", default="")),
            active=bool(_bool(_pick(d, "state", "active", "isCurrent", default=False))),
            screen_id=screen_id,
            raw=d,
        )

    @classmethod
    def list_from(cls, data: Any) -> list[Preset]:
        """Parse GET /api/v1/preset.

        Live shape: ``{"screenPresets": [{"screenID": ..., "presets": [...]}]}``
        (some builds spell it ``screenPresetList`` / ``presetList``). A bare list of
        presets (no screen scoping) is accepted too.
        """
        out: list[Preset] = []
        if isinstance(data, dict):
            groups = _pick(data, "screenPresets", "screenPresetList")
            if isinstance(groups, list):
                for g in groups:
                    if not isinstance(g, dict):
                        continue
                    sid = _pick(g, "screenID", "screenId")
                    for p in _pick(g, "presets", "presetList", default=[]) or []:
                        if isinstance(p, dict):
                            preset = cls.from_dict(p, str(sid) if sid is not None else None)
                            if preset:
                                out.append(preset)
                return out
        for p in _as_list(data, "presets", "list"):
            preset = cls.from_dict(p)
            if preset:
                out.append(preset)
        return out


@dataclass(frozen=True)
class InputSource:
    """An input connector / source group."""

    id: int
    type: int
    name: str
    group_id: int | None = None
    usable: bool | None = None
    hdr_supported: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def type_name(self) -> str:
        return INPUT_TYPES.get(self.type, f"0x{self.type:02x}")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InputSource:
        sid = _int(_pick(d, "id"))
        stype = _int(_pick(d, "type"))
        return cls(
            id=sid if sid is not None else -1,
            type=stype if stype is not None else 0xFF,
            name=str(_pick(d, "name", default="")),
            group_id=_int(_pick(d, "groupId", "groupID", "group_id")),
            usable=_bool(_pick(d, "usable")),
            hdr_supported=_bool(_pick(d, "isSupportHDR")),
            raw=d,
        )

    @classmethod
    def list_from(cls, data: Any) -> list[InputSource]:
        return [cls.from_dict(x) for x in _as_list(data, "sources", "list")]


@dataclass(frozen=True)
class MonitorInfo:
    """Real-time monitoring: temperatures, fans, voltages, runtime, cabinet count."""

    name: str
    runtime: int | None
    temperatures: list[float]
    fan_speeds: list[int]
    voltages: list[float]
    cabinet_count: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def max_temperature(self) -> float | None:
        return max(self.temperatures) if self.temperatures else None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MonitorInfo:
        def values(key: str, *subs: str) -> list[Any]:
            out = []
            for x in d.get(key) or []:
                if isinstance(x, dict):
                    v = _pick(x, *subs)
                    if v is not None:
                        out.append(v)
            return out

        temps = [
            t
            for t in (_float(v) for v in values("temperatureInfos", "temperature"))
            if t is not None
        ]
        mb = d.get("mainBoardTemperature")
        if isinstance(mb, dict) and _float(mb.get("value")) is not None:
            temps.append(_float(mb.get("value")))  # type: ignore[arg-type]
        elif _float(mb) is not None:
            temps.append(_float(mb))  # type: ignore[arg-type]
        cabinets = d.get("cabinets")
        return cls(
            name=str(_pick(d, "name", default="")),
            runtime=_int(_pick(d, "runtime")),
            temperatures=temps,
            fan_speeds=[
                s
                for s in (_int(v) for v in values("fanInfos", "fanSpeed", "speed"))
                if s is not None
            ],
            voltages=[
                v for v in (_float(x) for x in values("voltageInfos", "voltage")) if v is not None
            ],
            cabinet_count=len(cabinets) if isinstance(cabinets, list) else None,
            raw=d,
        )


@dataclass(frozen=True)
class ScreenOutput:
    """Per-screen output parameters as the controller reports them.

    ``brightness`` is the RAW value from GET /api/v1/screen/displayparams (scale not
    documented; the client detects ratio vs percent and fills ``brightness_pct``).
    ``display_mode`` / ``mapping_enabled`` are joined in from the per-canvas display
    state by the client.
    """

    screen_id: str
    brightness: float | None = None
    brightness_pct: float | None = None
    color_temperature: int | None = None
    gamma: float | None = None
    display_mode: DisplayMode | None = None
    mapping_enabled: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScreenOutput:
        sid = _pick(d, "screenID", "screenId", "screen_id", "screenid", "id")
        return cls(
            screen_id=str(sid) if sid is not None else "",
            brightness=_float(_pick(d, "brightness", "ratio")),
            color_temperature=_int(_pick(d, "colorTemperature", "colorTemp")),
            gamma=_float(_pick(d, "gamma")),
            raw=d,
        )

    @classmethod
    def list_from(cls, data: Any) -> list[ScreenOutput]:
        return [cls.from_dict(x) for x in _as_list(data, "list", "screens", "displayParams")]


@dataclass(frozen=True)
class DisplayState:
    """GET /api/v1/screen/output/display/state, keyed by canvas id."""

    modes: dict[int, DisplayMode] = field(default_factory=dict)
    mapping: dict[int, bool] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, d: Any) -> DisplayState:
        if not isinstance(d, dict):
            return cls()
        modes: dict[int, DisplayMode] = {}
        for item in d.get("displayState") or []:
            if not isinstance(item, dict):
                continue
            cid = _int(_pick(item, "canvasID", "canvasId"))
            mode = _int(_pick(item, "displayMode", "mode", "value"))
            if cid is not None and mode is not None and mode in DISPLAY_STATE_MODES:
                modes[cid] = DISPLAY_STATE_MODES[mode]
        mapping: dict[int, bool] = {}
        for item in d.get("mappingState") or []:
            if not isinstance(item, dict):
                continue
            cid = _int(_pick(item, "canvasID", "canvasId"))
            en = _bool(item.get("enable"))
            if cid is not None and en is not None:
                mapping[cid] = en
        return cls(modes=modes, mapping=mapping, raw=d)

    def mode_for(self, canvas_ids: tuple[int, ...]) -> DisplayMode | None:
        """Mode of a screen = the mode of its canvases when they agree."""
        ids = canvas_ids or tuple(self.modes)
        found = {self.modes[c] for c in ids if c in self.modes}
        return found.pop() if len(found) == 1 else None

    def mapping_for(self, canvas_ids: tuple[int, ...]) -> bool | None:
        ids = canvas_ids or tuple(self.mapping)
        found = [self.mapping[c] for c in ids if c in self.mapping]
        return any(found) if found else None
