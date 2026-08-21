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
- der letzte vollständige lokale Qualitätslauf: 235 Tests, 93 Prozent Coverage, Lint, Typprüfung und Hassfest grün.

Der Fremdcode wurde statisch untersucht. Seine Tests wurden nicht lokal ausgeführt und seine reale Hardwareerfahrung
wurde nur anhand öffentlich dokumentierter Geräte, Issues und Diskussionen bewertet.

## Zusammenfassung

`lbbrhzn/ocpp` ist das funktional breitere und praktisch reifere Produkt. Das Projekt unterstützt OCPP 1.6J sowie
experimentell 2.0.1/2.1, Firmware- und DataTransfer-Funktionen, umfangreiche Sitzungsmetriken und viele
reale Ladegeräte. Es verfügt über eine große Nutzerbasis und eine umfangreiche Testsuite (Coverage wird per
Codecov berichtet, aber laut `.coveragerc`/`tests.yaml` nicht als `fail_under`-Schwelle in CI erzwungen — direkt
gegen den Quellcode verifiziert, korrigiert eine frühere Fassung dieses Dokuments, die fälschlich einen
verpflichtenden 95-Prozent-Grenzwert unterstellte).

Unsere Integration ist kleiner und bislang nur simulatorgetestet. Ihr Fundament entspricht dafür konsequenter den
aktuellen Home-Assistant-Strukturen: typisiertes `entry.runtime_data`, einmalige Action-Registrierung in
`async_setup()`, entry-scoped Gerätekennungen, übersetzte Fehler und Entity-Metadaten sowie eine klare Trennung von
Home-Assistant-Layer, Domain-Modell und OCPP-Transport.

Die strategische Empfehlung lautet deshalb: Praxiserfahrung und Absicherung übernehmen, nicht die ältere interne
Architektur. Hardwarevalidierung, CI und klar abgegrenzte Sitzungsdiagnostik haben Vorrang. FirmwareManagement,
DataTransfer und OCPP 2.x bleiben separate Produktentscheidungen (direktes TLS wurde am 2026-08-21 bereits
umgesetzt, siehe Phase 5).

## Vergleichsmatrix

| Bereich              | `lbbrhzn/ocpp`                                                                                      | Dieses Projekt                                                 | Bewertung                     |
| -------------------- | --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------- |
| Produktreife         | Über 1.200 Commits, mehr als 100 Releases, breite Nutzerbasis                                       | `0.1.0`, junges Projekt                                        | Klarer Vorsprung extern       |
| Hardware             | Zahlreiche Modelle und Firmwarebesonderheiten dokumentiert                                          | Bisher OCPP-Simulator                                          | Größtes eigenes Defizit       |
| OCPP-Versionen       | 1.6J; 2.0.1 und 2.1 experimentell                                                                   | Bewusst nur 1.6                                                | Fokus versus Breite           |
| Transport            | `ws://` und direktes `wss://`                                                                       | `ws://` und direktes `wss://` (Phase 5, 2026-08-21)            | Gleichauf                     |
| Entities             | Sensor, Switch, Number, Button; viele Sitzungs-/Diagnosewerte                                       | Dieselben Plattformen, kleinerer Satz                          | Extern breiter                |
| Actions              | Acht, inklusive Firmware, DataTransfer und Custom Message                                           | Neun, inklusive Autorisierung, Reset, Unlock und Power Limit   | Unterschiedliche Schwerpunkte |
| Messwerte            | Konfigurierbare bekannte Measurands                                                                 | Dynamische Measurands, getrennt nach Phase                     | Eigene Modellierung flexibler |
| Power Limit          | Maximum Current, wiederhergestellter Wert                                                           | Set/Clear, optimistische Number und separater Effective-Sensor | Eigene Semantik klarer        |
| Mehrfachinstanzen    | Nutzergewählter `cpid`, integrationsweit geprüft                                                    | Entry-scoped, längenpräfixierte IDs                            | Eigenes Modell sicherer       |
| Laufzeitdaten        | `hass.data[DOMAIN]`                                                                                 | Typisiertes `entry.runtime_data`                               | Eigenes Modell aktueller      |
| Action-Registrierung | Beim Erzeugen des Central Systems je Entry                                                          | Einmalig in `async_setup()`                                    | Eigenes Modell aktueller      |
| Entity-Metadaten     | Teilweise hardcodierte Namen und Icons                                                              | Translation Keys und `icons.json`                              | Eigenes Modell aktueller      |
| Modularität          | Große Plattform-, API- und Charge-Point-Module                                                      | Kleine, fokussierte Pakete und Klassen                         | Eigenes Modell wartbarer      |
| Tests                | 273 Testfunktionen; Coverage per Codecov berichtet, kein `fail_under`-Grenzwert in CI (verifiziert) | 235 Testfälle; 93 Prozent Coverage                             | Extern noch mehr Testfälle    |
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

