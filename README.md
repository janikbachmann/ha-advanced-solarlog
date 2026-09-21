<div align="center">
  <img src="custom_components/advanced_solarlog/brand/icon.png" alt="Advanced Solar-Log" width="128">

  # Advanced Solar-Log

  **Alle Werte deiner Solar-Log-Anlage in Home Assistant — auch die, die das offizielle Plugin auslässt.**

  [![Status: Work in Progress][wip-badge]](#status)
  [![Version][version-badge]][releases]
  [![HACS: Custom][hacs-badge]][hacs]
  [![Validate][validate-badge]][validate]
  [![Lizenz: MIT][license-badge]][license]
</div>

---

## Status

> [!WARNING]
> **Work in Progress — Version 0.1.0.**
> Diese Integration ist noch **nicht auf einer echten Home-Assistant-Instanz
> getestet**. Der Code ist durch automatische Tests und die Prüfungen von
> Home Assistant (`hassfest`) abgedeckt, aber das Zusammenspiel mit einem
> laufenden Home Assistant und einem echten Gerät steht noch aus.
>
> Rechne mit Fehlern, und melde sie bitte als [Issue][issues].
> **Version 1.0.0 gibt es erst, wenn der produktive Betrieb bestätigt ist.**

Diese Integration liest die Werte deiner Photovoltaik-Anlage über den
**EnergyOptimizer-P4** aus — das Gerät, das Solar-Log bereits abfragt und die
Daten aufbereitet bereitstellt. Dadurch landen in Home Assistant auch
**Batterieleistung und Ladestand**, die im offiziellen Solar-Log-Plugin fehlen.

Die Integration arbeitet rein lokal: kein Cloud-Dienst, keine zusätzlichen
Python-Abhängigkeiten, keine Konfiguration in YAML.

## Warum diese Integration

| | Offizielles Solar-Log-Plugin | Advanced Solar-Log |
|---|---|---|
| Produktion, Verbrauch, Netz | ✅ | ✅ |
| **Batterieleistung und Ladestand** | ❌ | ✅ |
| Tages- und Gesamtzähler fürs Energie-Dashboard | teilweise | ✅ |
| Stromkosten und Einspeiseerlös | ❌ | ✅ |
| Anlagen-Alarme und Gerätediagnose | ❌ | ✅ |
| Einrichtung über die Oberfläche | ✅ | ✅ |

## Entitäten

### Leistung

| Entität | Einheit | Bemerkung |
|---|---|---|
| Produktion | W | aktuelle Erzeugung |
| Verbrauch | W | aktueller Hausverbrauch |
| Netzleistung | W | positiv = Bezug, negativ = Einspeisung |
| **Batterieleistung** | W | positiv = laden, negativ = entladen |
| **Batterie-Ladestand** | % | |

### Energie

Produktion, Verbrauch, Netzbezug und Einspeisung — jeweils **heute** und
**gesamt**, in kWh. Alle als `total_increasing` deklariert und damit direkt im
Energie-Dashboard verwendbar.

### Kosten

Bezugskosten, Einspeiseerlös, Eigenverbrauchswert und anteilige Grundgebühr für
den laufenden Tag, in CHF. Erscheinen nur, wenn am Gerät ein Strompreis
hinterlegt ist.

### Zustand und Diagnose

Fail-Safe, Batterie-Vorrang-Blockade, aktiver Alarm, MQTT-Verbindung,
Ethernet-Link, NVS-Fehler, Absturzabbild — dazu Alter und nächster Zeitpunkt der
Solar-Log-Abfrage, offene Alarme samt Schwere, Status-LED, Laufzeit,
Chip-Temperatur, freier Speicher, Absturzzähler, Neustartgrund und
Firmware-Build.

> Batterie- und Kostensensoren werden nur angelegt, wenn das Gerät die Felder
> auch liefert. Anlagen ohne Batterie bekommen keine leeren Entitäten.

## Installation

### Über HACS

[![Repository zu HACS hinzufügen][my-hacs-badge]][my-hacs]

Oder von Hand: HACS → Integrationen → ⋮ → **Benutzerdefinierte Repositories** →
`https://github.com/janikbachmann/ha-advanced-solarlog` als Kategorie
*Integration* hinzufügen, danach „Advanced Solar-Log" installieren und Home
Assistant neu starten.

### Manuell

Den Ordner `custom_components/advanced_solarlog/` in das
`config/custom_components/`-Verzeichnis von Home Assistant kopieren und neu
starten.

## Einrichtung

[![Integration hinzufügen][my-config-badge]][my-config]

Oder: **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Advanced
Solar-Log"**.

| Feld | Wert |
|---|---|
| Host | `energyoptimizer.local` oder die IP des Geräts |
| Port | `80` |
| Web-Passwort | das am Gerät gesetzte Passwort — leer lassen, wenn keins gesetzt ist |

Der Benutzername ist in der Firmware fest auf `admin` verdrahtet und wird nicht
abgefragt.

Das **Abfrageintervall** (Standard 15 Sekunden) lässt sich danach unter
*Konfigurieren* ändern. Die Web-Oberfläche des Geräts pollt jede Sekunde; für
Home Assistant ist ein gröberes Intervall sinnvoll.

## Dashboard

Die Integration liefert die Werte; die Darstellung übernehmen die Karten von
Home Assistant. Ein fertiges Beispiel mit Energiefluss, Momentanwerten,
Batterie-Anzeige, Tagesbilanz und Verlauf liegt unter
[`examples/dashboard.yaml`](examples/dashboard.yaml) — einfügen über
Dashboard → ⋮ → *Raw-Konfigurationseditor*.

Für das eingebaute **Energie-Dashboard** unter Einstellungen → Dashboards →
Energie:

- **Netzbezug** → `Netzbezug heute`
- **Einspeisung** → `Einspeisung heute`
- **Solarproduktion** → `Produktion heute`
- **Batterie** → die Batteriezähler, falls vorhanden

Eine Live-Flussanzeige wie in der Geräte-App liefert zusätzlich die Karte
[Power Flow Card Plus][power-flow] aus HACS; die passende Konfiguration steht
als Kommentar in der Beispieldatei.

## Was die Integration nicht tut

Sie ist **rein lesend**. Aufgerufen werden ausschliesslich `GET /api/status`,
`GET /api/sysinfo` und `GET /api/alarms`; auf das Gerät wird nichts
geschrieben.

Steckdosen erscheinen weder als Schalter noch als Messwerte. Der Code dafür —
Relais- und Automatik-Schalter, Solar-Log-Refresh, Alarmquittierung — liegt
unter [`archive/`](archive/README.md), wird von Home Assistant nicht geladen und
ist dort mit Reaktivierungsanleitung dokumentiert.

## Fehlersuche

**Die Einrichtung meldet „Verbindung fehlgeschlagen".**
Ist `energyoptimizer.local` aus dem Home-Assistant-Netz erreichbar? Im Zweifel
die IP-Adresse direkt eintragen. Das Gerät spricht reines HTTP, kein HTTPS.

**Die Einrichtung meldet „Passwort wurde abgelehnt".**
Das Web-Passwort des Geräts, nicht das Solar-Log-Passwort. Ist am Gerät keins
gesetzt, muss das Feld leer bleiben.

**Batterie-Entitäten fehlen.**
Das Gerät liefert `batt` und `soc` nur bei Anlagen mit Batterie. Prüfen lässt
sich das unter *Geräte & Dienste → Advanced Solar-Log → Diagnose herunterladen*.

**Werte stehen auf „nicht verfügbar".**
Der Sensor *Letzte Solar-Log-Abfrage* zeigt, wann das Gerät zuletzt
erfolgreich bei Solar-Log war. Bleibt er leer, hängt es zwischen Gerät und
Solar-Log, nicht an Home Assistant.

## Entwicklung

Die beiden Smoke-Tests laufen ohne Home-Assistant-Installation — einer gegen
einen nachgebauten Geräte-Server, einer prüft jede Sensordefinition gegen einen
Beispiel-Payload:

```bash
pip install aiohttp
python3 tests/test_api.py
python3 tests/test_entities.py
```

Die CI prüft zusätzlich mit `hassfest` die Manifest- und Übersetzungsdateien
gegen die Regeln von Home Assistant und mit `hacs/action` die
Repository-Struktur.

Der Domain-Name `advanced_solarlog` steckt in jeder Entity-ID und lässt sich
nach der ersten Installation nicht mehr ändern, ohne alle Entitäten neu
anzulegen.

`custom_components/advanced_solarlog/brand/icon.png` ist ein Platzhalter-Icon.
Für eine Aufnahme in die HACS-Standardliste gehört es zusätzlich ins
[`home-assistant/brands`][brands]-Repository.

## Lizenz

[MIT](LICENSE)

<!-- Links -->
[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[validate]: https://github.com/janikbachmann/ha-advanced-solarlog/actions/workflows/validate.yml
[validate-badge]: https://img.shields.io/github/actions/workflow/status/janikbachmann/ha-advanced-solarlog/validate.yml?style=for-the-badge&label=Validate
[license]: LICENSE
[license-badge]: https://img.shields.io/badge/Lizenz-MIT-green.svg?style=for-the-badge
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=janikbachmann&repository=ha-advanced-solarlog&category=integration
[my-hacs-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[my-config]: https://my.home-assistant.io/redirect/config_flow_start/?domain=advanced_solarlog
[my-config-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[brands]: https://github.com/home-assistant/brands
[wip-badge]: https://img.shields.io/badge/Status-Work%20in%20Progress-orange.svg?style=for-the-badge
[version-badge]: https://img.shields.io/badge/Version-0.1.0-blue.svg?style=for-the-badge
[releases]: https://github.com/janikbachmann/ha-advanced-solarlog/releases
[issues]: https://github.com/janikbachmann/ha-advanced-solarlog/issues
[power-flow]: https://github.com/flixlix/power-flow-card-plus
