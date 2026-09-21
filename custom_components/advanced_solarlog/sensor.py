"""Sensoren des EnergyOptimizer (Solar-Log-Werte, Zaehler, Diagnose)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SEVERITY_NAMES
from .coordinator import AdvancedSolarLogCoordinator, AdvancedSolarLogData
from .entity import AdvancedSolarLogEntity


def _neg_one_is_none(value: Any) -> Any:
    """Die Firmware kodiert "noch nie passiert" als -1."""
    if value is None or value == -1:
        return None
    return value


@dataclass(frozen=True, kw_only=True)
class EOSensorDescription(SensorEntityDescription):
    """Sensorbeschreibung mit Zugriffsfunktion auf die Poll-Daten."""

    value_fn: Callable[[AdvancedSolarLogData], Any]
    exists_fn: Callable[[AdvancedSolarLogData], bool] = lambda _: True


def _status(key: str) -> Callable[[AdvancedSolarLogData], Any]:
    return lambda data: data.status.get(key)


def _energy(key: str) -> Callable[[AdvancedSolarLogData], Any]:
    return lambda data: data.energy.get(key)


def _sysinfo(key: str) -> Callable[[AdvancedSolarLogData], Any]:
    return lambda data: data.sysinfo.get(key)


def _cost(key: str) -> Callable[[AdvancedSolarLogData], Any]:
    # Die Firmware rechnet in Rappen; Home Assistant will eine Waehrungseinheit.
    def _value(data: AdvancedSolarLogData) -> Any:
        raw = data.cost.get(key)
        return None if raw is None else round(raw / 100, 4)

    return _value


POWER_SENSORS: tuple[EOSensorDescription, ...] = (
    EOSensorDescription(
        key="prod",
        translation_key="production",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_status("prod"),
    ),
    EOSensorDescription(
        key="cons",
        translation_key="consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_status("cons"),
    ),
    EOSensorDescription(
        key="grid",
        translation_key="grid_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_status("grid"),
    ),
    # Batterie: nur vorhanden, wenn die Anlage eine hat (sd.has_battery).
    EOSensorDescription(
        key="batt",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_status("batt"),
        exists_fn=lambda data: "batt" in data.status,
    ),
    EOSensorDescription(
        key="soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_status("soc"),
        exists_fn=lambda data: "soc" in data.status,
    ),
)

ENERGY_SENSORS: tuple[EOSensorDescription, ...] = tuple(
    EOSensorDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=_energy(key),
    )
    for key, translation_key in (
        ("dp", "production_today"),
        ("dc", "consumption_today"),
        ("dgi", "grid_import_today"),
        ("dgo", "grid_export_today"),
        ("tp", "production_total"),
        ("tc", "consumption_total"),
        ("tgi", "grid_import_total"),
        ("tgo", "grid_export_total"),
    )
)

COST_SENSORS: tuple[EOSensorDescription, ...] = tuple(
    EOSensorDescription(
        key=f"cost_{key}",
        translation_key=translation_key,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="CHF",
        suggested_display_precision=2,
        value_fn=_cost(key),
        exists_fn=lambda data: bool(data.cost),
    )
    for key, translation_key in (
        ("buy", "cost_import_today"),
        ("sell", "cost_export_today"),
        ("saved", "cost_saved_today"),
        ("base", "cost_base_today"),
    )
)

DIAGNOSTIC_SENSORS: tuple[EOSensorDescription, ...] = (
    EOSensorDescription(
        key="sl_age",
        translation_key="solarlog_age",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _neg_one_is_none(data.status.get("sl_age")),
    ),
    EOSensorDescription(
        key="sl_next",
        translation_key="solarlog_next",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _neg_one_is_none(data.status.get("sl_next")),
    ),
    EOSensorDescription(
        key="al_n",
        translation_key="active_alarms",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status("al_n"),
    ),
    EOSensorDescription(
        key="al_sev",
        translation_key="alarm_severity",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "info", "warn", "crit"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: SEVERITY_NAMES.get(data.status.get("al_sev"), "none")
        if data.status.get("al_n")
        else "none",
    ),
    EOSensorDescription(
        key="led",
        translation_key="led_state",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "wifi_connecting", "connected", "disconnected", "scan"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status("led"),
    ),
    EOSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("uptime"),
    ),
    EOSensorDescription(
        key="chip_temp",
        translation_key="chip_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("temp"),
    ),
    EOSensorDescription(
        key="heap_free",
        translation_key="heap_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.KILOBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("heap_free"),
    ),
    EOSensorDescription(
        key="crashes",
        translation_key="crashes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("crashes"),
    ),
    EOSensorDescription(
        key="rst_txt",
        translation_key="reset_reason",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("rst_txt"),
    ),
    EOSensorDescription(
        key="build",
        translation_key="firmware_build",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_sysinfo("build"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren anlegen - was es gibt, entscheidet der erste Poll."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    entities: list[SensorEntity] = [
        AdvancedSolarLogSensor(coordinator, description)
        for description in (
            *POWER_SENSORS,
            *ENERGY_SENSORS,
            *COST_SENSORS,
            *DIAGNOSTIC_SENSORS,
        )
        if description.exists_fn(data)
    ]

    async_add_entities(entities)


class AdvancedSolarLogSensor(AdvancedSolarLogEntity, SensorEntity):
    """Ein Wert aus /api/status oder /api/sysinfo."""

    entity_description: EOSensorDescription

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        description: EOSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Aktueller Wert."""
        return self.entity_description.value_fn(self.coordinator.data)