## Explizite Handlungsempfehlungen für Phasen 0 bis 4

| Priorität | Phase | Handlung                                                                                                                                                   | Abnahme                                                                                                             |
| --------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| P1        | 1     | Den vorbereiteten `type-check-and-test`-Job in `.github/workflows/lint.yml` einfügen (Maintainer -- Agent-Umgebungen können diese Datei nicht bearbeiten). | Ein absichtlicher Typfehler und ein fehlschlagender Test lassen den Job rot werden; nach Rücknahme ist die CI grün. |

Coverage-Tests und der lokal erzwungene `fail_under = 90` sind bereits erledigt (siehe Status oben);
nur das Einfügen des Workflow-Jobs selbst bleibt offen.

Für **Phase 0** besteht kein weiterer Nachbesserungsbedarf: Die Vertrags- und
Dokumentationslücken wurden mit Commit `26e9a17` geschlossen; das besondere Ergebnisverhalten von
`trigger_message` ist eine dokumentierte Produktentscheidung. **Phase 4** ist ebenfalls
abgeschlossen: Restore, Clear auf `0`, Ablehnung und die Trennung zwischen optimistischem Sollwert
und tatsächlich wirksamem Wert sind automatisiert abgedeckt.

Der P2/Phase-3-Punkt (Restart-Verhalten von Sitzungsdiagnostik und Reconnect-Zähler entscheiden und
absichern) ist ebenfalls erledigt: entschieden wurde **Persistenz** (2026-08-21, siehe
`DECISIONS.md` "Phase-3 diagnostic sensors restore across a HA restart"), umgesetzt über
`homeassistant.components.sensor.RestoreSensor` an allen fünf Sensoren, automatisiert getestet
(je ein Restore-Test pro Sensor unter `tests/sensor/`).

Zwei weitere zunächst offene Punkte wurden im Recheck vom 2026-08-21 direkt behoben (reine
Dokumentationskorrekturen, kein Entscheidungsbedarf):

- Die Wahrscheinlichkeitsaussage in `SUPPORTED_DEVICES.md` ("it will very likely work") ist
  entfernt; die Datei nennt OCPP 1.6J über `ws://`/`wss://` jetzt nur noch als technische
  Voraussetzung, nicht als Kompatibilitätsprognose.
- `docs/user/CONFIGURATION.md`s Diagnoseexport-Beschreibung nennt jetzt Reconnect-Zähler und die
  letzte Transaktion je Connector inklusive deren Redaction (`id_tag`).

Phase 2 bleibt nach der Dokumentationskorrektur bewusst pausiert, bis reale Hardware verfügbar ist.
Die fehlende Hardwarevalidierung blockiert belastbare Kompatibilitätsaussagen, aber nicht die
Arbeit an den anderen Phasen.

## Phasenplan

Jede Phase ist separat review- und auslieferbar. Eine folgende Phase setzt nur die ausdrücklich genannten Ergebnisse
der vorherigen voraus.

### Phase 1 – CI als verbindliche Qualitätsgrenze etablieren

**Status: Coverage-Ziel erreicht und lokal erzwungen, Workflow-Job noch offen (2026-08-21).** Die
lokal gemessene Coverage liegt jetzt bei 93 Prozent (vorher 78 Prozent) -- über dem beschlossenen
Ziel von 90 Prozent. Erreicht durch gezielte Tests der bis dahin ungedeckten Kernmodule:
`core/config.py` (53% -> 100%), `core/__main__.py` (0% -> 94%), `core/ocpp16/handlers.py`
(38% -> 100%, vorher hatte kein Test je `ChargePointHandler` instanziiert), `core/console.py`
(0% -> 100%) und `core/transport.py` (41% -> 100%, inklusive eines echten `wss://`-Handshakes --
schließt zugleich Phase 5s offene Live-Verifikationslücke). `pyproject.toml`s
`[tool.coverage.report]` erzwingt `fail_under = 90` bereits jetzt -- jeder lokale
`script/test --cov`-Lauf schlägt unterhalb der Grenze fehl, verifiziert mit einem probeweise auf
99 Prozent gesetzten Wert. Nur der Workflow-Job selbst fehlt noch: Bearbeiten von
`.github/workflows/*.yml` ist in dieser Agent-Umgebung durch eine Berechtigungseinstellung
blockiert (Versuch am 2026-08-21 bestätigt) -- der fertige Job-Ausschnitt liegt bereit, der
Maintainer muss ihn selbst einfügen.

