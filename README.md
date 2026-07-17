# Home Assistant Performance Benchmark

<p align="center">
  <img src="https://brands.home-assistant.io/_/homeassistant/logo.png" alt="Home Assistant" width="110">
</p>

<p align="center">
  <strong>Measure Home Assistant, not a synthetic hardware workload.</strong>
</p>

<p align="center">
  <a href="https://github.com/Jarnsen/hacs-homeassistant-benchmark/releases"><img alt="Release" src="https://img.shields.io/github/v/release/Jarnsen/hacs-homeassistant-benchmark"></a>
  <a href="https://github.com/Jarnsen/hacs-homeassistant-benchmark/actions"><img alt="Validation" src="https://github.com/Jarnsen/hacs-homeassistant-benchmark/actions/workflows/validate.yml/badge.svg"></a>
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2025.12%2B-41BDF5">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-orange">
  <img alt="License" src="https://img.shields.io/github/license/Jarnsen/hacs-homeassistant-benchmark">
</p>

[Deutsch](README.de.md)

Home Assistant Performance Benchmark is a local custom integration that measures
how responsive and fluid **Home Assistant itself** is. Version 3 measures the
event loop, state machine, event bus, service dispatcher, and template engine
using a fixed protocol.

CPU model, RAM, architecture, installation type, and instance size are collected
only as comparison metadata. They do not directly add points to the score.

## What version 3 measures

| Measurement | Question answered |
|---|---|
| Idle event-loop P95/P99 | Does Home Assistant remain responsive during normal background activity? |
| Loaded event-loop P95/P99 | Does Home Assistant develop visible scheduling lag under a controlled HA workload? |
| State-machine P95 | How quickly does an internal state update reach a `state_changed` listener? |
| Event-bus P95 | How quickly does a Home Assistant event reach its listener? |
| Service-call P95 | How quickly does Home Assistant validate and dispatch an internal service call? |
| Template-render P95 | How quickly are warmed, state-aware Home Assistant templates rendered? |
| Variability | Are results stable, or dominated by jitter and long-tail stalls? |

The test does **not** run a synthetic CPU loop or disk throughput benchmark.
Restart recovery time is available as a separate diagnostic value and never
contributes directly to the main score.

## Scores

Version 3 exposes three scores from 0 to 10,000:

- **HA Core Score** — controlled Home Assistant pipelines and their stability.
- **Fluidity Score** — event-loop latency, long-tail stalls, and slowdown under
  a controlled HA workload.
- **HA Performance Score** — a geometric combination of 70% Core and 30%
  Fluidity.

P95 is the primary latency statistic. P99 and variability penalize systems that
look fast on average but regularly stutter. Values are normalized
logarithmically, and a weighted geometric mean prevents one very weak subsystem
from being completely hidden by unrelated strong results.

The formula is versioned as `ha_score_v3`. Public rankings never trust a
submitted score: the GitHub workflow imports the integration's scoring module
and recalculates the score from the submitted measurements.

Component weights:

| HA Core Score | Weight | Fluidity Score | Weight |
|---|---:|---|---:|
| Loaded event-loop P95 | 30% | Idle event-loop P95 | 40% |
| State-machine P95 | 25% | Idle event-loop P99 | 25% |
| Event-bus P95 | 15% | Loaded event-loop P99 | 20% |
| Service-call P95 | 15% | Controlled-load slowdown | 15% |
| Template-render P95 | 10% |  |  |
| Stability | 5% |  |  |

The normalization reference values are part of the versioned implementation in
[`scoring.py`](custom_components/benchmark/scoring.py). Changing weights,
reference values, sample counts, or workload requires a new score or protocol
version.

### Score interpretation

These bands are useful for reading one installation over time. Real comparative
calibration will improve as more protocol v3 results are collected.

| Score | Interpretation |
|---:|---|
| 0–3,999 | Frequent or severe HA latency |
| 4,000–6,499 | Usable, with measurable delay or jitter |
| 6,500–8,499 | Responsive |
| 8,500–10,000 | Very responsive and consistent |

