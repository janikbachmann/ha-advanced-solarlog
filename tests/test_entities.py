"""Prueft jede Sensordefinition gegen einen Beispiel-Payload.

Aufruf: python3 tests/test_entities.py
"""
import importlib.util, pathlib, sys, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ha_stubs  # noqa: F401
from test_api import STATUS, SYSINFO, ALARMS  # nutzt denselben Beispiel-Payload

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "advanced_solarlog")
pkg = types.ModuleType("eo"); pkg.__path__ = [ROOT]; sys.modules["eo"] = pkg
for name in ("const", "api", "coordinator", "entity", "sensor", "binary_sensor"):
    spec = importlib.util.spec_from_file_location(f"eo.{name}", f"{ROOT}/{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[f"eo.{name}"] = mod
    spec.loader.exec_module(mod)

coordinator, sensor, binary_sensor = (sys.modules[f"eo.{n}"] for n in ("coordinator", "sensor", "binary_sensor"))
data = coordinator.AdvancedSolarLogData(status=STATUS, sysinfo=SYSINFO, alarms=ALARMS)

problems, count = [], 0
for desc in (*sensor.POWER_SENSORS, *sensor.ENERGY_SENSORS, *sensor.COST_SENSORS, *sensor.DIAGNOSTIC_SENSORS):
    if not desc.exists_fn(data):
        print(f"  uebersprungen (nicht vorhanden): {desc.key}"); continue
    value = desc.value_fn(data); count += 1
    if value is None:
        problems.append(f"sensor {desc.key} -> None")
    if desc.options is not None and value not in desc.options:
        problems.append(f"sensor {desc.key} -> {value!r} nicht in options {desc.options}")
print(f"{count} Hauptsensoren liefern Werte")

for desc in binary_sensor.BINARY_SENSORS:
    if desc.value_fn(data) is None:
        problems.append(f"binary_sensor {desc.key} -> None")
print(f"{len(binary_sensor.BINARY_SENSORS)} Binaersensoren geprueft")

# Steckdosen sind bewusst kein Teil der Integration: kein Code darf sie anlegen.
assert not hasattr(sensor, "SOCKET_SENSORS")
assert not hasattr(data, "shelly"), "Steckdosen-Zugriffe gehoeren nach archive/"
for module, name in ((sensor, "sensor"), (binary_sensor, "binary_sensor")):
    socket_classes = [n for n in dir(module) if "Socket" in n]
    assert not socket_classes, f"{name}: {socket_classes}"
print("Keine Steckdosen-Entities im ausgelieferten Code")

# Kostenrechnung Rappen -> CHF
assert sensor._cost("buy")(data) == 0.324, sensor._cost("buy")(data)
# -1 = "noch nie" muss None werden, nicht -1 Sekunde
no_poll = coordinator.AdvancedSolarLogData(status={**STATUS, "sl_age": -1}, sysinfo=SYSINFO, alarms=ALARMS)
assert next(d for d in sensor.DIAGNOSTIC_SENSORS if d.key == "sl_age").value_fn(no_poll) is None

# Anlage ohne Batterie: batt/soc fehlen im Payload -> Entities werden nicht angelegt
without_batt = {k: v for k, v in STATUS.items() if k not in ("batt", "soc")}
nb = coordinator.AdvancedSolarLogData(status=without_batt, sysinfo=SYSINFO, alarms=ALARMS)
skipped = [d.key for d in sensor.POWER_SENSORS if not d.exists_fn(nb)]
assert skipped == ["batt", "soc"], skipped
# und ohne konfigurierten Preis entfallen die Kostensensoren
nc = coordinator.AdvancedSolarLogData(status=without_batt | {"cost": None}, sysinfo=SYSINFO, alarms=ALARMS)
assert not any(d.exists_fn(nc) for d in sensor.COST_SENSORS)
print("Optionale Werte (Batterie/Kosten) werden korrekt uebersprungen")

# unique_id-Kollisionen ausschliessen
ids = [d.key for d in (*sensor.POWER_SENSORS, *sensor.ENERGY_SENSORS, *sensor.COST_SENSORS,
                       *sensor.DIAGNOSTIC_SENSORS)] + [d.key for d in binary_sensor.BINARY_SENSORS]
assert len(ids) == len(set(ids)), [k for k in ids if ids.count(k) > 1]
print("Keine doppelten Entity-Keys")

print("\nPROBLEME:", problems or "keine")
raise SystemExit(1 if problems else 0)