**Empfehlung:** Den vorbereiteten `type-check-and-test`-Job (Typprüfung + `script/test --cov`,
dieselben Setup-Schritte wie der bestehende `ruff`-Job) in `.github/workflows/lint.yml` einfügen
und mit einem absichtlichen Typ- und Testfehler verifizieren.

- **Ziel:** Kein Typ- oder Testfehler kann mit grüner CI zusammengeführt werden.
- **Dateien:** `.github/workflows/lint.yml` oder neue fokussierte Workflows, gegebenenfalls `pyproject.toml` und
  Coverage-Konfiguration.
- **Änderungen:** Jobs für `script/type-check` und `script/test` ergänzen; Coverage-Grenzwert **90 Prozent**
  (Entscheidung des Maintainers, 2026-08-21 — bewusst nicht an `lbbrhzn/ocpp`s unbelegter 95-Prozent-Zahl
  orientiert, siehe Zusammenfassung) und ausschließlich ansteigend verändern.
- **Verifikation:** Ein absichtlich fehlschlagender Test und ein Typfehler müssen die jeweiligen Jobs lokal oder auf
  einem Testbranch rot machen; danach Teständerungen zurücknehmen.
- **Unabhängig auslieferbar:** ja.
- **Entscheidungstor:** aufgelöst -- Coverage-Grenzwert ist entschieden (90 Prozent) und lokal
  erzwungen; offen ist nur noch, wer/wann den folgenden Job einfügt.

**Fertiger Job-Ausschnitt für `.github/workflows/lint.yml`** (unter dem bestehenden `ruff`-Job
einfügen, dieselben Setup-Schritte):

```yaml
type-check-and-test:
  name: "Type check and test"
  runs-on: "ubuntu-latest"
  permissions:
    contents: read # check out the repository
  steps:
    - name: Checkout the repository
      uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      with:
        persist-credentials: false

    - name: Set up Python
      uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
      with:
        python-version: "3.14"

    - name: Install uv
      uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      with:
        version: "0.9.3"
        enable-cache: true
        cache-dependency-glob: "**/requirements*.txt"

    - name: Get Home Assistant version
      id: ha_version
      run: |
        HA_VERSION=$(grep '"homeassistant"' hacs.json | head -1 | sed 's/.*"homeassistant"\s*:\s*"\([^"]*\)".*/\1/')
        echo "HA_VERSION=${HA_VERSION}" >> $GITHUB_OUTPUT
        echo "Home Assistant version: ${HA_VERSION}"

    - name: Cache Home Assistant installation
      uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
      with:
        path: |
          .local/ha-venv
        key: ha-venv-${{ runner.os }}-py314-ha${{ steps.ha_version.outputs.HA_VERSION }}-${{ hashFiles('**/requirements*.txt') }}
        restore-keys: |
          ha-venv-${{ runner.os }}-py314-ha${{ steps.ha_version.outputs.HA_VERSION }}-
          ha-venv-${{ runner.os }}-py314-

    - name: Install requirements
      run: script/setup/bootstrap

    - name: Type check
      run: script/type-check

    # fail_under = 90 in pyproject.toml's [tool.coverage.report] is what actually enforces the
    # gate; --cov here only turns coverage measurement on for this run.
    - name: Test with coverage
      run: script/test --cov
```

### Phase 2 – Reale Hardwarevalidierung und Kompatibilitätsmatrix

**Status: pausiert (2026-08-21) — kommt mit der Zeit, sobald reale Geräte verfügbar sind. Bis dahin nur die
Struktur vorbereiten, keine Geräteeinträge erfinden.**

**Empfehlung aus dem Recheck:** Das vorbereitete Gerüst ist sinnvoll. Bis zum ersten realen Test
auch auf Wahrscheinlichkeitsaussagen zur Kompatibilität verzichten: OCPP 1.6J über `ws://`/`wss://`
ist eine technische Voraussetzung, aber noch kein Nachweis, dass ein konkretes Gerät funktioniert
— `SUPPORTED_DEVICES.md` wurde am 2026-08-21 entsprechend korrigiert (keine
Wahrscheinlichkeitsaussage mehr).

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

