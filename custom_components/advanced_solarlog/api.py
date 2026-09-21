"""Schmaler async-Client fuer die HTTP/JSON-API des EnergyOptimizer-P4."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError

from .const import API_USERNAME

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class AdvancedSolarLogError(Exception):
    """Allgemeiner Fehler beim Zugriff auf das Geraet."""


class AdvancedSolarLogAuthError(AdvancedSolarLogError):
    """Authentifizierung fehlgeschlagen (HTTP 401 {"ok":false,"auth":false})."""


class AdvancedSolarLogClient:
    """Spricht die gleiche JSON-API an wie die Web-UI des Geraets.

    Die Firmware akzeptiert HTTP-Basic-Auth auf jeder Route, daher kommt die
    Integration ohne Cookie-Handling aus. Ist auf dem Geraet kein Web-Passwort
    gesetzt, ist die API offen und `password` bleibt leer.

    Dieser Client ruft ausschliesslich lesende GET-Routen auf. Die schreibenden
    Routen (Schalten, Refresh, Alarmquittierung) liegen unter `archive/`.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._password = password or None

    @property
    def base_url(self) -> str:
        """Basis-URL des Geraets."""
        return f"http://{self._host}:{self._port}"

    @property
    def _auth(self) -> aiohttp.BasicAuth | None:
        if self._password is None:
            return None
        return aiohttp.BasicAuth(API_USERNAME, self._password)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = await self._session.request(
                method,
                url,
                params=params,
                auth=self._auth,
                timeout=REQUEST_TIMEOUT,
            )
            if response.status == 401:
                raise AdvancedSolarLogAuthError(
                    "Das Geraet hat die Zugangsdaten abgelehnt"
                )
            response.raise_for_status()
            # Die Firmware sendet application/json, aber wir sind hier tolerant.
            data = await response.json(content_type=None)
        except ClientResponseError as err:
            raise AdvancedSolarLogError(
                f"{method} {path} fehlgeschlagen: HTTP {err.status}"
            ) from err
        except (ClientError, asyncio.TimeoutError) as err:
            raise AdvancedSolarLogError(f"{method} {path} fehlgeschlagen: {err}") from err

        if not isinstance(data, dict):
            raise AdvancedSolarLogError(f"{path} lieferte kein JSON-Objekt")
        return data

    async def async_get_status(self) -> dict[str, Any]:
        """GET /api/status - der zentrale Dashboard-Payload."""
        return await self._request("GET", "/api/status")

    async def async_get_sysinfo(self) -> dict[str, Any]:
        """GET /api/sysinfo - Diagnosewerte des Geraets."""
        return await self._request("GET", "/api/sysinfo")

    async def async_get_alarms(self) -> dict[str, Any]:
        """GET /api/alarms - aktuell aktive Alarme."""
        return await self._request("GET", "/api/alarms")
