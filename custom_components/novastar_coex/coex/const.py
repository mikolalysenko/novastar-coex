"""Constants: ports, enums, error codes and endpoint paths for the COEX HTTP API.

Two NovaStar sources describe this API and they disagree in places: the 2023 PDF manual
(legacy ``/api/v1/device/...`` paths) and the live docs at api.coex.novastar.tech (which
NovaStar's own ``@novastar-dev/coex`` client only partly follows). Where they conflict
the live docs win here; docs/API.md lists every conflict and docs/HARDWARE-VERIFICATION.md
tells you how to settle it on a real controller.
"""

from __future__ import annotations

from enum import IntEnum

DEFAULT_PORT = 8001
DEFAULT_TIMEOUT = 5.0

# The envelope's success code. The manual says 0; one live example shows 200 with
# message "Success". Accept both.
SUCCESS_CODES = frozenset({0, 200})


class DisplayMode(IntEnum):
    """WRITE-side display mode (PUT .../displaymode ``value``)."""

    NORMAL = 0
    BLACKOUT = 1
    FREEZE = 2


# READ-side mapping for GET /api/v1/screen/output/display/state ``displayState[].displayMode``.
# The live doc claims 0 normal, 1 frozen, 2 blackout; an MX40 Pro (2026-09-03) reports the
# SAME values it was written with (1 blackout, 2 freeze). Verified on hardware; the doc is wrong.
DISPLAY_STATE_MODES: dict[int, DisplayMode] = {
    0: DisplayMode.NORMAL,
    1: DisplayMode.BLACKOUT,
    2: DisplayMode.FREEZE,
}


class WorkingMode(IntEnum):
    """Per-screen working mode, as ``PUT /api/v1/screen/mode`` takes it and as
    ``GET /api/v1/screen`` reports it (verified on an MX40 Pro, 2026-09-03).

    The 2023 manual's ``PUT /api/v1/device/hw/mode`` (2/3) is the controller-level device
    mode; on the MX40 Pro it reads back 3 and does not switch a screen.
    """

    SEND_ONLY = 0  # "Send-Only Controller": raw pass-through, no scaler (HDMI must match)
    ALL_IN_ONE = 1  # "All-In-One Controller": video processor / scaler engaged


WORKING_MODE_FROM_SCREEN: dict[int, WorkingMode] = {
    0: WorkingMode.SEND_ONLY,
    1: WorkingMode.ALL_IN_ONE,
    2: WorkingMode.SEND_ONLY,  # manual-era firmware scale
    3: WorkingMode.ALL_IN_ONE,
}


def working_mode_from_screen(value: int | None) -> WorkingMode | None:
    if value is None:
        return None
    return WORKING_MODE_FROM_SCREEN.get(int(value))


class HdrMode(IntEnum):
    """Per-input HDR override (PUT /api/v1/device/input/{id}/hdrmode ``hdrMode``)."""

    HDR10 = 0
    HLG = 1
    SDR = 2
    DCI = 3  # appears in read-side hdrList only; the setter rejects it
    AUTO = 255


HDR_MODE_SETTABLE = frozenset({HdrMode.HDR10, HdrMode.HLG, HdrMode.SDR, HdrMode.AUTO})

# Input connector types reported by GET /api/v1/device/input/sources ``type``.
# 0x00-0x0A, 0x10-0x14, 0xE0, 0xFF are from the 2023 manual; 11-13 are from the live doc,
# which numbers the newer connectors differently. They do not overlap, so both are kept.
INPUT_TYPES: dict[int, str] = {
    0x00: "DVI",
    0x01: "DualDVI",
    0x02: "HDMI1.4",
    0x03: "HDMI2.0",
    0x04: "DP1.1",
    0x05: "DP1.2",
    0x06: "DP1.4",
    0x07: "SDI_3G",
    0x08: "SDI_6G",
    0x09: "SDI_12G",
    0x0A: "PIPVideo",
    0x0B: "HDMI1.2",
    0x0C: "HDMI2.1",
    0x0D: "InternalSource",
    0x10: "HDMI1.3",
    0x11: "HDMI2.1",
    0x12: "PCIE",
    0x13: "Serdes",
    0x14: "LVDS",
    0xE0: "InternalSource",
    0xFF: "NoInputType",
}

