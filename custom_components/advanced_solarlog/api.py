"""Read-only client for the Solar-Log JSON interface (`/getjp`).

The integration talks to the Solar-Log device itself, over the local network.
No cloud service and no intermediate hardware is involved.

Solar-Log exposes a single endpoint, `POST /getjp`. The request body is a JSON
object whose keys are numeric value addresses; the response mirrors that shape
and carries the values. Protected installations require a session cookie that
`login()` obtains.

This client only ever reads. It has no method that changes anything on the
device -- see `archive/README.md` for the reasoning.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    DEFAULT_PORT,
    LOGIN_USERNAMES,
    REQ_BASIC,
    REQ_BATTERY,
    REQ_DEVICE_LIST,
    REQ_ENERGY,
    REQ_INVERTER_ENERGY,
    REQ_INVERTER_POWER,
    REQ_SALT,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30

# Solar-Log answers with these markers instead of an HTTP status code.
MARKER_DENIED = "ACCESS DENIED"
MARKER_IMPOSSIBLE = "QUERY IMPOSSIBLE 000"


class AdvancedSolarLogError(Exception):
    """The device could not be reached or answered with something unusable."""


class AdvancedSolarLogAuthError(AdvancedSolarLogError):
    """The device refused the request because of a wrong or missing password."""


class AdvancedSolarLogClient:
    """Minimal read-only client for one Solar-Log device."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
        password: str | None = None,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.password = password or ""
        # The account name the device accepted, once one has been found.
        self.username = LOGIN_USERNAMES[0]
        # Older firmware ignores the cookie and expects the session token
        # repeated in the request body.
        self._token = ""
        self._hashed_password = False
        # What the device answered to each login attempt of the last login.
        # Carries no password, and is what the diagnostics download reports.
        self.login_trace: list[dict[str, Any]] = []

    @property
    def base_url(self) -> str:
        """Base URL of the device, also used as the device page link in HA."""
        if self.port == DEFAULT_PORT:
            return f"http://{self.host}"
        return f"http://{self.host}:{self.port}"

    async def _post_response(
        self, body: str, path: str = "getjp"
    ) -> aiohttp.ClientResponse:
        """Send one request and return the raw response."""
        url = f"{self.base_url}/{path}"
        # Solar-Log rejects application/json here; its own web UI posts the
        # JSON document as text/html and relies on the CSRF header.
        headers = {"Content-Type": "text/html", "X-SL-CSRF-PROTECTION": "1"}
        if self._token:
            body = f"token={self._token}; " + body

        try:
            response = await self._session.post(
                url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            )
        except asyncio.TimeoutError as err:
            raise AdvancedSolarLogError(
                f"Timeout while connecting to Solar-Log at {self.host}"
            ) from err
        except aiohttp.ClientError as err:
            raise AdvancedSolarLogError(
                f"Cannot connect to Solar-Log at {self.host}: {err}"
            ) from err

        if response.status == 401:
            raise AdvancedSolarLogAuthError("Solar-Log rejected the credentials")
        if response.status != 200:
            raise AdvancedSolarLogError(
                f"Solar-Log answered with HTTP {response.status} on {path}"
            )

        return response

    async def _post(self, body: str, path: str = "getjp") -> str:
        """Send one request and return the raw response text."""
        response = await self._post_response(body, path)
        return await response.text(errors="replace")

    async def _request(self, body: str, *, allow_relogin: bool = True) -> dict[str, Any]:
        """Send one `/getjp` request and return the decoded response."""
        text = await self._post(body)

        if MARKER_IMPOSSIBLE in text:
            raise AdvancedSolarLogError(f"Solar-Log cannot answer this query: {body}")
        # The salt query legitimately carries "ACCESS DENIED" alongside the salt.
        if MARKER_DENIED in text and not text.startswith('{"550"'):
            _LOGGER.debug(
                "Solar-Log denied %s; token set=%s, cookie in jar for this host=%s",
                body,
                bool(self._token),
                self._cookie_in_jar(),
            )
            # The device drops a session after a while, and nothing else in the
            # integration notices -- so a denial is worth one fresh login.
            if allow_relogin and self.password and await self.async_login():
                return await self._request(body, allow_relogin=False)
            raise AdvancedSolarLogAuthError(
                "Solar-Log denied access -- a password is required for this value"
            )

        try:
            return json.loads(text)
        except ValueError as err:
            raise AdvancedSolarLogError(
                f"Solar-Log sent a response that is not JSON: {text[:200]}"
            ) from err

    async def async_login(self) -> bool:
        """Log in if a password is configured.

        Returns True when a session was established, False when no account
        name this integration knows was accepted -- which the device reports
        identically whether it has no password set or expects a different
        account name, so that case is logged rather than assumed away.
        """
        self.login_trace = []
        if not self.password:
            return False

        for username in LOGIN_USERNAMES:
            response = await self._post_response(
                f"u={username}&p={self.password}", path="login"
            )
            text = await response.text(errors="replace")
            _LOGGER.debug("Solar-Log login as %r answered: %s", username, text[:200])

            if "FAILED - User was wrong" in text:
                self._trace_login(username, text, response, "account name refused")
                continue

            if "FAILED - Password was wrong" in text:
                # Newer firmware expects the password bcrypt-hashed with a salt
                # the device hands out. Only a second failure is a real auth
                # error.
                self._trace_login(username, text, response, "retrying hashed")
                text, response = await self._retry_login_hashed(username)

            if "FAILED" in text:
                self._trace_login(username, text, response, "password refused")
                raise AdvancedSolarLogAuthError("Solar-Log rejected the password")

            self._trace_login(username, text, response, "accepted")
            self.username = username
            self._remember_session(response)
            return True

        _LOGGER.warning(
            "Solar-Log answered 'User was wrong' for every account name this "
            "integration knows (%s). Either the device has no password set, or "
            "its login expects an account name that is not in that list -- "
            "battery, self-consumption and per-inverter values stay unavailable",
            ", ".join(LOGIN_USERNAMES),
        )
        return False

    def _trace_login(
        self,
        username: str,
        text: str,
        response: aiohttp.ClientResponse,
        outcome: str,
    ) -> None:
        """Record what the device answered, for the diagnostics download.

        Which account name a given firmware accepts is the one thing that
        cannot be guessed from here, and asking for a debug log to find out
        has proven to be a lot to ask. The answer is a single short string
        per attempt, so the diagnostics file carries it instead. No password
        goes in -- the request body is not recorded, only the reply.
        """
        self.login_trace.append(
            {
                "username": username,
                "outcome": outcome,
                "answer": text[:120],
                "cookies": list(response.cookies.keys()),
            }
        )

    def login_report(self) -> dict[str, Any]:
        """Summarise the session state for the diagnostics download."""
        return {
            "password_configured": bool(self.password),
            "accepted_username": self.username if self.login_trace else None,
            "known_usernames": list(LOGIN_USERNAMES),
            "password_is_hashed": self._hashed_password,
            "body_token_set": bool(self._token),
            "cookie_in_jar": self._cookie_in_jar(),
            "attempts": self.login_trace,
        }

    async def _retry_login_hashed(
        self, username: str
    ) -> tuple[str, aiohttp.ClientResponse]:
        """Second login attempt with the bcrypt-hashed password."""
        # Imported lazily: bcrypt is only needed on firmware that hashes.
        import bcrypt  # noqa: PLC0415

        salt = (
            (await self._request(REQ_SALT, allow_relogin=False))
            .get("550", {})
            .get("104")
        )
        if not salt or salt == MARKER_IMPOSSIBLE:
            self.login_trace.append(
                {
                    "username": username,
                    "outcome": "no salt for the hashed login",
                    "answer": str(salt)[:120],
                    "cookies": [],
                }
            )
            raise AdvancedSolarLogAuthError("Solar-Log rejected the password")

        try:
            hashed = bcrypt.hashpw(self.password.encode(), salt.encode()).decode()
        except (TypeError, ValueError) as err:
            raise AdvancedSolarLogAuthError(
                "Solar-Log returned a salt that bcrypt does not accept"
            ) from err

        response = await self._post_response(f"u={username}&p={hashed}", path="login")
        text = await response.text(errors="replace")
        _LOGGER.debug("Solar-Log hashed-password login response: %s", text[:200])
        if "FAILED" not in text:
            # Keep the hash: the device expects it on every later login.
            self.password = hashed
            self._hashed_password = True
        return text, response

    def _remember_session(self, response: aiohttp.ClientResponse) -> None:
        """Make sure the session cookie survives on an IP-address host too.

        Home Assistant's shared HTTP session uses aiohttp's default cookie
        jar, which silently drops cookies for bare IP-address hosts -- common
        for a local device like this one. Calling `update_cookies()` without
        a response URL stores the cookie with no host restriction at all, so
        aiohttp attaches it to every request from this session regardless of
        host -- the jar's `unsafe`/IP check only ever looks at the URL that
        is passed in, and an empty one has none. This is the same workaround
        `solarlog_cli` (the reference client this integration is modelled
        on) uses.

        Some older firmware doesn't honour the cookie at all, even once it's
        present, and instead expects the session token repeated in the
        request body -- so that fallback is kept too, but only for the
        plain-password login path. `solarlog_cli` restricts it the same
        way, which suggests hashed-password (newer) firmware does not
        expect that prefix and may reject a request body that carries it.
        """
        cookie = response.cookies.get("SolarLog")
        if not cookie:
            _LOGGER.warning(
                "Solar-Log login reported success but sent no 'SolarLog' cookie "
                "(cookies in the response: %s) -- battery, self-consumption and "
                "per-inverter values will stay unavailable",
                list(response.cookies.keys()),
            )
            return
        _LOGGER.debug(
            "Solar-Log session cookie captured (hashed_password=%s)",
            self._hashed_password,
        )
        self._session.cookie_jar.update_cookies({"SolarLog": cookie.value})
        if not self._hashed_password:
            self._token = cookie.value

    def _cookie_in_jar(self) -> bool:
        """Debug helper: is a cookie currently attached for this host."""
        try:
            return bool(self._session.cookie_jar.filter_cookies(self.base_url))
        except Exception:  # noqa: BLE001 - diagnostic only, must never break a request
            return False

    async def async_test_connection(self) -> bool:
        """Check that the host really is a Solar-Log with the interface enabled."""
        data = await self._request(REQ_BASIC)
        return isinstance(data.get("801", {}).get("170"), dict)

    async def async_test_extended_data(self) -> bool:
        """Check whether the protected values (battery, inverters) are readable."""
        try:
            await self._request(REQ_DEVICE_LIST)
        except AdvancedSolarLogAuthError:
            return await self.async_login()
        except AdvancedSolarLogError:
            return False
        return True

    async def async_get_basic_data(self) -> dict[str, Any]:
        """Read the main measurements (`801`/`170`)."""
        data = await self._request(REQ_BASIC)
        values = data.get("801", {}).get("170")
        if not isinstance(values, dict):
            raise AdvancedSolarLogError(
                "Solar-Log did not return the expected 801/170 block"
            )
        return values

    async def async_get_battery(self) -> dict[str, float] | None:
        """Read battery voltage, state of charge and charge/discharge power.

        Solar-Log returns a bare list here. An empty list means the
        installation has no battery.
        """
        raw = (await self._request(REQ_BATTERY)).get("858")
        if not raw or not isinstance(raw, list) or len(raw) < 4:
            return None
        return {
            "voltage": _as_float(raw[0]),
            "level": _as_float(raw[1]),
            "charge_power": _as_float(raw[2]),
            "discharge_power": _as_float(raw[3]),
        }

    async def async_get_energy(self) -> dict[str, float] | None:
        """Read this year's production and self-consumption totals (`878`)."""
        raw = (await self._request(REQ_ENERGY)).get("878")
        if not isinstance(raw, list) or not raw:
            return None
        latest = raw[-1]
        if not isinstance(latest, list) or len(latest) < 4:
            return None
        return {
            "production": _as_float(latest[1]),
            "self_consumption": _as_float(latest[3]),
        }

    async def async_get_device_list(self) -> dict[int, str]:
        """Read the connected inverters and their names."""
        raw = (await self._request(REQ_DEVICE_LIST)).get("740") or {}
        devices: dict[int, str] = {}
        for key, value in raw.items():
            if value == "Err":
                continue
            name = (
                (await self._request(f'{{"141":{{"{key}":{{"119":null}}}}}}'))
                .get("141", {})
                .get(key, {})
                .get("119")
            )
            devices[int(key)] = name or f"Inverter {key}"
        return devices

    async def async_get_inverter_power(self) -> dict[int, float]:
        """Read the current AC power of every inverter (`782`)."""
        raw = (await self._request(REQ_INVERTER_POWER)).get("782") or {}
        return {int(key): _as_float(value) for key, value in raw.items()}

    async def async_get_inverter_energy(self) -> dict[int, float]:
        """Read this year's yield of every inverter (`854`).

        The response is a nested history array; the last entry holds the
        current year, with one value per inverter in device-index order.
        """
        raw = (await self._request(REQ_INVERTER_ENERGY)).get("854")
        if not isinstance(raw, list) or not raw:
            return {}
        values = raw[-1][-1]
        if not isinstance(values, list):
            return {}
        return {index: _as_float(value) for index, value in enumerate(values)}


def _as_float(value: Any) -> float:
    """Solar-Log mixes numbers and numeric strings in the same response."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_timestamp(value: Any) -> datetime | None:
    """Parse Solar-Log's `dd.mm.yy HH:MM:SS` timestamp."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%d.%m.%y %H:%M:%S")
    except ValueError:
        return None
