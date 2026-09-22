"""Checks every sensor description against sample Solar-Log data.

Run with: python3 tests/test_entities.py
"""
import importlib.util, pathlib, sys, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ha_stubs  # noqa: F401
from test_api import BASIC, BATTERY, ENERGY  # reuse the same sample payload

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "advanced_solarlog")
pkg = types.ModuleType("asl"); pkg.__path__ = [ROOT]; sys.modules["asl"] = pkg
for name in ("const", "api", "coordinator", "entity", "sensor"):
    spec = importlib.util.spec_from_file_location(f"asl.{name}", f"{ROOT}/{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[f"asl.{name}"] = mod
    spec.loader.exec_module(mod)

coordinator, sensor = (sys.modules[f"asl.{n}"] for n in ("coordinator", "sensor"))

BATTERY_DICT = {
    "voltage": BATTERY[0], "level": BATTERY[1],
    "charge_power": BATTERY[2], "discharge_power": BATTERY[3],
}
ENERGY_DICT = {"production": ENERGY[-1][1], "self_consumption": ENERGY[-1][3]}
INVERTERS = {
    0: coordinator.InverterData(name="Fronius Dach Sued", power=2600.0, yield_year=2400000.0),
    1: coordinator.InverterData(name="Fronius Dach Ost", power=1610.0, yield_year=1720000.0),
}

from asl.api import parse_timestamp  # noqa: E402

# In production the coordinator fills last_updated after every poll; build
# the sample data the same way instead of leaving it None.
data = coordinator.AdvancedSolarLogData(
    values=BASIC,
    battery=BATTERY_DICT,
    energy=ENERGY_DICT,
    inverters=INVERTERS,
    last_updated=parse_timestamp(BASIC["100"]),
)

problems, count = [], 0
for desc in sensor.ALL_SENSORS:
    if not desc.exists_fn(data):
        print(f"  skipped (not available): {desc.key}"); continue
    value = desc.value_fn(data); count += 1
    if value is None:
        problems.append(f"sensor {desc.key} -> None")
print(f"{count} sensors produced a value")

# Sockets are deliberately out of scope: nothing in the shipped code must
# create them. The binary_sensor platform (EnergyOptimizer diagnostics) was
# removed outright, since Solar-Log itself reports none of those values.
socket_classes = [n for n in dir(sensor) if "Socket" in n]
assert not socket_classes, f"sensor: {socket_classes}"
assert not pathlib.Path(ROOT, "binary_sensor.py").exists()
print("No socket entities and no binary_sensor platform in the shipped code")

# An installation without a battery: no battery entities are created.
without_battery = coordinator.AdvancedSolarLogData(values=BASIC, battery=None, energy=ENERGY_DICT)
skipped = [d.key for d in sensor.BATTERY_SENSORS if not d.exists_fn(without_battery)]
assert skipped == [d.key for d in sensor.BATTERY_SENSORS], skipped
print("Battery sensors correctly skipped when there is no battery")

# -- unique_id collisions --
ids = [d.key for d in sensor.ALL_SENSORS]
assert len(ids) == len(set(ids)), [k for k in ids if ids.count(k) > 1]
print("No duplicate entity keys")

# -- every translation_key used in sensor.py is declared in strings.json --
import json
strings = json.load(open(f"{ROOT}/strings.json"))
declared = set(strings["entity"]["sensor"])
used = {d.translation_key for d in sensor.ALL_SENSORS} | {
    sensor.INVERTER_POWER.translation_key, sensor.INVERTER_YIELD_YEAR.translation_key
}
assert used <= declared, f"missing from strings.json: {used - declared}"
print("Every translation_key is declared in strings.json")

# -- grid_power sign: consumption below production means feed-in (negative) --
export_data = coordinator.AdvancedSolarLogData(
    values={**BASIC, "101": "500", "110": "300"}, battery=None, energy=None
)
assert export_data.grid_power == -200.0, export_data.grid_power
print("Grid power sign is correct for feed-in")

# -- the derived grid energy counters, the two the Energy dashboard needs --
# BASIC["114"] is consumption this year, ENERGY carries this year's production
# and the part of it used in the house.
grid_data = coordinator.AdvancedSolarLogData(values=BASIC, battery=None, energy=ENERGY_DICT)
assert grid_data.grid_import_year == float(BASIC["114"]) - ENERGY_DICT["self_consumption"], (
    grid_data.grid_import_year
)
assert grid_data.grid_export_year == (
    ENERGY_DICT["production"] - ENERGY_DICT["self_consumption"]
), grid_data.grid_export_year
print("Grid import and export are consumption/production minus self-consumption")

# A total_increasing sensor reads a negative value as a counter reset, so the
# two blocks disagreeing by a rounding step must not push either below zero.
skewed = coordinator.AdvancedSolarLogData(
    values={**BASIC, "114": "1"},
    battery=None,
    energy={"production": 1.0, "self_consumption": 5.0},
)
assert skewed.grid_import_year == 0.0, skewed.grid_import_year
assert skewed.grid_export_year == 0.0, skewed.grid_export_year
print("Neither grid counter can go negative")

# Without the login-gated energy block there is nothing to derive them from.
no_energy = coordinator.AdvancedSolarLogData(values=BASIC, battery=None, energy=None)
assert no_energy.grid_import_year is None and no_energy.grid_export_year is None
print("Grid counters stay absent without the energy block")

# -- the battery energy counters this integration adds up itself --
# The Solar-Log reports battery power in W and no Wh counters, so these are
# integrated from the power readings. Three things decide whether the result
# is usable to the Energy dashboard: the arithmetic, surviving a restart, and
# not inventing energy across an outage.
import asyncio as _asyncio  # noqa: E402
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402


class _FakeEntry:
    entry_id = "entry"
    title = "Advanced Solar-Log"


class _FakeClient:
    base_url = "http://192.0.2.10"


class _FakeCoordinator:
    config_entry = _FakeEntry()
    client = _FakeClient()

    def __init__(self, data):
        self.data = data


def _battery_data(charge, discharge):
    return coordinator.AdvancedSolarLogData(
        values=BASIC,
        battery={"voltage": 400.0, "level": 50.0,
                 "charge_power": charge, "discharge_power": discharge},
        energy=None,
    )


CHARGED, DISCHARGED = sensor.BATTERY_ENERGY_COUNTERS
clock = {"now": _dt(2026, 9, 22, 8, 0, tzinfo=_tz.utc)}
sys.modules["homeassistant.util.dt"].utcnow = lambda: clock["now"]

counter = sensor.AdvancedSolarLogEnergyCounter(_FakeCoordinator(_battery_data(0.0, 0.0)), CHARGED)
_asyncio.run(counter.async_added_to_hass())
assert counter.native_value == 0.0, counter.native_value

# 1000 W held over an hour is 1000 Wh. The first reading only starts the
# clock, so the energy arrives with the second one.
counter.coordinator.data = _battery_data(1000.0, 0.0)
clock["now"] += _td(minutes=10)
counter._handle_coordinator_update()
# Averaged across the interval: 0 W rising to 1000 W over 10 minutes.
assert counter.native_value == round(500.0 * 600 / 3600, 3), counter.native_value
print("Battery counter integrates power over the interval")

before_gap = counter.native_value
clock["now"] += _td(hours=6)
counter._handle_coordinator_update()
assert counter.native_value == before_gap, counter.native_value
print("A long gap adds nothing instead of inventing energy")

# After the gap the clock restarts, so counting resumes normally.
clock["now"] += _td(minutes=10)
counter._handle_coordinator_update()
assert counter.native_value > before_gap, counter.native_value
print("Counting resumes after the gap")

# A restart must not reset the counter to zero: the Energy dashboard reads
# the rise between two points and would see that as a full discharge.
class _Restored:
    native_value = 1234.5

restarted = sensor.AdvancedSolarLogEnergyCounter(
    _FakeCoordinator(_battery_data(0.0, 500.0)), DISCHARGED
)
restarted.async_get_last_sensor_data = lambda: _asyncio.sleep(0, result=_Restored())
_asyncio.run(restarted.async_added_to_hass())
assert restarted.native_value == 1234.5, restarted.native_value
print("The counter is restored after a restart")

# Each counter follows its own direction.
assert CHARGED.power_fn(_battery_data(700.0, 0.0)) == 700.0
assert DISCHARGED.power_fn(_battery_data(0.0, 300.0)) == 300.0
assert CHARGED.power_fn(coordinator.AdvancedSolarLogData(values=BASIC, battery=None)) is None
print("Charge and discharge counters read their own side")

# Both are declared the way the Energy dashboard's battery section needs: the
# same energy unit the device's own Wh counters already use, which the
# dashboard accepts.
WATT_HOURS = next(d for d in sensor.ENERGY_SENSORS if d.key == "yield_year")
for description in sensor.BATTERY_ENERGY_COUNTERS:
    assert description.device_class == sensor.SensorDeviceClass.ENERGY
    assert description.state_class == sensor.SensorStateClass.TOTAL_INCREASING
    assert (
        description.native_unit_of_measurement
        == WATT_HOURS.native_unit_of_measurement
    ), description.native_unit_of_measurement
    assert description.translation_key in declared, description.translation_key
print("Battery counters are declared as energy for the Energy dashboard")

print("\nPROBLEMS:", problems or "none")
raise SystemExit(1 if problems else 0)
