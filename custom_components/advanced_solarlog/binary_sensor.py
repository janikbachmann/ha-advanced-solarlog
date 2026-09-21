"""Binaere Zustaende des EnergyOptimizer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AdvancedSolarLogCoordinator, AdvancedSolarLogData
from .entity import AdvancedSolarLogEntity


@dataclass(frozen=True, kw_only=True)
class EOBinarySensorDescription(BinarySensorEntityDescription):
    """Binaersensor mit Zugriffsfunktion."""

    value_fn: Callable[[AdvancedSolarLogData], bool | None]


BINARY_SENSORS: tuple[EOBinarySensorDescription, ...] = (
    EOBinarySensorDescription(
        key="failsafe",
        translation_key="failsafe",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.status.get("failsafe"),
    ),
    EOBinarySensorDescription(
        key="battblk",
        translation_key="battery_priority_blocking",
        value_fn=lambda data: data.status.get("battblk"),
    ),
    EOBinarySensorDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data.status.get("al_n")),
    ),
    EOBinarySensorDescription(
        key="mqtt",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (data.status.get("mqtt") or {}).get("conn"),
    ),
    EOBinarySensorDescription(
        key="eth",
        translation_key="ethernet",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.sysinfo.get("eth"),
    ),
    EOBinarySensorDescription(
        key="nvs_err",
        translation_key="nvs_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.sysinfo.get("nvs_err"),
    ),
    EOBinarySensorDescription(
        key="coredump",
        translation_key="coredump",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.sysinfo.get("coredump"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binaersensoren anlegen."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AdvancedSolarLogBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class AdvancedSolarLogBinarySensor(AdvancedSolarLogEntity, BinarySensorEntity):
    """Ein boolesches Feld aus /api/status oder /api/sysinfo."""

    entity_description: EOBinarySensorDescription

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        description: EOBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Aktueller Zustand."""
        return self.entity_description.value_fn(self.coordinator.data)
