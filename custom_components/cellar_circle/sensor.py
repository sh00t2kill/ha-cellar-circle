"""Sensors for Cellar Circle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BASE_URL, DOMAIN, MAX_ITEMS_IN_ATTRIBUTES
from .coordinator import CellarCircleConfigEntry, CellarCircleCoordinator
from .parse import Summary


@dataclass(frozen=True, kw_only=True)
class CellarCircleSensorDescription(SensorEntityDescription):
    value: Callable[[Summary], int | float]
    attributes: Callable[[Summary], dict[str, Any]] | None = None


def _people(field: str) -> Callable[[Summary], dict[str, Any]]:
    return lambda s: {"people": [{"name": p["name"], "bottles": p[field]} for p in s.people if p[field]]}


SENSORS: tuple[CellarCircleSensorDescription, ...] = (
    CellarCircleSensorDescription(
        key="open_items",
        translation_key="open_items",
        icon="mdi:clipboard-list-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.open_items_total,
        attributes=lambda s: {"items": s.open_items[:MAX_ITEMS_IN_ATTRIBUTES]},
    ),
    CellarCircleSensorDescription(
        key="bottles_i_owe",
        translation_key="bottles_i_owe",
        icon="mdi:bottle-wine-outline",
        native_unit_of_measurement="bottles",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.bottles_i_owe,
        attributes=_people("bottles_i_owe"),
    ),
    CellarCircleSensorDescription(
        key="bottles_owed_to_me",
        translation_key="bottles_owed_to_me",
        icon="mdi:bottle-wine",
        native_unit_of_measurement="bottles",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.bottles_owed_to_me,
        attributes=_people("bottles_owed_to_me"),
    ),
    CellarCircleSensorDescription(
        key="money_i_owe",
        translation_key="money_i_owe",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value=lambda s: s.money_i_owe_cents / 100,
    ),
    CellarCircleSensorDescription(
        key="money_owed_to_me",
        translation_key="money_owed_to_me",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value=lambda s: s.money_owed_to_me_cents / 100,
    ),
    CellarCircleSensorDescription(
        key="open_swaps",
        translation_key="open_swaps",
        icon="mdi:swap-horizontal",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.open_swaps_total,
        attributes=lambda s: {"listings": s.open_swaps[:MAX_ITEMS_IN_ATTRIBUTES]},
    ),
    CellarCircleSensorDescription(
        key="my_swaps",
        translation_key="my_swaps",
        icon="mdi:swap-horizontal-bold",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.my_swaps_total,
        attributes=lambda s: {"listings": s.my_swaps[:MAX_ITEMS_IN_ATTRIBUTES]},
    ),
    CellarCircleSensorDescription(
        key="open_offers",
        translation_key="open_offers",
        icon="mdi:cart-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.open_offers_total,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: CellarCircleConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(CellarCircleSensor(coordinator, entry, description) for description in SENSORS)


class CellarCircleSensor(CoordinatorEntity[CellarCircleCoordinator], SensorEntity):
    entity_description: CellarCircleSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: CellarCircleCoordinator, entry: CellarCircleConfigEntry, description: CellarCircleSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Cellar Circle",
            manufacturer="Cellar Circle",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_BASE_URL],
        )

    @property
    def native_value(self) -> int | float:
        return self.entity_description.value(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.device_class == SensorDeviceClass.MONETARY:
            return self.coordinator.data.currency
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes = self.entity_description.attributes
        return attributes(self.coordinator.data) if attributes else None
