# Changelog

All notable changes are documented in this file.

## 3.0.0

### Changed

- Replaced the hardware-oriented v2 score with a Home Assistant-centric latency
  protocol.
- Added separate HA Core, Fluidity, and overall HA Performance scores.
- Added P50/P95/P99 summaries for the event loop, state machine, event bus,
  service dispatcher, and template engine.
- Removed CPU and disk throughput from scoring.
- Moved restart recovery time to a non-scoring diagnostic measurement.
- Added confidence classification and ranking eligibility metadata.
- Standardized the loaded phase at 250 internal HA service calls per second.
- Added exact, protocol-validated sample counts for comparable ranking runs.
- Replaced hidden JSON persistence with Home Assistant managed storage.
- Added automatic continuation after a restart benchmark.
- Reduced recorder-heavy sensor attributes.
- Rebuilt sensors, buttons, translations, dashboard, diagnostics, and actions.
- Added server-side score recalculation and strict worldlist validation.
- Added versioned exports and safe migration of version 2 history.

### Added

- Quick, standard, and extended profiles.
- HACS metadata.
- Ruff, pytest, Hassfest, and HACS validation workflows.
- English and German product documentation.
- Structured bug and ranking issue forms.
- Complete behavior, lifecycle, storage, entity, engine, and failure-path test
  suites with enforced 100% statement and branch coverage.
- Per-version XML coverage artifacts in GitHub Actions.

### Compatibility

- Version 2 profile names remain accepted as aliases.
- `benchmark.start` retains the legacy `restart` field.
- Version 2 scores are preserved only as legacy export data and are never mixed
  with version 3 rankings.
