"""DataUpdateCoordinator fuer den EnergyOptimizer."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AdvancedSolarLogAuthError, AdvancedSolarLogClient, AdvancedSolarLogError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdvancedSolarLogData:
    """Ein Satz zusammengehoeriger Antworten eines Poll-Durchlaufs."""

    status: dict[str, Any] = field(default_factory=dict)
    sysinfo: dict[str, Any] = field(default_factory=dict)
    alarms: dict[str, Any] = field(default_factory=dict)

    @property
    def energy(self) -> dict[str, Any]:
        """Das `energy`-Unterobjekt von /api/status."""
        return self.status.get("energy") or {}

    @property
    def cost(self) -> dict[str, Any]:
        """Das `cost`-Unterobjekt - fehlt, wenn kein Preis konfiguriert ist."""
        return self.status.get("cost") or {}


AdvancedSolarLogConfigEntry = ConfigEntry


class AdvancedSolarLogCoordinator(DataUpdateCoordinator[AdvancedSolarLogData]):
    """Pollt /api/status, /api/sysinfo und /api/alarms in einem Durchlauf."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AdvancedSolarLogClient,
        poll_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client

    async def _async_update_data(self) -> AdvancedSolarLogData:
        try:
            status = await self.client.async_get_status()
            sysinfo = await self.client.async_get_sysinfo()
            alarms = await self.client.async_get_alarms()
        except AdvancedSolarLogAuthError as err:
            # Einheitliches 401 {"ok":false,"auth":false} auf allen Routen.
            raise ConfigEntryAuthFailed(str(err)) from err
        except AdvancedSolarLogError as err:
            raise UpdateFailed(str(err)) from err

        return AdvancedSolarLogData(status=status, sysinfo=sysinfo, alarms=alarms)
