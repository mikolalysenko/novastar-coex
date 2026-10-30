"""Numbers: brightness (percent), colour temperature (K) and gamma, per screen."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoexConfigEntry
from .coex import Screen
from .coordinator import CoexCoordinator
from .entity import CoexScreenEntity, screens_with_ids


async def async_setup_entry(
    hass: HomeAssistant, entry: CoexConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []
    for screen in screens_with_ids(coordinator):
        entities.append(CoexBrightness(coordinator, screen))
        entities.append(CoexColorTemperature(coordinator, screen))
        entities.append(CoexGamma(coordinator, screen))
    async_add_entities(entities)


class CoexBrightness(CoexScreenEntity, NumberEntity):
    _attr_translation_key = "brightness"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "brightness")

    @property
    def native_value(self) -> float | None:
        out = self.output
        return round(out.brightness_pct, 1) if out and out.brightness_pct is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"wire_scale": self.coordinator.data.brightness_scale}

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(
            self.coordinator.client.set_brightness(value, [self.screen_id])
        )


class CoexColorTemperature(CoexScreenEntity, NumberEntity):
    _attr_translation_key = "color_temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_min_value = 1700
    _attr_native_max_value = 15000
    _attr_native_step = 100
    _attr_native_unit_of_measurement = UnitOfTemperature.KELVIN
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "color_temperature")

    @property
    def native_value(self) -> float | None:
        out = self.output
        return out.color_temperature if out else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(
            self.coordinator.client.set_color_temperature(int(value), [self.screen_id])
        )


class CoexGamma(CoexScreenEntity, NumberEntity):
    _attr_translation_key = "gamma"
    _attr_icon = "mdi:gradient-vertical"
    _attr_native_min_value = 1.0
    _attr_native_max_value = 4.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: CoexCoordinator, screen: Screen) -> None:
        super().__init__(coordinator, screen, "gamma")

    @property
    def native_value(self) -> float | None:
        out = self.output
        return out.gamma if out else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(
            self.coordinator.client.set_gamma(float(value), [self.screen_id])
        )
