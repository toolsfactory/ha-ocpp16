# Vergleich mit `lbbrhzn/ocpp` und phased Handlungsempfehlungen

Stand: 21. August 2026

## Zweck und Vergleichsstand

Dieser Vergleich ordnet die eigene Integration gegenüber
[`lbbrhzn/ocpp`](https://github.com/lbbrhzn/ocpp) ein. Er ist keine Empfehlung, das Fremdprojekt zu kopieren. Ziel ist,
dessen Praxiserfahrung gezielt zu nutzen, ohne die modularere Architektur und den bewusst engen OCPP-1.6-Fokus dieses
Projekts aufzugeben.

Verglichen wurden:

- `lbbrhzn/ocpp` auf `main`, Commit
  [`9fb32d0`](https://github.com/lbbrhzn/ocpp/commit/9fb32d0dd2309d984ea3128f041b8542f726c09c) vom 15. August 2026;
- dessen Repository, Manifest, Config Flow, Entity-Plattformen, Actions, Tests und
  [Read-the-Docs-Dokumentation](https://home-assistant-ocpp.readthedocs.io/en/stable/);
- dieses Repository auf dem lokalen Stand vom 21. August 2026;
- der letzte vollständige lokale Qualitätslauf: 123 Tests, 76 Prozent Coverage, Lint, Typprüfung und Hassfest grün.

Der Fremdcode wurde statisch untersucht. Seine Tests wurden nicht lokal ausgeführt und seine reale Hardwareerfahrung
wurde nur anhand öffentlich dokumentierter Geräte, Issues und Diskussionen bewertet.

## Zusammenfassung

`lbbrhzn/ocpp` ist das funktional breitere und praktisch reifere Produkt. Das Projekt unterstützt OCPP 1.6J sowie
experimentell 2.0.1/2.1, direktes TLS, Firmware- und DataTransfer-Funktionen, umfangreiche Sitzungsmetriken und viele
reale Ladegeräte. Es verfügt über eine große Nutzerbasis und eine umfangreiche Testsuite (Coverage wird per
Codecov berichtet, aber laut `.coveragerc`/`tests.yaml` nicht als `fail_under`-Schwelle in CI erzwungen — direkt
gegen den Quellcode verifiziert, korrigiert eine frühere Fassung dieses Dokuments, die fälschlich einen
verpflichtenden 95-Prozent-Grenzwert unterstellte).

Unsere Integration ist kleiner und bislang nur simulatorgetestet. Ihr Fundament entspricht dafür konsequenter den
aktuellen Home-Assistant-Strukturen: typisiertes `entry.runtime_data`, einmalige Action-Registrierung in
`async_setup()`, entry-scoped Gerätekennungen, übersetzte Fehler und Entity-Metadaten sowie eine klare Trennung von
Home-Assistant-Layer, Domain-Modell und OCPP-Transport.

Die strategische Empfehlung lautet deshalb: Praxiserfahrung und Absicherung übernehmen, nicht die ältere interne
Architektur. Hardwarevalidierung, CI und klar abgegrenzte Sitzungsdiagnostik haben Vorrang. TLS, FirmwareManagement,
DataTransfer und OCPP 2.x sind separate Produktentscheidungen.

## Vergleichsmatrix

| Bereich              | `lbbrhzn/ocpp`                                                                                      | Dieses Projekt                                                 | Bewertung                     |
| -------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------- |
| Produktreife         | Über 1.200 Commits, mehr als 100 Releases, breite Nutzerbasis                                       | `0.1.0`, junges Projekt                                        | Klarer Vorsprung extern       |
| Hardware             | Zahlreiche Modelle und Firmwarebesonderheiten dokumentiert                                          | Bisher OCPP-Simulator                                          | Größtes eigenes Defizit       |
| OCPP-Versionen       | 1.6J; 2.0.1 und 2.1 experimentell                                                                   | Bewusst nur 1.6                                                | Fokus versus Breite           |
| Transport            | `ws://` und direktes `wss://`                                                                       | `ws://`, TLS nur über Reverse Proxy                            | Extern komfortabler           |
| Entities             | Sensor, Switch, Number, Button; viele Sitzungs-/Diagnosewerte                                       | Dieselben Plattformen, kleinerer Satz                          | Extern breiter                |
| Actions              | Acht, inklusive Firmware, DataTransfer und Custom Message                                           | Neun, inklusive Autorisierung, Reset, Unlock und Power Limit   | Unterschiedliche Schwerpunkte |
| Messwerte            | Konfigurierbare bekannte Measurands                                                                 | Dynamische Measurands, getrennt nach Phase                     | Eigene Modellierung flexibler |
| Power Limit          | Maximum Current, wiederhergestellter Wert                                                           | Set/Clear, optimistische Number und separater Effective-Sensor | Eigene Semantik klarer        |
| Mehrfachinstanzen    | Nutzergewählter `cpid`, integrationsweit geprüft                                                    | Entry-scoped, längenpräfixierte IDs                            | Eigenes Modell sicherer       |
| Laufzeitdaten        | `hass.data[DOMAIN]`                                                                                 | Typisiertes `entry.runtime_data`                               | Eigenes Modell aktueller      |
| Action-Registrierung | Beim Erzeugen des Central Systems je Entry                                                          | Einmalig in `async_setup()`                                    | Eigenes Modell aktueller      |
| Entity-Metadaten     | Teilweise hardcodierte Namen und Icons                                                              | Translation Keys und `icons.json`                              | Eigenes Modell aktueller      |
| Modularität          | Große Plattform-, API- und Charge-Point-Module                                                      | Kleine, fokussierte Pakete und Klassen                         | Eigenes Modell wartbarer      |
| Tests                | 273 Testfunktionen; Coverage per Codecov berichtet, kein `fail_under`-Grenzwert in CI (verifiziert) | 123 Testfälle; 76 Prozent Coverage                             | Extern klar stärker           |
| CI                   | Pytest, Coverage-Report, Hassfest und HACS                                                          | Lint/Hassfest; Typprüfung und Tests nicht verpflichtend        | Extern klar stärker           |
| Dokumentation        | Eigene Website und Supported-Devices-Katalog                                                        | Architektur-, Entscheidungs- und Interop-Dokumente             | Unterschiedliche Stärken      |

## Was übernommen werden sollte

### Hoher Nutzen

- Verpflichtende Tests und Coverage in CI.
- Reale Geräte- und Firmwarematrix mit reproduzierbaren Ergebnissen.
- Sitzungsdaten: Transaktions-ID, Dauer, Energie und Stop-Grund.
- Verbindungsdiagnostik: Reconnect-Zähler und optional gemessene Latenz.
- Dokumentierte Herstellerabweichungen statt stiller Workarounds im Code.

### Nur nach Produktentscheidung

- Direktes TLS im eingebetteten WebSocket-Server.
- FirmwareManagement-Actions.
- Generischer DataTransfer oder frei formulierbare OCPP-Nachrichten.
- OCPP 2.0.1 oder 2.1.
- Automatische Konfiguration von Measurands am Ladepunkt.

## Was nicht übernommen werden sollte

- Laufzeitobjekte in `hass.data[DOMAIN]` zurückverlagern.
- Actions pro Config Entry registrieren.
- Nutzergewählte Namen als Grundlage persistenter Geräte- oder Entity-IDs verwenden.
- Entity-Namen und Icons in Python hardcodieren.
- Große `api.py`-, `chargepoint.py`- oder Plattformmonolithen aufbauen.
- Schema-Validierung als gewöhnliche Nutzeroption abschaltbar machen.
- Generische OCPP-Actions ohne enges Schema, übersetzte Fehler und klaren Sicherheitsrahmen anbieten.
- OCPP 2.x als Marketingmerkmal ergänzen, bevor Protokoll- und reale Gerätetests vorhanden sind. Ein aktuelles
  [Issue](https://github.com/lbbrhzn/ocpp/issues/2008) zeigt, dass falsche Versionszuordnung einen Ladepunkt vollständig
  unbenutzbar machen kann.

## Phasenplan

Jede Phase ist separat review- und auslieferbar. Eine folgende Phase setzt nur die ausdrücklich genannten Ergebnisse
der vorherigen voraus.

### Phase 1 – CI als verbindliche Qualitätsgrenze etablieren

- **Ziel:** Kein Typ- oder Testfehler kann mit grüner CI zusammengeführt werden.
- **Dateien:** `.github/workflows/lint.yml` oder neue fokussierte Workflows, gegebenenfalls `pyproject.toml` und
  Coverage-Konfiguration.
- **Änderungen:** Jobs für `script/type-check` und `script/test` ergänzen; Coverage-Grenzwert **90 Prozent**
  (Entscheidung des Maintainers, 2026-08-21 — bewusst nicht an `lbbrhzn/ocpp`s unbelegter 95-Prozent-Zahl
  orientiert, siehe Zusammenfassung) und ausschließlich ansteigend verändern.
- **Verifikation:** Ein absichtlich fehlschlagender Test und ein Typfehler müssen die jeweiligen Jobs lokal oder auf
  einem Testbranch rot machen; danach Teständerungen zurücknehmen.
- **Unabhängig auslieferbar:** ja.
- **Entscheidungstor:** Wer darf Workflowdateien ändern? (Coverage-Grenzwert ist entschieden: 90 Prozent.)

### Phase 2 – Reale Hardwarevalidierung und Kompatibilitätsmatrix

**Status: pausiert (2026-08-21) — kommt mit der Zeit, sobald reale Geräte verfügbar sind. Bis dahin nur die
Struktur vorbereiten, keine Geräteeinträge erfinden.**

- **Ziel:** Aussagen zur Geräteunterstützung beruhen auf reproduzierbaren Tests statt auf Protokollannahmen.
- **Dateien:** neue, ausdrücklich freizugebende `docs/user/SUPPORTED_DEVICES.md`,
  `docs/user/GETTING_STARTED.md`, gerätespezifische Fixtures unter `tests/fixtures/` und passende Regressionstests.
- **Änderungen:** Pro Gerät Hersteller, Modell, Firmware, OCPP-Version, Connectoranzahl, Authentisierung,
  Measurands, Power-Limit-Funktionen, Reset/Unlock und bekannte Abweichungen erfassen. Workarounds nur mit konkretem
  Gerät/Firmware und Regressionstest aufnehmen.
- **Verifikation:** Definierter manueller Smoke-Test gegen jedes verfügbare Gerät; automatisierte Replay- oder
  Payloadtests für jede gefundene Abweichung.
- **Unabhängig auslieferbar:** ja, fortlaufend erweiterbar.
- **Nicht-Ziel:** Ungetestete Geräte als unterstützt auflisten.

### Phase 3 – Sitzungs- und Verbindungsdiagnostik ergänzen

**Status: umgesetzt (2026-08-21).** Fünf neue Sensoren: `last_transaction_id`, `session_duration_s`,
`session_energy_wh`, `last_stop_reason` (connector-scoped, über den neuen
`QueryService.get_last_transaction()`-Lesepfad) und `reconnect_count` (charge-point-scoped,
`EntityCategory.DIAGNOSTIC`, über ein neues `reconnect_count`-Feld in `registry.py`). Latenz
bewusst nicht ergänzt (Non-Goal dieser Phase, sofern nicht traffic-frei messbar — kein
naheliegender traffic-freier Signal gefunden). `diagnostics.py` erweitert um `reconnect_count` je
Charge Point und einen `last_transaction`-Eintrag je Connector (`id_tag` darin neu in `_TO_REDACT`
aufgenommen).

- **Ziel:** Nutzer können einen Ladevorgang und Verbindungsprobleme ohne DEBUG-Vollframes nachvollziehen.
- **Dateien:** `custom_components/ocpp/core/domain/models.py`, `transactions.py`, `registry.py`, `query.py`,
  `core/ocpp16/handlers.py`, neue fokussierte Sensor-Dateien, `sensor/__init__.py`, `translations/en.json`,
  `icons.json`, `diagnostics.py`, Tests und Nutzerdokumentation.
- **Änderungen:** Zuerst Transaktions-ID, Stop-Grund, Sitzungsdauer und Sitzungsenergie; danach Reconnect-Zähler.
  Latenz nur ergänzen, wenn sie ohne zusätzlichen oder übermäßigen OCPP-Traffic zuverlässig messbar ist.
- **Verifikation:** Start/Stop-, Reconnect- und Restart-Szenarien; Zustände über `hass.states` prüfen; Diagnoseexport
  auf Redaction kontrollieren.
- **Unabhängig auslieferbar:** ja, in zwei Teilphasen „Sitzung“ und „Verbindung“.
- **Nicht-Ziel:** Herstellerabhängige Werte als universelle OCPP-Fakten darstellen.

### Phase 4 – Power-Limit-Zustand nach Neustart verständlicher machen

**Status: umgesetzt (2026-08-21).** Entscheidungstor aufgelöst: letzten gesetzten Wert wiederherstellen (nicht
per `GetCompositeSchedule` abgleichen), über `homeassistant.components.number.RestoreNumber` — kein
zusätzlicher Central-System-initiierter Traffic beim Neustart. Siehe `DECISIONS.md`.

- **Ziel:** Die optimistische Number zeigt nach einem HA-Neustart nicht unnötig `unknown`, ohne sich als Live-Wert
  auszugeben.
- **Dateien:** `custom_components/ocpp/number/power_limit.py`, Tests der Number-Entity sowie README und
  Konfigurationsdokumentation.
- **Änderungen:** Letzten erfolgreich gesetzten Wert wiederherstellen oder beim ersten Connect einmal gezielt über
  den vorhandenen Effective-Power-Limit-Pfad abgleichen. Optimistischen Sollwert und tatsächlich wirksamen Wert
  weiterhin als getrennte Entities behandeln.
- **Verifikation:** Neustart-/Restore-Test, Clear-auf-`0`, abgelehnte Änderung und abweichender Effective-Wert.
- **Unabhängig auslieferbar:** ja.
- **Entscheidungstor:** Ist ein alter Sollwert nach Neustart nützlicher als `unknown`, obwohl das Gerät ihn außerhalb
  von HA geändert haben kann?

### Phase 5 – Direktes TLS bewerten und gegebenenfalls implementieren

- **Ziel:** Ladepunkte können sich ohne externen Reverse Proxy per `wss://` verbinden, falls dies ein bestätigter
  Nutzerbedarf ist.
- **Dateien:** zunächst `.agents/scratch/`-Plan und anschließend Entscheidung in
  `docs/development/DECISIONS.md`; bei Freigabe Config Flow, Entry-Daten/Migration, Transport/App-Konfiguration,
  Übersetzungen, Tests und Nutzerdokumentation.
- **Änderungen:** Zertifikats- und Schlüsselpfad, sichere Dateivalidierung, asynchrones Laden, klare Fehler und
  Reload-Verhalten. Bestehendes `ws://` bleibt unterstützt.
- **Verifikation:** Gültige und ungültige Zertifikate, belegter Port, Reload, parallele Einträge sowie realer
  TLS-Handshake mit Simulator.
- **Unabhängig auslieferbar:** ja, aber erst nach Entscheidung.
- **Breaking Change:** keiner bei additiver Konfiguration; eine Änderung bestehender Entry-Daten erfordert Migration.

### Phase 6 – Erweiterte OCPP-Operationen nach konkretem Bedarf

- **Ziel:** Nur nachgewiesen benötigte Funktionen wie FirmwareManagement oder DataTransfer ergänzen.
- **Dateien:** jeweils eigene Domain-Ergebnisse und Command-Methoden, Verbindungsschnittstelle,
  OCPP-1.6-Handler, separater Action-Handler, `services.yaml`, Übersetzungen, Tests und Dokumentation.
- **Änderungen:** Eine Operation pro Teilphase. Enge Schemas, Device-Targeting, Timeouts und übersetzte Fehler;
  Antworten nicht als Erfolg ausgeben, wenn das Ladegerät die Operation ablehnt.
- **Verifikation:** Erfolgs-, Ablehnungs-, Timeout-, Disconnect- und ungültige Eingabepfade gegen Tests und mindestens
  einen geeigneten Simulator oder ein reales Gerät.
- **Unabhängig auslieferbar:** ja, je Operation.
- **Nicht-Ziel:** Eine unbeschränkte „sende beliebige OCPP-Nachricht“-Action.

### Phase 7 – OCPP 2.x nur als separates Produktprogramm

- **Ziel:** Eine spätere OCPP-2.x-Unterstützung gefährdet weder 1.6-Verbindungen noch deren persistente Identitäten.
- **Voraussetzung:** Nachweisbarer Nutzerbedarf, Zugriff auf mindestens ein reales 2.x-Gerät, protokollspezifische
  Test-Payloads und eine bestätigte Geräte-/Entity-Modellierung.
- **Planungsumfang:** Eigener Architekturplan und eigene Entscheidungen für Subprotokollauswahl, Domain-Modell,
  Device Registry, Transaktionen, Security Profiles und Migration. Noch keine konkreten Implementierungsdateien
  festlegen, bevor diese Seams entschieden sind.
- **Verifikation:** Gemischte 1.6-/2.x-Verbindungen, falsche und fehlende Subprotokolle, Boot, Transaktionen,
  Messwerte und Neustarts. Eine 2.x-Nachricht darf niemals gegen ein 1.6-Schema laufen.
- **Unabhängig auslieferbar:** nein; eigenes größeres Vorhaben.
- **Nicht-Ziel:** Experimentelle 2.x-Unterstützung im bestehenden 1.6-Handler verzweigen.

## Empfohlene Reihenfolge

Phase 0 (Vertrags-/Dokumentationslücken) wurde am 2026-08-21 vollständig umgesetzt (Commit `26e9a17`) und ist aus
diesem Plan entfernt.

1. Phase 1: CI-Coverage-Grenzwert auf 90 Prozent festgelegt (2026-08-21); Umsetzung hängt an
   Workflow-Schreibrechten.
2. Phase 2 ist pausiert, bis reale Geräte verfügbar sind — nur die Struktur (`SUPPORTED_DEVICES.md`-Gerüst) wurde
   vorbereitet, keine Geräteeinträge.
3. Phase 3 wird jetzt umgesetzt.
4. Phase 4 wird jetzt umgesetzt.
5. Nach Phase 3/4: Recheck und Prüfung der nächsten Schritte (2026-08-21, Maintainer-Vorgabe).
6. Phasen 5 und 6 ausschließlich bei bestätigtem Nutzerbedarf.
7. Phase 7 nicht in die aktuelle OCPP-1.6-Roadmap aufnehmen.

## Risiken und offene Entscheidungen

- **Reale Hardware fehlt:** Phase 2 ist deshalb bewusst pausiert (2026-08-21) — kommt mit der Zeit, sobald Geräte
  verfügbar sind; blockiert belastbare Kompatibilitätsaussagen, nicht die übrigen Phasen.
- **Workflowberechtigung:** Der Maintainer klärt Schreibzugriff auf `.github/workflows/`; blockiert Phase 1
  (Coverage-Grenzwert selbst ist mit 90 Prozent bereits entschieden).
- **Stale Devices:** Die bestehende Entscheidung zu manueller oder zeitbasierter Entfernung bleibt offen und ist
  unabhängig von diesem Vergleich.
- **TLS-Bedarf:** Der Maintainer entscheidet Reverse Proxy versus eingebautes TLS; blockiert Phase 5.
- **Restore-Semantik:** Der Maintainer entscheidet, ob ein möglicherweise veralteter Sollwert besser als `unknown`
  ist; blockiert Phase 4.
- **Erweiterte Operationen:** Konkrete Geräte- oder Nutzeranforderungen entscheiden den Umfang; blockiert Phase 6.
- **OCPP 2.x:** Benötigt ein eigenes bestätigtes Zielbild; blockiert Phase 7 vollständig.

## Quellen

- [`lbbrhzn/ocpp` Repository](https://github.com/lbbrhzn/ocpp)
- [Manifest auf `main`](https://github.com/lbbrhzn/ocpp/blob/main/custom_components/ocpp/manifest.json)
- [Config Flow auf `main`](https://github.com/lbbrhzn/ocpp/blob/main/custom_components/ocpp/config_flow.py)
- [Actions auf `main`](https://github.com/lbbrhzn/ocpp/blob/main/custom_components/ocpp/services.yaml)
- [CI-Workflow auf `main`](https://github.com/lbbrhzn/ocpp/blob/main/.github/workflows/tests.yaml)
- [Supported Devices](https://home-assistant-ocpp.readthedocs.io/en/stable/supported-devices.html)
- [User Guide](https://home-assistant-ocpp.readthedocs.io/en/latest/user-guide.html)
