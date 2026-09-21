"""Diagnostics download for one config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .api import AdvancedSolarLogError
from .const import DOMAIN
from .coordinator import AdvancedSolarLogCoordinator

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Dump the last poll, including the raw Solar-Log field numbers.

    The raw block is the fastest way to tell which values a given firmware
    actually reports, so it goes in unchanged -- it contains measurements only.
    """
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    # A fresh login attempt, so the report shows what the device answers right
    # now rather than what it answered at startup. It reads only: a login is
    # what the integration does anyway on every poll that needs it.
    login_error: str | None = None
    if coordinator.client.password:
        try:
            await coordinator.client.async_login()
        except AdvancedSolarLogError as err:
            login_error = str(err)

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "extended_data": coordinator.extended_data,
        "login": {**coordinator.client.login_report(), "error": login_error},
        "raw_801_170": data.values,
        "battery": data.battery,
        "energy": data.energy,
        "inverters": {
            index: {
                "name": inverter.name,
                "power": inverter.power,
                "yield_year": inverter.yield_year,
            }
            for index, inverter in data.inverters.items()
        },
    }