Only results produced by the same protocol and score version are directly
comparable.

## Profiles

| Profile | Purpose | Public ranking |
|---|---|---|
| `quick` | Fast health check with fewer samples | No |
| `standard` | Reproducible HA comparison across systems | Yes |
| `extended` | More samples for local diagnostics | No |

The fixed protocol is:

| Profile | Idle loop | Loaded loop | State | Event | Service | Template | Timing floor |
|---|---:|---:|---:|---:|---:|---:|---|
| `quick` | 60 | 60 | 40 | 40 | 30 | 30 | at least 1.2 seconds |
| `standard` | 300 | 300 | 300 | 300 | 200 | 300 | at least 12 seconds |
| `extended` | 600 | 600 | 600 | 600 | 400 | 600 | at least 24 seconds |

The standard and extended profiles sample event-loop lag every 20 ms. During
the loaded phase, every system receives the same target load: five internal HA
service calls every 20 ms, or 250 calls per second. This avoids making the
workload itself dependent on how fast the host happens to be.

The complete run can take substantially longer than the timing floor on a busy
or slow installation. Duration is recorded for diagnostics but does not
directly add or remove score points.

The integration still accepts the version 2 aliases `light`, `normal`, and
`heavy` in existing automations. They map to `quick`, `standard`, and
`extended`.

## Installation

### HACS custom repository

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Jarnsen&repository=hacs-homeassistant-benchmark&category=integration)

Or add it manually:

1. Open HACS.
2. Select **Integrations**.
3. Open **Custom repositories**.
4. Add `https://github.com/Jarnsen/hacs-homeassistant-benchmark`.
5. Select category **Integration**.
6. Install **Home Assistant Performance Benchmark**.
7. Restart Home Assistant.
8. Add the integration under **Settings → Devices & services**.

### Manual installation

Copy:

```text
custom_components/benchmark
```

to:

```text
/config/custom_components/benchmark
```

Restart Home Assistant and add the integration from the UI.

## Running a benchmark

The recommended method is the **Start standard benchmark** button on the
integration device page.

The equivalent action is:

```yaml
action: benchmark.start
data:
  profile: standard
```

For an extended diagnostic run:

```yaml
action: benchmark.start
data:
  profile: extended
```

Avoid intentionally starting backups, database maintenance, large downloads, or
other exceptional workloads during a comparison run. Normal integrations and
automations should remain active: their effect is part of the real Home
Assistant fluidity measurement.

## Restart benchmark

Restart time is deliberately separate from the performance score.

```yaml
action: benchmark.restart_and_run
data:
  profile: standard
```

The request is saved in Home Assistant storage before restart. After Home
Assistant reports startup completion, the benchmark resumes automatically and
stores the recovery duration with the result. Stale requests older than 15
minutes are discarded safely.

## Entities

Core entities include:

```text
sensor.benchmark_score
sensor.benchmark_core_score
sensor.benchmark_fluidity_score
sensor.benchmark_confidence
sensor.benchmark_event_loop_idle
sensor.benchmark_event_loop_loaded
sensor.benchmark_state_machine
sensor.benchmark_event_bus
sensor.benchmark_service_calls
sensor.benchmark_template_render
sensor.benchmark_restart_time
sensor.benchmark_progress
sensor.benchmark_status
sensor.benchmark_last_run
button.benchmark_start_standard
```

Hardware and instance-size sensors are diagnostic entities and disabled by
default. They are useful for explaining differences, but never contribute
directly to the score.

Large result documents are not attached to sensor states, which avoids
unnecessary Recorder database growth. Full history is stored in Home Assistant's
managed `.storage` system.

## Actions

