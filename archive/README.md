# Archiv — noch nicht aktiver Code

Was hier liegt, ist **bewusst nicht Teil der Integration**. Die Dateien werden
von Home Assistant nicht geladen, weil sie ausserhalb von
`custom_components/advanced_solarlog/` liegen. Sie sind aufgehoben, um später
ohne Neuschreiben wieder aktiviert werden zu können.

Aktueller Stand: Die Integration ist **rein lesend**. Sie ruft nur die drei
GET-Routen `/api/status`, `/api/sysinfo` und `/api/alarms` auf und schreibt
nichts auf das Gerät.

## `switch.py` — Steckdosen schalten

Ein Relais-Schalter und ein Automatik-Schalter je Shelly-Steckdose und je
MQTT-Ext-Switch, über `POST /api/shelly/<idx>/<on|off|autoon|autooff>` bzw.
`/api/ext/...`. Löst den Slot-Index vor jedem Befehl neu über die stabile
Shelly-ID auf, weil die Indizes beim Hinzufügen und Entfernen von Geräten
verrutschen.

## `button.py` — Aktionen am Gerät

Zwei Buttons: „Solar-Log jetzt abfragen“ (`POST /api/refresh`) und „Alarme
quittieren“ (`POST /api/alarms/ack?id=-1`).

## Wieder aktivieren

1. Aus `socket_support.py` die Klasse `AdvancedSolarLogSocketEntity` zurück nach
   `entity.py` holen und die auskommentierten Properties zurück in
   `AdvancedSolarLogData` in `coordinator.py`.
2. Die gewünschte Plattformdatei nach `custom_components/advanced_solarlog/`
   verschieben.
3. In `__init__.py` die Plattform zu `PLATFORMS` hinzufügen
   (`Platform.SWITCH` bzw. `Platform.BUTTON`).
4. In `api.py` die passenden Methoden wieder ergänzen — siehe unten.
5. Die Übersetzungsschlüssel in `strings.json`, `translations/de.json` und
   `translations/en.json` ergänzen: für `switch.py` `switch.socket_auto`
   („Automatik“ / „Automatic mode“), für `button.py` `button.refresh_solarlog`
   („Solar-Log jetzt abfragen“ / „Poll Solar-Log now“) und `button.ack_alarms`
   („Alarme quittieren“ / „Acknowledge alarms“).
6. `tests/test_entities.py` sichert zu, dass im ausgelieferten Code keine
   Steckdosen-Entities stehen — diese Zusicherung dann entfernen.

### Fehlende Methoden in `api.py`

```python
    async def async_refresh_solarlog(self) -> None:
        """POST /api/refresh - sofortigen Solar-Log-Poll anfordern."""
        await self._request("POST", "/api/refresh")

    async def async_ack_alarms(self, alarm_id: int = -1) -> None:
        """POST /api/alarms/ack - Alarme quittieren (-1 = alle)."""
        await self._request("POST", "/api/alarms/ack", params={"id": alarm_id})

    async def async_switch_command(
        self,
        kind: str,
        index: int,
        command: str,
        minutes: int = 0,
    ) -> None:
        """POST /api/<shelly|ext>/<idx>/<on|off|autoon|autooff>."""
        if kind not in ("shelly", "ext"):
            raise ValueError(f"Unbekannter Geraetetyp: {kind}")
        if command not in ("on", "off", "autoon", "autooff"):
            raise ValueError(f"Unbekannter Befehl: {command}")
        params = {"min": minutes} if minutes else None
        await self._request("POST", f"/api/{kind}/{index}/{command}", params=params)
```

Die CSRF-Prüfung des Geräts (`checkOrigin()`) besteht ohne `Origin`- oder
`Referer`-Header automatisch, wie sie von `aiohttp` gesendet werden — schaltende
Aufrufe brauchen also keine Sonderbehandlung.
