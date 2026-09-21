"""Schalter fuer Steckdosen und Automatikmodus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AdvancedSolarLogError
from .const import DOMAIN
from .coordinator import AdvancedSolarLogCoordinator
from .entity import AdvancedSolarLogSocketEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Je Steckdose einen Relais- und einen Automatik-Schalter anlegen."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    for socket in coordinator.data.shelly:
        device_id = socket.get("id")
        if not device_id:
            continue
        name = socket.get("name") or device_id
        entities.append(AdvancedSolarLogRelay(coordinator, "shelly", device_id, name))
        entities.append(AdvancedSolarLogAutoMode(coordinator, "shelly", device_id, name))

    for socket in coordinator.data.ext:
        name = socket.get("name")
        if not name:
            continue
        entities.append(AdvancedSolarLogRelay(coordinator, "ext", name, name))
        entities.append(AdvancedSolarLogAutoMode(coordinator, "ext", name, name))

    async_add_entities(entities)


class _AdvancedSolarLogSwitchBase(AdvancedSolarLogSocketEntity, SwitchEntity):
    """Gemeinsame Befehlslogik fuer beide Schaltertypen."""

    async def _async_send(self, command: str) -> None:
        """Befehl mit frisch aufgeloestem Slot-Index senden.

        Slot-Indizes verschieben sich beim Hinzufuegen/Entfernen von Geraeten,
        deshalb wird der Index unmittelbar vor jedem Befehl neu gelesen.
        """
        socket = self._socket
        if socket is None:
            raise HomeAssistantError(
                f"{self._key} ist auf dem Geraet nicht mehr konfiguriert"
            )
        index = socket.get("idx")
        if index is None:
            raise HomeAssistantError(f"{self._key} hat keinen Slot-Index")
        try:
            await self.coordinator.client.async_switch_command(
                self._kind, int(index), command
            )
        except AdvancedSolarLogError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class AdvancedSolarLogRelay(_AdvancedSolarLogSwitchBase):
    """Manuelles Ein-/Ausschalten einer Steckdose."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        kind: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, kind, key, name)
        self._attr_unique_id = f"{self._entry_id}_{kind}_{key}_relay"

    @property
    def is_on(self) -> bool | None:
        """True, wenn das Relais an ist."""
        socket = self._socket
        return None if socket is None else socket.get("on")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Zusatzinfos, die auf dem Dashboard nuetzlich sind."""
        socket = self._socket
        if socket is None:
            return None
        attributes = {
            "auto": socket.get("auto"),
            "priority": socket.get("pri"),
            "rated_power_w": socket.get("pw"),
            "forced_by_bad_weather": socket.get("forced"),
            "daily_limit_reached": socket.get("cap"),
            "window_open": socket.get("win"),
            "schedule_active": socket.get("sch"),
        }
        override = socket.get("ov")
        if override:
            attributes["override_remaining_s"] = override
        lock = socket.get("lock")
        if lock:
            attributes["min_on_off_lock_s"] = lock
        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Steckdose manuell einschalten."""
        await self._async_send("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Steckdose manuell ausschalten."""
        await self._async_send("off")


class AdvancedSolarLogAutoMode(_AdvancedSolarLogSwitchBase):
    """Automatik (Ueberschusssteuerung) je Steckdose."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "socket_auto"

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        kind: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, kind, key, name)
        self._attr_unique_id = f"{self._entry_id}_{kind}_{key}_auto"

    @property
    def is_on(self) -> bool | None:
        """True, wenn die Automatik aktiv ist."""
        socket = self._socket
        return None if socket is None else socket.get("auto")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Automatik einschalten."""
        await self._async_send("autoon")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Automatik ausschalten."""
        await self._async_send("autooff")
