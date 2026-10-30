"""Switches: Display (normal vs blackout), Freeze, and cabinet mapping, per screen."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoexConfigEntry
from .coex import DisplayMode, Screen
from .coordinator import CoexCoordinator
from .entity import CoexScreenEntity, screens_with_ids


async def async_setup_entry(
    hass: HomeAssistant, entry: CoexConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for screen in screens_with_ids(coordinator):
        entities.append(CoexDisplaySwitch(coordinator, screen))
        entities.append(CoexFreezeSwitch(coordinator, screen))
        entities.append(CoexMappingSwitch(coordinator, screen))
    async_add_entities(entities)


class CoexDisplaySwitch(CoexScreenEntity, SwitchEntity):
    """On = normal output, Off = blackout; controller and cabinets remain powered."""

    _attr_translation_key = "display"
    _attr_icon = "mdi:television"

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "display")

    @property
    def is_on(self) -> bool | None:
        out = self.output
        if out is None or out.display_mode is None:
            return None
        return out.display_mode != DisplayMode.BLACKOUT

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.normal([self.screen_id]))

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.blackout([self.screen_id]))


class CoexFreezeSwitch(CoexScreenEntity, SwitchEntity):
    """On = frame frozen, Off = normal output."""

    _attr_translation_key = "freeze"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "freeze")

    @property
    def is_on(self) -> bool | None:
        out = self.output
        if out is None or out.display_mode is None:
            return None
        return out.display_mode == DisplayMode.FREEZE

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.freeze([self.screen_id]))

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.normal([self.screen_id]))


class CoexMappingSwitch(CoexScreenEntity, SwitchEntity):
    """Paint cabinet numbers on the wall (for calibration / service days)."""

    _attr_translation_key = "mapping"
    _attr_icon = "mdi:map-marker-radius"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "mapping")

    @property
    def is_on(self) -> bool | None:
        out = self.output
        return out.mapping_enabled if out else None

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.set_cabinet_mapping(True))

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        await self.coordinator.async_write(self.coordinator.client.set_cabinet_mapping(False))
