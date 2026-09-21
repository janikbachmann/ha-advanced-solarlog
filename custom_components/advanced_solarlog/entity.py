"""Gemeinsame Entity-Basis fuer den EnergyOptimizer."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import AdvancedSolarLogCoordinator


class AdvancedSolarLogEntity(CoordinatorEntity[AdvancedSolarLogCoordinator]):
    """Basis fuer alle Entities am Hauptgeraet."""

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
            sw_version=coordinator.data.sysinfo.get("build") if coordinator.data else None,
        )
