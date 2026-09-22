"""Polls the Solar-Log device and hands one consistent snapshot to the entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AdvancedSolarLogAuthError,
    AdvancedSolarLogClient,
    AdvancedSolarLogError,
    parse_timestamp,
)
from .const import (
    DOMAIN,
    FIELD_CONSUMPTION_AC,
    FIELD_CONSUMPTION_YEAR,
    FIELD_LAST_UPDATED,
    FIELD_POWER_AC,
    FIELD_POWER_DC,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class InverterData:
    """One inverter behind the Solar-Log."""

    name: str
    power: float | None = None
    yield_year: float | None = None


@dataclass(slots=True)
class AdvancedSolarLogData:
    """Everything one poll produced."""

    # Raw 801/170 block, keyed by Solar-Log's field numbers.
    values: dict[str, Any] = field(default_factory=dict)
    battery: dict[str, float] | None = None
    energy: dict[str, float] | None = None
    inverters: dict[int, InverterData] = field(default_factory=dict)
    last_updated: datetime | None = None

    def number(self, field_number: str) -> float | None:
        """Read one field of the main block as a number."""
        value = self.values.get(field_number)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def grid_power(self) -> float | None:
        """Grid exchange in W: positive means import, negative means feed-in.

        Solar-Log reports production and consumption separately, so this is
        derived rather than measured.
        """
        production = self.number(FIELD_POWER_AC)
        consumption = self.number(FIELD_CONSUMPTION_AC)
        if production is None or consumption is None:
            return None
        return consumption - production

    @property
    def grid_import_year(self) -> float | None:
        """Energy drawn from the grid this year, in Wh.

        The Solar-Log has no meter at the grid connection, but it does report
        what the house used over the year and how much of the production was
        used on site. Whatever the house used beyond that had to come from the
        grid. Both numbers are the device's own yearly counters, so this is
        exact arithmetic rather than power integrated over time -- nothing
        drifts and nothing is lost across a restart.

        The two numbers come from different blocks of the device, so they can
        disagree by a rounding step; the result is clamped at zero, because a
        `total_increasing` sensor reads a negative value as a counter reset.
        """
        consumption = self.number(FIELD_CONSUMPTION_YEAR)
        if consumption is None or self.energy is None:
            return None
        return max(0.0, consumption - self.energy["self_consumption"])

    @property
    def grid_export_year(self) -> float | None:
        """Energy fed into the grid this year, in Wh.

        Production minus the part of it used in the house, both taken from the
        device's own yearly energy block. See `grid_import_year`.
        """
        if self.energy is None:
            return None
        return max(0.0, self.energy["production"] - self.energy["self_consumption"])

    @property
    def battery_power(self) -> float | None:
        """Battery power in W: positive means charging, negative discharging."""
        if self.battery is None:
            return None
        return self.battery["charge_power"] - self.battery["discharge_power"]

    @property
    def alternator_loss(self) -> float | None:
        """Difference between DC input and AC output of the inverters, in W."""
        power_dc = self.number(FIELD_POWER_DC)
        power_ac = self.number(FIELD_POWER_AC)
        if power_dc is None or power_ac is None:
            return None
        return power_dc - power_ac

    @property
    def efficiency(self) -> float | None:
        """Inverter efficiency in percent."""
        power_dc = self.number(FIELD_POWER_DC)
        power_ac = self.number(FIELD_POWER_AC)
        if not power_dc or power_ac is None:
            return None
        return power_ac / power_dc * 100


AdvancedSolarLogConfigEntry = ConfigEntry


class AdvancedSolarLogCoordinator(DataUpdateCoordinator[AdvancedSolarLogData]):
    """Fetches the main values every cycle, and the protected ones if available."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AdvancedSolarLogClient,
        poll_interval: int,
        extended_data: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.extended_data = extended_data
        self._inverter_names: dict[int, str] = {}

    async def _async_update_data(self) -> AdvancedSolarLogData:
        try:
            values = await self.client.async_get_basic_data()
            data = AdvancedSolarLogData(values=values)
            data.last_updated = _as_local(values.get(FIELD_LAST_UPDATED))

            if self.extended_data:
                await self._async_update_extended(data)
        except AdvancedSolarLogAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AdvancedSolarLogError as err:
            raise UpdateFailed(str(err)) from err

        return data

    async def _async_update_extended(self, data: AdvancedSolarLogData) -> None:
        """Add the values that need a session: battery, yearly totals, inverters.

        A failure here must not take the main values down with it, so anything
        other than an auth problem is logged and skipped.
        """
        try:
            data.battery = await self.client.async_get_battery()
            data.energy = await self.client.async_get_energy()

            if not self._inverter_names:
                self._inverter_names = await self.client.async_get_device_list()

            power = await self.client.async_get_inverter_power()
            energy = await self.client.async_get_inverter_energy()
            data.inverters = {
                index: InverterData(
                    name=name,
                    power=power.get(index),
                    yield_year=energy.get(index),
                )
                for index, name in self._inverter_names.items()
            }
        except AdvancedSolarLogAuthError:
            raise
        except AdvancedSolarLogError as err:
            _LOGGER.debug("Extended Solar-Log data unavailable this cycle: %s", err)


def _as_local(value: Any) -> datetime | None:
    """Solar-Log sends local time without a zone; attach Home Assistant's."""
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.replace(tzinfo=dt_util.get_default_time_zone())
