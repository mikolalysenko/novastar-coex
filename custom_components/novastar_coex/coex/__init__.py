"""Async client for NovaStar COEX LED controllers (MX40 Pro, MX30, MX20, CX40 Pro, KU20, ...).

The controller speaks plain HTTP + JSON on port 8001. Every response is wrapped in
``{"code": <int>, "message": <str>, "data": <any>}`` where ``code == 0`` means success.

This package is vendored inside the Home Assistant custom component so HACS / a plain
copy ships it with no pip dependency; the wheel built from the repo root re-exports it as
the top-level ``novastar_coex`` package.
"""

from .client import CoexClient, CoexStatus
from .const import DEFAULT_PORT, DisplayMode, HdrMode, WorkingMode
from .errors import CoexApiError, CoexConnectionError, CoexDeviceLocked, CoexError
from .models import DisplayState, InputSource, Layer, MonitorInfo, Preset, Screen, ScreenOutput

__all__ = [
    "CoexApiError",
    "CoexClient",
    "CoexConnectionError",
    "CoexDeviceLocked",
    "CoexError",
    "CoexStatus",
    "DEFAULT_PORT",
    "DisplayMode",
    "DisplayState",
    "HdrMode",
    "InputSource",
    "Layer",
    "MonitorInfo",
    "Preset",
    "Screen",
    "ScreenOutput",
    "WorkingMode",
]

__version__ = "0.2.0"
