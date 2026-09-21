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

print("\nPROBLEMS:", problems or "none")
raise SystemExit(1 if problems else 0)
