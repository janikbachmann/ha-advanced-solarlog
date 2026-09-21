"""Home Assistant integration for Solar-Log devices, read over their JSON interface."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdvancedSolarLogClient
from .const import (
    CONF_EXTENDED_DATA,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import AdvancedSolarLogCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one configured Solar-Log."""
    client = AdvancedSolarLogClient(
        async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        password=entry.data.get(CONF_PASSWORD),
    )

    extended_data = entry.options.get(
        CONF_EXTENDED_DATA, entry.data.get(CONF_EXTENDED_DATA, False)
    )
    if extended_data:
        # Battery, yearly totals and the per-inverter values sit behind the
        # device password; without a session they stay unavailable.
        await client.async_login()

    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    )

    coordinator = AdvancedSolarLogCoordinator(
        hass, entry, client, poll_interval, extended_data
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an option changed, e.g. the poll interval."""
    await hass.config_entries.async_reload(entry.entry_id)
