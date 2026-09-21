"""Constants for the Advanced Solar-Log integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "advanced_solarlog"

CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_EXTENDED_DATA: Final = "extended_data"

DEFAULT_PORT: Final = 80
DEFAULT_POLL_INTERVAL: Final = 60
MIN_POLL_INTERVAL: Final = 15
MAX_POLL_INTERVAL: Final = 600

# Account names the login accepts. "user" covers the common case, but the
# device's own login screen also offers an installer role, and firmware that
# expects one of those answers a "user" login with "FAILED - User was wrong"
# -- the same answer it gives when no password is set at all, so the names are
# tried in turn before concluding the device is unprotected.
LOGIN_USERNAMES: Final = ("user", "installer", "installateur", "pm")

MANUFACTURER: Final = "Solare Datensysteme"
MODEL: Final = "Solar-Log"

# Request bodies of the /getjp interface. Solar-Log addresses every value by a
# numeric key; the nesting mirrors the device's internal object tree.
REQ_BASIC: Final = '{"801":{"170":null}}'
REQ_BATTERY: Final = '{"858":null}'
REQ_ENERGY: Final = '{"878":null}'
REQ_INVERTER_POWER: Final = '{"782":null}'
REQ_INVERTER_ENERGY: Final = '{"854":null}'
REQ_DEVICE_LIST: Final = '{"740":null}'
REQ_SALT: Final = '{"550":null}'

# Field numbers inside 801/170. Documented by the Solar-Log JSON interface and
# stable across the firmware generations that expose /getjp.
FIELD_LAST_UPDATED: Final = "100"
FIELD_POWER_AC: Final = "101"
FIELD_POWER_DC: Final = "102"
FIELD_VOLTAGE_AC: Final = "103"
FIELD_VOLTAGE_DC: Final = "104"
FIELD_YIELD_DAY: Final = "105"
FIELD_YIELD_YESTERDAY: Final = "106"
FIELD_YIELD_MONTH: Final = "107"
FIELD_YIELD_YEAR: Final = "108"
FIELD_YIELD_TOTAL: Final = "109"
FIELD_CONSUMPTION_AC: Final = "110"
FIELD_CONSUMPTION_DAY: Final = "111"
FIELD_CONSUMPTION_YESTERDAY: Final = "112"
FIELD_CONSUMPTION_MONTH: Final = "113"
FIELD_CONSUMPTION_YEAR: Final = "114"
FIELD_CONSUMPTION_TOTAL: Final = "115"
FIELD_TOTAL_POWER: Final = "116"
