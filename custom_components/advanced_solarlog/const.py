"""Konstanten fuer die EnergyOptimizer-Integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "advanced_solarlog"

CONF_POLL_INTERVAL: Final = "poll_interval"

DEFAULT_PORT: Final = 80
DEFAULT_POLL_INTERVAL: Final = 15
MIN_POLL_INTERVAL: Final = 5
MAX_POLL_INTERVAL: Final = 600

# Der Benutzername ist in der Firmware fest verdrahtet (req->authenticate("admin", ...)).
API_USERNAME: Final = "admin"

MANUFACTURER: Final = "EnergyOptimizer"
MODEL: Final = "ESP32-P4"

# NotifySeverity / al_sev
SEVERITY_NAMES: Final = {0: "info", 1: "warn", 2: "crit"}

# AlarmId -> Klartext (Anhang A der API-Doku)
ALARM_NAMES: Final = {
    0: "Solar-Log",
    1: "Fail-Safe",
    2: "Keine Produktion",
    3: "Wechselrichter",
    4: "NVS",
}
