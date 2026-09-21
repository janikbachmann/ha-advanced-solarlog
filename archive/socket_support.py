"""Steckdosen-Bausteine - gehoeren zu den archivierten Schalt-Plattformen.

Diese Datei wird von Home Assistant nicht geladen. Sie haelt den Code, den
`archive/switch.py` braucht: die Entity-Basis fuer ein einzelnes Steckdosen-
Geraet und die Zugriffsfunktionen auf die Steckdosen-Arrays aus /api/status.
Beim Reaktivieren gehoert die Klasse zurueck nach `entity.py` und die
Properties zurueck in `AdvancedSolarLogData` in `coordinator.py`.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AdvancedSolarLogCoordinator


# --- gehoert nach coordinator.py, in die Klasse AdvancedSolarLogData ---

#     @property
#     def shelly(self) -> list[dict[str, Any]]:
#         """Live-Zustand je Shelly-Steckdose."""
#         return self.status.get("shelly") or []
#
#     @property
#     def ext(self) -> list[dict[str, Any]]:
#         """Live-Zustand je generischem MQTT-Ext-Switch."""
#         return self.status.get("ext") or []
#
#     def shelly_by_id(self, device_id: str) -> dict[str, Any] | None:
#         """Steckdose ueber ihre stabile Shelly-ID finden.
#
#         Slot-Indizes verschieben sich, wenn Geraete hinzugefuegt oder entfernt
#         werden - stabil ist nur `shelly[].id`.
#         """
#         for entry in self.shelly:
#             if entry.get("id") == device_id:
#                 return entry
#         return None
#
#     def ext_by_name(self, name: str) -> dict[str, Any] | None:
#         """Ext-Switch ueber seinen Namen finden (eine ID gibt es dort nicht)."""
#         for entry in self.ext:
#             if entry.get("name") == name:
#                 return entry
#         return None


# --- gehoert nach entity.py ---

class AdvancedSolarLogSocketEntity(CoordinatorEntity[AdvancedSolarLogCoordinator]):
    """Basis fuer Entities einer einzelnen Steckdose (eigenes Sub-Geraet)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        kind: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._entry_id = entry.entry_id
        self._kind = kind
        self._key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{kind}_{key}")},
            name=name,
            manufacturer=MANUFACTURER,
            model="Shelly" if kind == "shelly" else "MQTT-Schalter",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _socket(self) -> dict | None:
        """Aktueller Live-Eintrag dieser Steckdose, oder None wenn verschwunden."""
        data = self.coordinator.data
        if data is None:
            return None
        if self._kind == "shelly":
            return data.shelly_by_id(self._key)
        return data.ext_by_name(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._socket is not None
