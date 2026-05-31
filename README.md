# Home Assistant Benchmark

<p align="center">
  <img src="https://brands.home-assistant.io/_/homeassistant/logo.png" alt="Home Assistant" width="120">
</p>

<p align="center">
  <strong>Measure. Compare. Improve.</strong><br>
  A clean and practical benchmark integration for Home Assistant.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-2.1.0-blue">
  <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-orange">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-yellow">
  <img alt="Status" src="https://img.shields.io/badge/status-beta-important">
</p>

---

## What is Home Assistant Benchmark?

**Home Assistant Benchmark** is a custom integration that measures the real-world performance of your Home Assistant instance and exposes the results as sensors.

It is designed to help you compare different systems such as:

- Raspberry Pi
- Home Assistant Green
- Home Assistant Yellow
- Mini PCs / NUCs
- Virtual machines
- Docker / Container installations
- Proxmox setups

The integration creates a unified **Benchmark Score from 0 to 10,000** and also shows the individual results for CPU, disk, template rendering and restart time.

---

## Preview

> Dashboard example is included in `lovelace/example_dashboard.yaml`.

```yaml
sensor.benchmark_score
sensor.benchmark_progress
sensor.benchmark_cpu_performance
sensor.benchmark_disk_write
sensor.benchmark_disk_read
sensor.benchmark_template_render
sensor.benchmark_restart_time
```

<p align="center">
  <img src="https://www.home-assistant.io/images/screenshots/lovelace.png" alt="Example Lovelace Dashboard" width="720">
</p>

---

## Highlights

| Feature | Description |
|---|---|
| Benchmark Score | One clear score from 0 to 10,000 |
| Profiles | `light`, `normal`, `heavy` |
| CPU Benchmark | Measures calculation throughput |
| Disk Benchmark | Measures read and write speed in MB/s |
| Template Benchmark | Measures Home Assistant template rendering speed |
| Restart Benchmark | Measures real Home Assistant restart duration |
| Progress Sensor | Live progress with ASCII progress bar attribute |
| Export | JSON and CSV export service |
| Dashboard Helper | Service that outputs ready-to-copy Lovelace YAML |
| Diagnostics | Includes diagnostic data for troubleshooting |

---

## Benchmark Profiles

| Profile | Use case | Runtime | Intensity |
|---|---|---:|---:|
| `light` | Quick check | Short | Low |
| `normal` | Recommended default | Medium | Balanced |
| `heavy` | More stable comparison | Longer | High |

Recommendation: Use **normal** for regular tests and **heavy** when comparing different hardware.

---

## Sensors

After setup, the integration exposes sensors like:

| Entity | Description |
|---|---|
| `sensor.benchmark_score` | Main benchmark score |
| `sensor.benchmark_progress` | Current benchmark progress |
| `sensor.benchmark_status` | Running / idle |
| `sensor.benchmark_active_profile` | Last used benchmark profile |
| `sensor.benchmark_cpu_performance` | CPU operations per second |
| `sensor.benchmark_disk_write` | Disk write speed |
| `sensor.benchmark_disk_read` | Disk read speed |
| `sensor.benchmark_template_render` | Template rendering time |
| `sensor.benchmark_restart_time` | Measured restart time |
| `sensor.benchmark_last_run` | Last benchmark timestamp |

The main score sensor also contains detailed attributes:

- scoring formula
- scoring weights
- normalized scoring values
- raw benchmark results
- system information
- dashboard YAML
- last export paths

---

## Services

### Start Benchmark

```yaml
service: benchmark.start
data:
  profile: normal
  restart: false
```

Available profiles:

```yaml
light
normal
heavy
```

### Restart Benchmark

```yaml
service: benchmark.start
data:
  profile: normal
  restart: true
```

This prepares the restart measurement and restarts Home Assistant.

### Export Results

```yaml
service: benchmark.export
```

Creates:

```text
/config/benchmark_export.json
/config/benchmark_export.csv
```

### Generate Dashboard YAML

```yaml
service: benchmark.setup_dashboard
```

This shows a ready-to-copy Lovelace dashboard configuration as a persistent notification.

---

## Installation

### HACS custom repository

1. Open HACS.
2. Go to **Integrations**.
3. Open the three-dot menu.
4. Select **Custom repositories**.
5. Add this repository:

```text
https://github.com/Jarnsen/hacs-homeassistant-benchmark
```

6. Category: **Integration**
7. Install **Home Assistant Benchmark**
8. Restart Home Assistant.
9. Add the integration from **Settings → Devices & services**.

### Manual installation

Copy the folder:

```text
custom_components/benchmark
```

to:

```text
/config/custom_components/benchmark
```

Then restart Home Assistant.

---

## Dashboard

A dashboard example is included here:

```text
lovelace/example_dashboard.yaml
```

It uses standard Home Assistant cards and can optionally be combined with:

- `custom:button-card`
- `custom:mini-graph-card`

---

## Scoring

The score is calculated from weighted normalized values:

```text
score = 10000 * (0.35*cpu + 0.20*disk_write + 0.20*disk_read + 0.15*template + 0.10*restart)
```

The formula is also exposed as an attribute of `sensor.benchmark_score`.

| Score | Meaning |
|---:|---|
| 0 - 3,499 | Slow / warning range |
| 3,500 - 5,999 | Usable |
| 6,000 - 7,999 | Good |
| 8,000 - 10,000 | Very fast |

---

## Example use cases

- Compare Raspberry Pi vs Mini PC
- Check whether an SSD upgrade improves Home Assistant
- Compare VM performance before and after resource changes
- Track performance over time
- Detect slow storage
- Benchmark before and after large Home Assistant changes

---

## Current status

Version **2.1.0** is a larger internal rewrite.

Included:

- new benchmark engine
- new profile system
- JSON / CSV export
- dashboard helper
- progress sensor
- restart benchmark
- diagnostics update
- German and English translations

> This version should be tested carefully after installation. Please check Home Assistant logs after the first restart.

---

## Roadmap

Planned ideas for future versions:

- visual leaderboard export
- local benchmark history graph
- optional anonymous comparison payload
- better dashboard package
- automatic weekly benchmark automation
- more detailed storage detection
- optional recorder benchmark

---

## Credits

Created by **Jarnsen** for the Home Assistant community.

If this project helps you compare or improve your Home Assistant setup, a star on GitHub is appreciated.
