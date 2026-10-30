"""Base entities: tie every platform entity to the controller device."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from yarl import URL

from .coex import Screen, ScreenOutput
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import CoexCoordinator


class CoexEntity(CoordinatorEntity[CoexCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: CoexCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="NovaStar",
            model="COEX controller",
            name=entry.data.get(CONF_NAME) or entry.title or DEFAULT_NAME,
            configuration_url=str(URL.build(scheme="http", host=coordinator.client.host)),
        )


class CoexScreenEntity(CoexEntity):
    """An entity scoped to one logical screen on the controller.

    With one screen the entity keeps its translated name ("Brightness"); with several
    the screen name is prefixed so they stay distinguishable.
    """

    _base_translation_key: str = ""

    def __init__(self, coordinator: CoexCoordinator, screen: Screen, key: str) -> None:
        super().__init__(coordinator, f"screen_{screen.screen_id}_{key}")
        self.screen_id = screen.screen_id
        self._screen_name = screen.name
        if len(coordinator.data.screens) > 1:
            self._attr_translation_key = None
            self._attr_name = f"{screen.name} {key.replace('_', ' ').title()}"

    @property
    def screen(self) -> Screen | None:
        return self.coordinator.data.screen(self.screen_id)

    @property
    def output(self) -> ScreenOutput | None:
        return self.coordinator.data.output_for(self.screen_id)

    @property
    def available(self) -> bool:
        return super().available and self.screen is not None


def screens_with_ids(coordinator: CoexCoordinator) -> list[Screen]:
    """Screens that can back entities (skips any without a usable id)."""
    return [s for s in coordinator.data.screens if s.screen_id]
