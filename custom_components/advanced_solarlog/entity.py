"""Shared entity bases for the Advanced Solar-Log integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import AdvancedSolarLogCoordinator


class AdvancedSolarLogEntity(CoordinatorEntity[AdvancedSolarLogCoordinator]):
    """Base for entities that belong to the Solar-Log itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdvancedSolarLogCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._entry_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=coordinator.client.base_url,
        )


class AdvancedSolarLogInverterEntity(CoordinatorEntity[AdvancedSolarLogCoordinator]):
    """Base for entities of a single inverter behind the Solar-Log.

    Each inverter gets its own device so the dashboard can show them apart,
    linked to the Solar-Log as its parent.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AdvancedSolarLogCoordinator, index: int, name: str
    ) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._entry_id = entry.entry_id
        self._index = index
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_inverter_{index}")},
            name=name,
            manufacturer=MANUFACTURER,
            model="Inverter",
            via_device=(DOMAIN, entry.entry_id),
        )
