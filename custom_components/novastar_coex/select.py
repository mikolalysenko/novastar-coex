"""Selects: working mode, preset and input source, per screen."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoexConfigEntry
from .coex import Screen, WorkingMode
from .const import WORKING_MODE_OPTIONS
from .coordinator import CoexCoordinator
from .entity import CoexScreenEntity, screens_with_ids


async def async_setup_entry(
    hass: HomeAssistant, entry: CoexConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = []
    for screen in screens_with_ids(coordinator):
        entities.append(CoexWorkingModeSelect(coordinator, screen))
        entities.append(CoexPresetSelect(coordinator, screen))
        entities.append(CoexInputSelect(coordinator, screen))
    async_add_entities(entities)


class CoexWorkingModeSelect(CoexScreenEntity, SelectEntity):
    """Send-Only (raw pass-through, HDMI must match the wall) vs All-in-One (scaler)."""

    _attr_translation_key = "working_mode"
    _attr_icon = "mdi:video-switch"
    _attr_options = list(WORKING_MODE_OPTIONS.values())

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "working_mode")

    @property
    def current_option(self) -> str | None:
        screen = self.screen
        if screen is None or screen.working_mode is None:
            return None
        return (
            WORKING_MODE_OPTIONS["send_only"]
            if screen.working_mode is WorkingMode.SEND_ONLY
            else WORKING_MODE_OPTIONS["all_in_one"]
        )

    async def async_select_option(self, option: str) -> None:
        mode = (
            WorkingMode.SEND_ONLY
            if option == WORKING_MODE_OPTIONS["send_only"]
            else WorkingMode.ALL_IN_ONE
        )
        await self.coordinator.async_write(
            self.coordinator.client.set_working_mode(mode, self.screen_id)
        )


class CoexPresetSelect(CoexScreenEntity, SelectEntity):
    _attr_translation_key = "preset"
    _attr_icon = "mdi:playlist-star"

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "preset")

    @property
    def options(self) -> list[str]:
        return [p.label for p in self.coordinator.data.presets_for(self.screen_id)]

    @property
    def current_option(self) -> str | None:
        p = self.coordinator.data.active_preset(self.screen_id)
        return p.label if p else None

    async def async_select_option(self, option: str) -> None:
        match = next(
            (p for p in self.coordinator.data.presets_for(self.screen_id) if p.label == option),
            None,
        )
        if match is None:
            raise ValueError(f"unknown preset {option!r}")
        await self.coordinator.async_write(
            self.coordinator.client.apply_preset(match.sequence_number, self.screen_id)
        )


class CoexInputSelect(CoexScreenEntity, SelectEntity):
    """Route an input source group to the screen's main layer.

    The current value is read from the screen's layer list (``layersInWorkingMode``),
    so it survives restarts and reflects changes made from VMP.
    """

    _attr_translation_key = "input"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "input")

    @property
    def options(self) -> list[str]:
        return [s.name for s in self.coordinator.data.sources if s.name and s.group_id is not None]

    @property
    def current_option(self) -> str | None:
        screen = self.screen
        if screen is None:
            return None
        src = self.coordinator.data.source_by_group(screen.current_source_group)
        return src.name if src and src.name in self.options else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(
            self.coordinator.client.select_input(option, self.screen_id)
        )
