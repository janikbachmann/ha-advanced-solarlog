# Advanced Solar-Log — Home Assistant Integration

Custom Integration für Home Assistant, die den EnergyOptimizer-P4 über dieselbe
HTTP/JSON-API abfragt wie dessen eigene Web-UI. Damit stehen in Home Assistant
alle Werte zur Verfügung, die das Gerät von Solar-Log holt — **inklusive
Batterieleistung und Ladestand**, die im offiziellen Solar-Log-Plugin fehlen.

Die Integration spricht **nur das lokale Gerät** an (kein Cloud-Dienst), pollt
im einstellbaren Intervall und kommt ohne zusätzliche Python-Abhängigkeiten aus.

> **Rein lesend.** Die Integration ruft ausschliesslich die GET-Routen
> `/api/status`, `/api/sysinfo` und `/api/alarms` auf und schreibt nichts auf
> das Gerät. Steckdosen schalten, Automatikmodus umschalten, Refresh und
> Alarmquittierung sind vorbereitet, aber bewusst nicht aktiv — der Code dazu
> liegt unter [`archive/`](archive/README.md).

## Entitäten

### Anlagenwerte (aus `GET /api/status`)

| Entity | Quelle | Einheit |
|---|---|---|
| Produktion / Verbrauch / Netzleistung | `prod`, `cons`, `grid` | W |
| **Batterieleistung** (+ laden / − entladen) | `batt` | W |
| **Batterie-Ladestand** | `soc` | % |
| Produktion / Verbrauch / Netzbezug / Einspeisung — heute | `energy.dp/dc/dgi/dgo` | kWh |
| dieselben Zähler — gesamt | `energy.tp/tc/tgi/tgo` | kWh |
| Bezugskosten, Einspeiseerlös, Eigenverbrauchswert, Grundgebühr | `cost.*` | CHF |

Batterie- und Kostensensoren werden nur angelegt, wenn das Gerät die Felder
liefert — `batt`/`soc` nur bei Anlagen mit Batterie, `cost` nur, wenn auf dem
Gerät ein Strompreis hinterlegt ist. Die Firmware rechnet in Rappen; die
Integration rechnet auf CHF um, damit Home Assistants Währungslogik greift.

Die Zähler haben `state_class: total_increasing` und passen damit direkt ins
**Energie-Dashboard** von Home Assistant.

### Zustand und Diagnose

Binärsensoren für Fail-Safe, Batterie-Vorrang-Blockade, aktiven Alarm,
MQTT-Verbindung, Ethernet-Link, NVS-Fehler und vorhandenes Absturzabbild;
Diagnosesensoren für Alter und nächsten Zeitpunkt der Solar-Log-Abfrage,
offene Alarme und deren Schwere, Status-LED, Laufzeit, Chip-Temperatur,
freien Speicher, Absturzzähler, Neustartgrund und Firmware-Build.

Steckdosen erscheinen nicht — weder als Schalter noch als Messwerte. Die
Integration zeigt ausschliesslich die Werte der Anlage.

## Installation

### HACS

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories
2. `https://github.com/janikbachmann/ha-advanced-solarlog` als Kategorie
   „Integration“ hinzufügen
3. „Advanced Solar-Log“ installieren und Home Assistant neu starten

### Manuell

`custom_components/advanced_solarlog/` in das `config/custom_components/`-
Verzeichnis von Home Assistant kopieren und neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → „Advanced Solar-Log“.

- **Host**: `energyoptimizer.local` oder die IP des Geräts
- **Port**: 80
- **Web-Passwort**: das am Gerät gesetzte Passwort. Der Benutzername ist in der
  Firmware fest auf `admin` verdrahtet. Ist am Gerät kein Passwort gesetzt, ist
  die API offen und das Feld bleibt leer.

Das Abfrageintervall (Standard 15 s) lässt sich danach unter „Konfigurieren“
ändern. Die Web-UI des Geräts pollt jede Sekunde; für Home Assistant ist ein
gröberes Intervall sinnvoll. Ein serverseitiges Rate-Limit gibt es auf den
GET-Routen nicht.

Lehnt das Gerät die Zugangsdaten ab, antworten alle Routen einheitlich mit
`401 {"ok":false,"auth":false}`. Die Integration startet dann automatisch einen
Re-Auth-Dialog, in dem nur das Passwort neu eingegeben wird.

## Hinweise

- Reines HTTP im LAN, keine TLS-Verschlüsselung — das Gerät bietet kein HTTPS.
- Passwörter und Secrets (Solar-Log-, MQTT-, Web-Passwort, ntfy-Topic) sind auf
  keiner Leseroute abrufbar und tauchen daher auch in den Diagnosedaten nicht
  auf.
- Der Domain-Name `advanced_solarlog` ist unveränderlich und steckt in jeder
  Entity-ID. Er lässt sich nach der ersten Installation nicht mehr ändern, ohne
  alle Entitäten neu anzulegen.

## Entwicklung

Die API-Referenz, gegen die diese Integration gebaut ist, liegt als
`HOMEASSISTANT_API.md` beim Firmware-Projekt.

Die beiden Smoke-Tests laufen ohne Home-Assistant-Installation gegen einen
nachgebauten Geräte-Server bzw. gegen Stub-Module:

```
pip install aiohttp
python3 tests/test_api.py
python3 tests/test_entities.py
```

Für eine Aufnahme in die HACS-Standardliste wäre zusätzlich ein Brand-Asset
(`icon.png`) nötig. Als benutzerdefiniertes Repository funktioniert die
Integration auch ohne.
