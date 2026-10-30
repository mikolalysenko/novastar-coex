"""Sensors: controller temperature, runtime and cabinet count."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoexConfigEntry
from .coordinator import CoexCoordinator
from .entity import CoexEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: CoexConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CoexTemperature(coordinator),
            CoexRuntime(coordinator),
            CoexCabinetCount(coordinator),
        ]
    )


class CoexTemperature(CoexEntity, SensorEntity):
    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoexCoordinator) -> None:
        super().__init__(coordinator, "temperature")

    @property
    def native_value(self) -> float | None:
        m = self.coordinator.data.monitor
        return m.max_temperature if m else None


class CoexRuntime(CoexEntity, SensorEntity):
    _attr_translation_key = "runtime"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoexCoordinator) -> None:
        super().__init__(coordinator, "runtime")

    @property
    def native_value(self) -> int | None:
        m = self.coordinator.data.monitor
        return m.runtime if m else None


class CoexCabinetCount(CoexEntity, SensorEntity):
    _attr_translation_key = "cabinets"
    _attr_icon = "mdi:view-grid"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoexCoordinator) -> None:
        super().__init__(coordinator, "cabinets")

    @property
    def native_value(self) -> int | None:
        m = self.coordinator.data.monitor
        return m.cabinet_count if m else None