| Action | Purpose |
|---|---|
| `benchmark.start` | Run a selected profile; supports the legacy `restart` flag |
| `benchmark.restart_and_run` | Restart and continue automatically |
| `benchmark.export` | Export v3 history as JSON and CSV |
| `benchmark.export_worldlist` | Export the latest rankable standard result |
| `benchmark.create_ranking_issue` | Prepare the export and show the ranking form |
| `benchmark.setup_dashboard` | Show ready-to-copy dashboard YAML |
| `benchmark.create_issue` | Show a privacy-safe support issue link |

Exports are written to:

```text
/config/benchmark_export.json
/config/benchmark_export.csv
/config/benchmark_worldlist_export.json
```

## Dashboard

A built-in-card dashboard is available at:

```text
lovelace/example_dashboard.yaml
```

You can also press **Show dashboard YAML** or call
`benchmark.setup_dashboard`.

## Public worldlist

1. Run the `standard` profile.
2. Press **Export ranking payload**.
3. Press **Prepare ranking submission**.
4. Review and paste `/config/benchmark_worldlist_export.json` into the issue
   form.

The public builder:

- accepts only protocol v3 standard results;
- validates required sample counts and finite latency values;
- rejects unsupported protocol or score versions;
- deduplicates result IDs;
- recalculates all scores server-side;
- safely escapes public table metadata;
- includes only open issues with the `ranking` label.

The generated data is available in
[`docs/worldlist.json`](docs/worldlist.json) and
[`docs/worldlist.md`](docs/worldlist.md).

## Privacy

Everything runs locally. No result is uploaded automatically.

The optional worldlist export excludes:

- entity IDs and custom names;
- device names;
- IP addresses and hostnames;
- usernames and tokens;
- configuration paths;
- integration configuration.

It includes latency summaries and secondary comparison metadata such as Home
Assistant version, installation type, entity count, architecture, logical CPU
count, and total RAM. Always review the JSON before publishing it.

The payload itself contains no Home Assistant account identity, but a ranking
submission is a public GitHub issue and is therefore linked to the GitHub
account that submits it.

## Migration from version 2

- The version 2 hardware-oriented score is not mixed with version 3 history.
- Existing v2 history is preserved as `legacy_v2_history` in full exports.
- Old hidden JSON files are migrated once into Home Assistant storage and then
  removed.
- Removed CPU/disk entities are cleaned from the entity registry.
- Existing profile aliases and the `benchmark.start` restart flag remain
  compatible.

Version 3 scores are intentionally not comparable with version 2 scores.

## Development and validation

The repository includes:

- pure unit tests for statistics, scoring, validation, and worldlist security;
- Home Assistant config-flow and setup tests;
- Ruff linting and formatting checks;
- pytest statement and branch coverage with a mandatory 100% threshold;
- Hassfest validation;
- HACS repository validation;
- JSON and translation consistency checks.

Run locally:

```bash
# Python 3.13 or newer
python -m pip install -r requirements_test.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

The test suite covers normal operation, cancellation, concurrent starts,
restart continuation, storage migration, export failures, entity state,
platform fallbacks, malformed measurements, and every registered action. CI
publishes a machine-readable coverage report for every supported Home Assistant
test generation.

## Limitations

- A benchmark is a controlled sample, not a guarantee about every automation or
  third-party integration.
- Normal background activity is intentionally visible in the Fluidity Score.
- P95/P99 results can vary; compare several standard runs and pay attention to
  the confidence sensor.
- Database-specific Recorder performance is not part of score v3. It may be
  added later as a separate, versioned subscore.
- The state-machine test creates short-lived internal state changes. They are
  removed after the run, but Recorder may retain their historical events.
- Worldlist validation detects malformed payloads and recalculates scores, but
  it cannot cryptographically prove that submitted measurements came from an
  unmodified Home Assistant installation.
- Hardware metadata explains results but cannot prove causation.

## License

MIT — see [LICENSE](LICENSE).

Contributions are covered by [CONTRIBUTING.md](CONTRIBUTING.md). Please report
security issues according to [SECURITY.md](SECURITY.md).
