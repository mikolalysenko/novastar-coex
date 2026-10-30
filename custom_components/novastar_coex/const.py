"""Constants for the NovaStar COEX integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "novastar_coex"
DEFAULT_NAME = "Video Wall"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)
MONITOR_EVERY_N_POLLS = 6  # temperatures/fans change slowly; poll them once a minute

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

WORKING_MODE_OPTIONS = {"send_only": "Send-Only", "all_in_one": "All-in-One"}
