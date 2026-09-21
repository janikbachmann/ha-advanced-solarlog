"""Sensors for the values the Solar-Log reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FIELD_CONSUMPTION_AC,
    FIELD_CONSUMPTION_DAY,
    FIELD_CONSUMPTION_MONTH,
    FIELD_CONSUMPTION_TOTAL,
    FIELD_CONSUMPTION_YEAR,
    FIELD_CONSUMPTION_YESTERDAY,
    FIELD_POWER_AC,
    FIELD_POWER_DC,
    FIELD_TOTAL_POWER,
    FIELD_VOLTAGE_AC,
    FIELD_VOLTAGE_DC,
    FIELD_YIELD_DAY,
    FIELD_YIELD_MONTH,
    FIELD_YIELD_TOTAL,
    FIELD_YIELD_YEAR,
    FIELD_YIELD_YESTERDAY,
)
from .coordinator import AdvancedSolarLogCoordinator, AdvancedSolarLogData
from .entity import AdvancedSolarLogEntity, AdvancedSolarLogInverterEntity


@dataclass(frozen=True, kw_only=True)
class SolarLogSensorDescription(SensorEntityDescription):
    """Sensor description with the accessor for its value."""

    value_fn: Callable[[AdvancedSolarLogData], float | datetime | None]
    # Entities whose source is absent on this installation are never created.
    exists_fn: Callable[[AdvancedSolarLogData], bool] = lambda _: True


def _field(number: str) -> Callable[[AdvancedSolarLogData], float | None]:
    """Accessor for one field of the main 801/170 block."""
    return lambda data: data.number(number)


def _battery(key: str) -> Callable[[AdvancedSolarLogData], float | None]:
    """Accessor for one battery value."""
    return lambda data: None if data.battery is None else data.battery[key]


def _has_battery(data: AdvancedSolarLogData) -> bool:
    return data.battery is not None


POWER_SENSORS: tuple[SolarLogSensorDescription, ...] = (
    SolarLogSensorDescription(
        key="power_ac",
        translation_key="power_ac",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_field(FIELD_POWER_AC),
    ),
    SolarLogSensorDescription(
        key="power_dc",
        translation_key="power_dc",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_field(FIELD_POWER_DC),
    ),
    SolarLogSensorDescription(
        key="consumption_ac",
        translation_key="consumption_ac",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_field(FIELD_CONSUMPTION_AC),
    ),
    SolarLogSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.grid_power,
    ),
    SolarLogSensorDescription(
        key="voltage_ac",
        translation_key="voltage_ac",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_field(FIELD_VOLTAGE_AC),
    ),
    SolarLogSensorDescription(
        key="voltage_dc",
        translation_key="voltage_dc",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_field(FIELD_VOLTAGE_DC),
    ),
)

# The values the official integration leaves out on an unprotected setup, and
# the reason this integration exists.
BATTERY_SENSORS: tuple[SolarLogSensorDescription, ...] = (
    SolarLogSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery("level"),
        exists_fn=_has_battery,
    ),
    SolarLogSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_power,
        exists_fn=_has_battery,
    ),
    SolarLogSensorDescription(
        key="battery_charge_power",
        translation_key="battery_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery("charge_power"),
        exists_fn=_has_battery,
    ),
    SolarLogSensorDescription(
        key="battery_discharge_power",
        translation_key="battery_discharge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery("discharge_power"),
        exists_fn=_has_battery,
    ),
    SolarLogSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_battery("voltage"),
        exists_fn=_has_battery,
    ),
)

# Wh counters. `total_increasing` lets the Energy Dashboard use them directly
# and handles the reset at midnight / month / year on its own.
ENERGY_SENSORS: tuple[SolarLogSensorDescription, ...] = (
    SolarLogSensorDescription(
        key="yield_day",
        translation_key="yield_day",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_YIELD_DAY),
    ),
    SolarLogSensorDescription(
        key="yield_yesterday",
        translation_key="yield_yesterday",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=_field(FIELD_YIELD_YESTERDAY),
    ),
    SolarLogSensorDescription(
        key="yield_month",
        translation_key="yield_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_YIELD_MONTH),
    ),
    SolarLogSensorDescription(
        key="yield_year",
        translation_key="yield_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_YIELD_YEAR),
    ),
    SolarLogSensorDescription(
        key="yield_total",
        translation_key="yield_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_YIELD_TOTAL),
    ),
    SolarLogSensorDescription(
        key="consumption_day",
        translation_key="consumption_day",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_CONSUMPTION_DAY),
    ),
    SolarLogSensorDescription(
        key="consumption_yesterday",
        translation_key="consumption_yesterday",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=_field(FIELD_CONSUMPTION_YESTERDAY),
    ),
    SolarLogSensorDescription(
        key="consumption_month",
        translation_key="consumption_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_CONSUMPTION_MONTH),
    ),
    SolarLogSensorDescription(
        key="consumption_year",
        translation_key="consumption_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_CONSUMPTION_YEAR),
    ),
    SolarLogSensorDescription(
        key="consumption_total",
        translation_key="consumption_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_field(FIELD_CONSUMPTION_TOTAL),
    ),
    SolarLogSensorDescription(
        key="self_consumption_year",
        translation_key="self_consumption_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: None if data.energy is None else data.energy["self_consumption"],
        exists_fn=lambda data: data.energy is not None,
    ),
)

DIAGNOSTIC_SENSORS: tuple[SolarLogSensorDescription, ...] = (
    SolarLogSensorDescription(
        key="last_updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_updated,
    ),
    SolarLogSensorDescription(
        key="installed_power",
        translation_key="installed_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field(FIELD_TOTAL_POWER),
    ),
)

ALL_SENSORS: tuple[SolarLogSensorDescription, ...] = (
    POWER_SENSORS + BATTERY_SENSORS + ENERGY_SENSORS + DIAGNOSTIC_SENSORS
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors this installation actually has."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    entities: list[SensorEntity] = [
        AdvancedSolarLogSensor(coordinator, description)
        for description in ALL_SENSORS
        if description.exists_fn(data)
    ]

    for index, inverter in data.inverters.items():
        entities.append(
            AdvancedSolarLogInverterSensor(
                coordinator, index, inverter.name, INVERTER_POWER
            )
        )
        entities.append(
            AdvancedSolarLogInverterSensor(
                coordinator, index, inverter.name, INVERTER_YIELD_YEAR
            )
        )

    async_add_entities(entities)


class AdvancedSolarLogSensor(AdvancedSolarLogEntity, SensorEntity):
    """One value of the Solar-Log itself."""

    entity_description: SolarLogSensorDescription

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        description: SolarLogSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_id}_{description.key}"

    @property
    def native_value(self) -> float | datetime | None:
        """Current value."""
        return self.entity_description.value_fn(self.coordinator.data)


INVERTER_POWER = SensorEntityDescription(
    key="inverter_power",
    translation_key="inverter_power",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
)

INVERTER_YIELD_YEAR = SensorEntityDescription(
    key="inverter_yield_year",
    translation_key="inverter_yield_year",
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    state_class=SensorStateClass.TOTAL_INCREASING,
)


class AdvancedSolarLogInverterSensor(AdvancedSolarLogInverterEntity, SensorEntity):
    """One value of a single inverter behind the Solar-Log."""

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        index: int,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, index, name)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_id}_inverter_{index}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Current value, or None while the inverter is not reporting."""
        inverter = self.coordinator.data.inverters.get(self._index)
        if inverter is None:
            return None
        if self.entity_description.key == "inverter_power":
            return inverter.power
        return inverter.yield_year
