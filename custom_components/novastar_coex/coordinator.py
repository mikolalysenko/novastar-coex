"""Polling coordinator: one aggregated read of the controller per interval."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .coex import CoexClient, CoexDeviceLocked, CoexError, CoexStatus, MonitorInfo
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MONITOR_EVERY_N_POLLS

_LOGGER = logging.getLogger(__name__)


class CoexCoordinator(DataUpdateCoordinator[CoexStatus]):
    """Fetches :class:`CoexStatus` on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: CoexClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._poll = 0
        self._last_monitor: MonitorInfo | None = None

    async def _async_update_data(self) -> CoexStatus:
        include_monitor = self._poll % MONITOR_EVERY_N_POLLS == 0 or self._last_monitor is None
        try:
            status = await self.client.get_status(include_monitor=include_monitor)
        except CoexDeviceLocked as err:
            raise UpdateFailed(
                "Controller is locked by VMP on another machine; close VMP to release it"
            ) from err
        except CoexError as err:
            raise UpdateFailed(f"Controller error: {err}") from err
        except (ValueError, TypeError, KeyError) as err:  # defensive: parser surprises
            raise UpdateFailed(f"Could not parse controller reply: {err}") from err
        self._poll += 1
        if include_monitor:
            self._last_monitor = status.monitor
        else:
            status.monitor = self._last_monitor
        return status

    async def async_write(self, coro: Awaitable[object]) -> None:
        """Run a write, surface failures as HomeAssistantError, then refresh."""
        try:
            await coro
        except CoexDeviceLocked as err:
            raise HomeAssistantError(
                "The controller is locked by VMP on another computer; close VMP first"
            ) from err
        except (CoexError, ValueError) as err:
            raise HomeAssistantError(f"Controller rejected the command: {err}") from err
        await self.async_request_refresh()
