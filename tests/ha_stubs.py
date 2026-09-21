"""Minimal homeassistant stubs so the platform modules import without Home Assistant."""
import sys, types
from dataclasses import dataclass
from enum import StrEnum

def _mod(name):
    m = sys.modules.get(name)
    if m is None:
        m = types.ModuleType(name); sys.modules[name] = m
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(_mod(parent), child, m)
    return m

class _Str(StrEnum):
    pass

def _enum(name, members):
    return StrEnum(name, {m: m.lower() for m in members})

class EntityDescription:
    def __init_subclass__(cls, **kw): super().__init_subclass__(**kw)

@dataclass(frozen=True, kw_only=True)
class _Desc:
    key: str
    translation_key: str | None = None
    device_class: object = None
    state_class: object = None
    native_unit_of_measurement: str | None = None
    suggested_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    entity_category: object = None
    entity_registry_enabled_default: bool = True
    options: list | None = None
    name: object = None
    icon: str | None = None

_mod("homeassistant")
const = _mod("homeassistant.const")
const.PERCENTAGE = "%"
const.EntityCategory = _enum("EntityCategory", ["DIAGNOSTIC", "CONFIG"])
for unit_name, members in {
    "UnitOfElectricCurrent": ["AMPERE"], "UnitOfElectricPotential": ["VOLT"],
    "UnitOfEnergy": ["KILO_WATT_HOUR", "WATT_HOUR"], "UnitOfInformation": ["BYTES", "KILOBYTES"],
    "UnitOfPower": ["WATT"], "UnitOfTemperature": ["CELSIUS"],
    "UnitOfTime": ["SECONDS", "MINUTES"],
}.items():
    setattr(const, unit_name, _enum(unit_name, members))
const.Platform = _enum("Platform", ["SENSOR", "BINARY_SENSOR", "SWITCH", "BUTTON"])
const.CONF_HOST, const.CONF_PORT, const.CONF_PASSWORD = "host", "port", "password"

sensor = _mod("homeassistant.components.sensor")
sensor.SensorEntity = type("SensorEntity", (), {})
sensor.SensorEntityDescription = _Desc
sensor.SensorDeviceClass = _enum("SensorDeviceClass", [
    "POWER", "BATTERY", "ENERGY", "MONETARY", "DURATION", "ENUM",
    "TEMPERATURE", "DATA_SIZE", "VOLTAGE", "CURRENT", "TIMESTAMP"])
sensor.SensorStateClass = _enum("SensorStateClass", ["MEASUREMENT", "TOTAL", "TOTAL_INCREASING"])

bs = _mod("homeassistant.components.binary_sensor")
bs.BinarySensorEntity = type("BinarySensorEntity", (), {})
bs.BinarySensorEntityDescription = _Desc
bs.BinarySensorDeviceClass = _enum("BinarySensorDeviceClass", ["PROBLEM", "CONNECTIVITY"])

ce = _mod("homeassistant.config_entries")
ce.ConfigEntry = type("ConfigEntry", (), {})
core = _mod("homeassistant.core")
core.HomeAssistant = type("HomeAssistant", (), {})
core.callback = lambda f: f
ep = _mod("homeassistant.helpers.entity_platform")
ep.AddEntitiesCallback = object
uc = _mod("homeassistant.helpers.update_coordinator")
uc.CoordinatorEntity = type("CoordinatorEntity", (), {"__class_getitem__": classmethod(lambda cls, item: cls)})
uc.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {"__class_getitem__": classmethod(lambda cls, item: cls)})
uc.UpdateFailed = type("UpdateFailed", (Exception,), {})
dr = _mod("homeassistant.helpers.device_registry")
dr.DeviceInfo = dict
exc = _mod("homeassistant.exceptions")
exc.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
exc.HomeAssistantError = type("HomeAssistantError", (Exception,), {})

import datetime as _datetime
dt_util = _mod("homeassistant.util.dt")
dt_util.get_default_time_zone = lambda: _datetime.timezone.utc
util = _mod("homeassistant.util")
util.dt = dt_util
