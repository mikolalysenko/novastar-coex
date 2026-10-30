"""NovaStar COEX LED controller integration (MX40 Pro and friends)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coex import DEFAULT_PORT, CoexClient
from .const import PLATFORMS
from .coordinator import CoexCoordinator

type CoexConfigEntry = ConfigEntry[CoexCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CoexConfigEntry) -> bool:
    client = CoexClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        session=async_get_clientsession(hass),
    )
    coordinator = CoexCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoexConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