**Status: umgesetzt, inkl. Restart-Verhalten (2026-08-21).** Fünf neue Sensoren:
`last_transaction_id`, `session_duration_s`,
`session_energy_wh`, `last_stop_reason` (connector-scoped, über den neuen
`QueryService.get_last_transaction()`-Lesepfad) und `reconnect_count` (charge-point-scoped,
`EntityCategory.DIAGNOSTIC`, über ein neues `reconnect_count`-Feld in `registry.py`). Latenz
bewusst nicht ergänzt (Non-Goal dieser Phase, sofern nicht traffic-frei messbar — kein
naheliegender traffic-freier Signal gefunden). `diagnostics.py` erweitert um `reconnect_count` je
Charge Point und einen `last_transaction`-Eintrag je Connector (`id_tag` darin neu in `_TO_REDACT`
aufgenommen).

Start/Stop, Reconnect, Entity-Zustände und Redaction sind automatisiert nachgewiesen; die
Diagnoseexport-Dokumentation nennt seit dem 2026-08-21-Recheck auch Reconnect-Zähler und letzte
Transaktion. Das Restart-Szenario, das der Recheck als offen markiert hatte, ist ebenfalls
entschieden und umgesetzt: alle fünf Sensoren stellen ihren zuletzt bekannten Wert per
`RestoreSensor` über einen HA-Neustart hinweg wieder her (siehe `DECISIONS.md` "Phase-3 diagnostic
sensors restore across a HA restart"), automatisiert mit je einem Restore-Test pro Sensor
abgesichert. Der Domain-Layer selbst (`TransactionManager`/`ChargePointRegistryStore`) bleibt
unverändert rein im Arbeitsspeicher -- die Wiederherstellung passiert ausschließlich auf
Entity-Ebene, exakt wie bei `number.power_limit_w`.

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

**Recheck:** Vollständig umgesetzt. Restore, Clear auf `0`, abgelehnte Änderung und die Trennung
vom tatsächlich wirksamen Wert sind automatisiert abgedeckt. Kein weiterer funktionaler
Nachbesserungsbedarf innerhalb dieser Phase.

- **Ziel:** Die optimistische Number zeigt nach einem HA-Neustart nicht unnötig `unknown`, ohne sich als Live-Wert
  auszugeben.
- **Dateien:** `custom_components/ocpp/number/power_limit.py`, Tests der Number-Entity sowie README und
  Konfigurationsdokumentation.
- **Änderungen:** Letzten erfolgreich gesetzten Wert wiederherstellen oder beim ersten Connect einmal gezielt über
  den vorhandenen Effective-Power-Limit-Pfad abgleichen. Optimistischen Sollwert und tatsächlich wirksamen Wert
  weiterhin als getrennte Entities behandeln.
- **Verifikation:** Neustart-/Restore-Test, Clear-auf-`0`, abgelehnte Änderung und abweichender Effective-Wert.
- **Unabhängig auslieferbar:** ja.
- **Entscheidungstor:** aufgelöst — der möglicherweise veraltete Sollwert wird bewusst wiederhergestellt und klar vom
  tatsächlich wirksamen Wert getrennt.

### Phase 5 – Direktes TLS bewerten und gegebenenfalls implementieren

**Status: umgesetzt (2026-08-21).** Entwickler hat die "nicht ohne bestätigten Bedarf bauen"-Empfehlung
bewusst überstimmt und die Implementierung direkt beauftragt -- eingebautes TLS statt Reverse Proxy,
wie empfohlen. Siehe `DECISIONS.md` ("Direct built-in TLS instead of a reverse proxy for `wss://`")
für die vollständige Begründung, warum eingebautes TLS hier tatsächlich der einfachere Weg ist:
anders als bei HAs eigener Weboberfläche (HTTP-Vhost-Proxying, Standardfall bei praktisch jedem
Self-Hosting-Setup) braucht OCPP über einen Reverse Proxy TCP-Stream-Proxying (z. B. nginx
`stream {}`) statt des üblichen `proxy_pass`, weil der Ladepunkt direkt gegen `IP:Port` spricht und
kein HTTP-Client ist, der Host-basiertes Routing versteht.

**Umsetzung:**

- `core/config.py`: `AppConfig` um `certificate_path`/`private_key_path` erweitert, plus
  `--certificate-file`/`--private-key-file` für den Standalone-CLI.
- `core/transport.py`: neue `build_ssl_context()` (stdlib `ssl`, keine neue Abhängigkeit),
  `start_server()` reicht das Ergebnis als `ssl=` an `websockets.serve(...)` weiter. Ohne
  Zertifikat bleibt `ws://` exakt wie zuvor.
- `core/app.py`: `CentralSystemApp.__init__` bekommt ein optionales `ssl_context`-Argument,
  gespiegelt an das bestehende `authorization`-Argument -- die HA-Schicht baut den Kontext per
  Executor-Job und übergibt ihn, der Standalone-CLI fällt auf den synchronen Aufbau zurück.
- `config_flow_handler/validators/tls.py` (neu): `validate_tls_certificate()`, gespiegelt an
  `validators/authorization.py`, ruft den echten `build_ssl_context()`-Loader auf.
- `config_flow_handler/config_flow.py`: zwei neue optionale Felder (`certificate_path`,
  `private_key_path`) in `entry.data` -- additiv, keine Migration nötig (Präzedenzfall
  `max_power_limit_w`). Validiert sowohl im `user`- als auch im `reconfigure`-Schritt (nicht nur im
  Options-Flow, da verbindungskritisch wie Host/Port); nur eines von beiden gesetzt ist ein
  Formularfehler (`tls_incomplete_pair`).
- `__init__.py`: baut den `SSLContext` per Executor-Job, `ConfigEntryError` mit Übersetzungsschlüssel
  `tls_certificate_unreadable`, falls das Paar zwischen Config-Flow und (Re-)Setup ungültig wurde --
  derselbe Fehlerfall wie `authorization_file_unreadable`.
- Dokumentation: README, `CONFIGURATION.md` (neuer Abschnitt "TLS Certificate (`wss://`)", Setup-
  Tabelle, Reconfigure-Flow, Netzwerk-Abschnitt), `DECISIONS.md`.

- **Ziel:** Ladepunkte können sich ohne externen Reverse Proxy per `wss://` verbinden.
- **Verifikation:** 6 automatisierte Tests am Config-Flow (gültiges Zertifikat, unvollständiges Paar,
  ungültiges Zertifikat, Reconfigure fügt TLS hinzu, Zertifikat verschwindet nach Setup,
  `AppConfig`-Verdrahtung), plus seit dem Coverage-Recheck (2026-08-21) ein echter
  `wss://`-Handshake in `tests/core/test_transport.py`: `start_server()` bindet einen echten
  `127.0.0.1`-Socket mit selbstsigniertem Zertifikat (`tls_cert_pair`-Fixture), ein echter
  `websockets`-Client verbindet sich und schließt eine vollständige BootNotification ab -- die
  zuvor offene Live-Verifikationslücke ist damit geschlossen.
- **Unabhängig auslieferbar:** ja.
- **Breaking Change:** keiner -- rein additive Konfiguration, `ws://` bleibt der Default und bleibt
  unterstützt.

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

1. Phase 1: CI-Coverage-Grenzwert auf 90 Prozent festgelegt und in `pyproject.toml` lokal erzwungen
   (2026-08-21), Coverage-Arbeit abgeschlossen (78% -> 93%, 2026-08-21); nur der Workflow-Job selbst
   (`.github/workflows/lint.yml`) fehlt noch -- fertig vorbereitet, Einfügen durch den Maintainer
   nötig (Agent-Umgebung kann `.github/workflows/` nicht selbst bearbeiten).
2. Phase 2 ist pausiert, bis reale Geräte verfügbar sind — nur die Struktur (`SUPPORTED_DEVICES.md`-Gerüst) wurde
   vorbereitet, keine Geräteeinträge.
3. Phase 3 umgesetzt (2026-08-21).
4. Phase 4 umgesetzt (2026-08-21).
5. Nach Phase 3/4: Recheck und Prüfung der nächsten Schritte (2026-08-21, Maintainer-Vorgabe) --
   Ergebnis: Phase 5 direkt beauftragt.
6. Phase 5 umgesetzt (2026-08-21) -- Maintainer hat die "erst bei bestätigtem Bedarf"-Empfehlung
   bewusst überstimmt. Phase 6 bleibt ausschließlich bei bestätigtem Nutzerbedarf.
7. Phase 7 nicht in die aktuelle OCPP-1.6-Roadmap aufnehmen.

## Risiken und offene Entscheidungen

- **Reale Hardware fehlt:** Phase 2 ist deshalb bewusst pausiert (2026-08-21) — kommt mit der Zeit, sobald Geräte
  verfügbar sind; blockiert belastbare Kompatibilitätsaussagen, nicht die übrigen Phasen.
- **Workflowberechtigung:** Bestätigt blockiert (2026-08-21) -- Agent-Umgebungen können
  `.github/workflows/*.yml` nicht bearbeiten. Coverage-Grenzwert (90 Prozent) und -Arbeit sind
  bereits erledigt; nur das Einfügen des vorbereiteten `type-check-and-test`-Jobs bleibt am
  Maintainer hängen.
- **Stale Devices:** Die bestehende Entscheidung zu manueller oder zeitbasierter Entfernung bleibt offen und ist
  unabhängig von diesem Vergleich.
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