# Global response codes from the COEX Series Interface API manual, section 1.5.1.
ERROR_CODES: dict[int, str] = {
    0: "Success",
    1: "InvalidParam",
    2: "SendFailed",
    3: "InternalErr",
    4: "AnalysisFailed",
    5: "Busying",
    6: "NotSupport",
    7: "LengthError",
    8: "SerializeError",
    9: "NoSupportIrModule",
    10: "OpenFileFailed",
    11: "CloseFileFailed",
    12: "ReadError",
    13: "CreateDirFailed",
    14: "ReadFileFailed",
    15: "DecodeFailed",
    16: "EncodeFailed",
    17: "WriteFileFailed",
    18: "RequestTimeout",
    19: "ResponseErr",
    20: "DBOperErr",
    21: "RvCardSoftSpaceHeaderInvalid",
    22: "TagNotMatch",
    23: "UnknownSubBoardType",
    24: "FindComponentObjErr",
    25: "InterfaceConvertErr",
    26: "SerializeDataFailed",
    27: "FunctionalRestrictions",
    28: "InvalidPointer",
    29: "LowDelayFunctionalRestrictions",
    30: "ThreadDFunctionalRestrictions",
    31: "GenLockFunctionalRestrictions",
    32: "AdditionFrameDelayFunctionalRestrictions",
    33: "MultiplierFunctionalRestrictions",
    34: "ScreenYPosIsNotEqualForOpenLowDelay",
    35: "NoScreenLayoutInfo",
    36: "NotImplement",
    37: "PresetNameRepeatError",
    38: "MemoryNotEnough",
    39: "CfgFileNotExist",
    41: "NonStandardFileName",
}

# ---------------------------------------------------------------------------
# Endpoint paths (live api.coex.novastar.tech docs unless marked legacy).
# ---------------------------------------------------------------------------
EP_SCREENS = "/api/v1/screen"
EP_SCREEN_BASE_INFO = "/api/v1/screen/base/info"
EP_SCREEN_OUTPUT = "/api/v1/screen/output"
EP_DISPLAY_MODE = "/api/v1/screen/output/displaymode"  # {value, screenIdList}
EP_DISPLAY_MODE_CANVAS = "/api/v1/device/displaymode"  # {value, canvasIDs}
EP_DISPLAY_STATE = "/api/v1/screen/output/display/state"
EP_DISPLAY_PARAMS = "/api/v1/screen/displayparams"
EP_BRIGHTNESS = "/api/v1/screen/brightness"  # {brightness 0..1, screenIdList}
EP_COLOR_TEMPERATURE = "/api/v1/screen/colortemperature"  # {colorTemperature, screenIdList}
EP_GAMMA = "/api/v1/screen/gamma"  # {gamma, screenIdList}
EP_LAYER_INPUT = "/api/v1/screen/layer/input"  # {screenID, layers:[{id, source}]}
EP_PRESETS = "/api/v1/preset"
EP_PRESET_APPLY = "/api/v1/preset/current/update"  # POST {screenID, sequenceNumber}
EP_INPUT_SOURCES = "/api/v1/device/input/sources"
EP_INPUT_HDR_MODE = "/api/v1/device/input/{id}/hdrmode"
EP_MONITOR_INFO = "/api/v1/device/monitor/info"
EP_CABINETS = "/api/v1/device/cabinet"
EP_CABINET_MAPPING = "/api/v1/device/cabinet/mapping"  # {idList, enable}
EP_CABINET_BRIGHTNESS = "/api/v1/device/cabinet/brightness"  # {idList, ratio 0..1}
EP_DEVICE_IDENTIFY = "/api/v1/device/hw/mapping"  # {enable} — controller, not cabinets
EP_CONTROLLER_BEACON = "/api/v1/device/hw/colorBeacon"  # POST {enable, color{r,g,b}}
EP_CONTROLLER_NAME = "/api/v1/device/hw/customname"
EP_SCREEN_WORKING_MODE = "/api/v1/screen/mode"  # {screenID, workingMode: 0|1} (verified)
EP_DEVICE_MODE = (
    "/api/v1/device/hw/mode"  # manual §5.3 {mode: 2|3}; controller-level, no-op for screens
)

# Legacy (2023 manual) paths, kept for fallback experiments on old firmware.
LEGACY_EP_DISPLAY_MODE = "/api/v1/device/screen/displaymode"
LEGACY_EP_SCREEN_INPUT = "/api/v1/device/screen/input"  # {groupId}, send-only mode
LEGACY_EP_CURRENT_PRESET = "/api/v1/device/currentpreset"  # {sequenceNumber 1..50}
