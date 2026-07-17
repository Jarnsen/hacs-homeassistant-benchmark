# Home Assistant Performance Benchmark

Der Home Assistant Performance Benchmark misst primär **Home Assistant selbst**:
Reaktionsfähigkeit, Latenzen, Ruckler und Verhalten unter einer kontrollierten
HA-Last.

Hardwaredaten wie CPU-Kerne, RAM, Architektur und Installationsart werden nur als
Vergleichsmetadaten gespeichert. Sie geben dem Score keine direkten Punkte.

## Gemessene HA-Bereiche

- Event Loop im Leerlauf: P50, P95, P99 und Ausreißer
- Event Loop unter kontrollierter HA-Service-Last
- State Machine: State-Änderung bis zum Listener
- Event Bus: Event bis zum Listener
- Service-System: Aufruf bis zum Abschluss
- Template Engine: realistische, aufgewärmte Templates mit State-Zugriff
- Stabilität und Schwankung zwischen den Einzelmessungen

Synthetische CPU-Schleifen und Datenträger-Durchsatz sind seit Version 3 nicht
mehr Bestandteil des Benchmarks.

## Scores

- **HA Core Score:** kontrollierte interne HA-Verarbeitung
- **Flüssigkeits-Score:** Event-Loop-Latenz, P99-Ruckler und Verhalten unter Last
- **HA Performance Score:** 70 % Core und 30 % Flüssigkeit, geometrisch kombiniert

Die Score-Formel heißt `ha_score_v3`. Öffentliche Ranking-Ergebnisse werden auf
GitHub aus den Messwerten neu berechnet. Ein vom Nutzer eingesendeter Score wird
nicht vertraut.

Gewichtung des HA Core Scores: Loaded Event Loop 30 %, State Machine 25 %,
Event Bus 15 %, Service Calls 15 %, Template Rendering 10 % und Stabilität 5 %.
Der Flüssigkeits-Score besteht aus Idle P95 40 %, Idle P99 25 %, Loaded P99
20 % und der Verlangsamung unter kontrollierter Last 15 %. Änderungen an diesen
Werten erfordern eine neue Score- oder Protokollversion.

## Installation über HACS

[![Repository in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Jarnsen&repository=hacs-homeassistant-benchmark&category=integration)

Alternativ das Repository als benutzerdefiniertes HACS-Repository der Kategorie
**Integration** hinzufügen:

```text
https://github.com/Jarnsen/hacs-homeassistant-benchmark
```

Danach Home Assistant neu starten und die Integration unter
**Einstellungen → Geräte & Dienste** hinzufügen.

## Empfohlener Vergleichslauf

Für Hardware- und Systemvergleiche immer das Profil `standard` verwenden:

```yaml
action: benchmark.start
data:
  profile: standard
```

Profile:

- `quick`: schneller Gesundheitstest, nicht fürs Ranking
- `standard`: reproduzierbarer HA-Vergleich auf unterschiedlichen Systemen
- `extended`: mehr Messwerte für lokale Diagnose

Festes Messprotokoll:

| Profil | Idle Loop | Loaded Loop | State | Event | Service | Template | Zeituntergrenze |
|---|---:|---:|---:|---:|---:|---:|---|
| `quick` | 60 | 60 | 40 | 40 | 30 | 30 | mindestens 1,2 Sekunden |
| `standard` | 300 | 300 | 300 | 300 | 200 | 300 | mindestens 12 Sekunden |
| `extended` | 600 | 600 | 600 | 600 | 400 | 600 | mindestens 24 Sekunden |

Beim Standard- und Extended-Profil wird die Event-Loop-Latenz alle 20 ms
gemessen. Die Lastphase erzeugt auf jedem System dieselbe Zielbelastung von 250
internen HA-Serviceaufrufen pro Sekunde. Damit hängt die Testlast nicht davon ab,
wie schnell die jeweilige Hardware sie selbst erzeugen kann.

Auf einer langsamen oder stark ausgelasteten Installation kann der vollständige
Lauf deutlich länger dauern. Die Dauer wird als Diagnosewert gespeichert,
vergibt aber keine direkten Scorepunkte.

Die alten Namen `light`, `normal` und `heavy` funktionieren weiterhin und werden
auf die neuen Profile abgebildet.

## Neustartmessung

Die Neustartdauer ist ein separater Diagnosewert und beeinflusst den Hauptscore
nicht:

```yaml
action: benchmark.restart_and_run
data:
  profile: standard
```

Der Benchmark wird nach dem Start von Home Assistant automatisch fortgesetzt.

## Ranking und Datenschutz

Es wird niemals automatisch etwas hochgeladen.

Für einen freiwilligen Ranking-Eintrag:

1. Standard-Benchmark starten.
2. **Ranking-Daten exportieren** drücken.
3. **Ranking-Eintrag vorbereiten** drücken.
4. Die Datei `/config/benchmark_worldlist_export.json` prüfen und in GitHub
   einfügen.

Nicht exportiert werden unter anderem Entitätsnamen, Gerätenamen, IP-Adressen,
Hostnamen, Benutzer, Tokens, Konfigurationspfade oder Integrationskonfiguration.

Die Messdatei selbst enthält keine Home-Assistant-Benutzeridentität. Der
Ranking-Eintrag ist jedoch ein öffentliches GitHub-Issue und damit mit dem
einreichenden GitHub-Konto verknüpft.

## Dashboard und Export

Dashboard-Beispiel:

```text
lovelace/example_dashboard.yaml
```

Lokale Exporte:

```text
/config/benchmark_export.json
/config/benchmark_export.csv
/config/benchmark_worldlist_export.json
```

Die vollständige technische Dokumentation, Einschränkungen, Entwicklungshinweise
und Entity-Liste stehen in der englischen [README.md](README.md).

Hinweis: Der State-Machine-Test erzeugt kurzlebige interne Zustandsänderungen.
Sie werden nach dem Lauf entfernt, können aber als historische Events im
Recorder verbleiben. Die Recorder-Datenbank selbst fließt nicht in Score v3 ein.
Die Ranking-Prüfung erkennt ungültige Daten und berechnet den Score neu, kann
aber nicht kryptografisch beweisen, dass Messwerte aus einer unveränderten
Home-Assistant-Installation stammen.

## Entwicklung und Qualität

Die Testsuite prüft Normalbetrieb, Abbruch, parallele Starts,
Neustart-Fortsetzung, Speichermigration, Exporte, Entity-Zustände,
Plattform-Fallbacks, ungültige Messwerte und jede registrierte Aktion. In der CI
gilt eine verpflichtende Testabdeckung von 100 % für Statements und Branches.

```bash
python -m pip install -r requirements_test.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest
```
