"""Diagnosedaten fuer einen Config-Entry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AdvancedSolarLogCoordinator

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Rohdaten des letzten Polls ausgeben."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        # Die Leserouten enthalten laut API-Doku nie Passwoerter oder Secrets,
        # nur Vorhanden-Flags - daher koennen sie unveraendert mit.
        "status": data.status,
        "sysinfo": data.sysinfo,
        "alarms": data.alarms,
    }
