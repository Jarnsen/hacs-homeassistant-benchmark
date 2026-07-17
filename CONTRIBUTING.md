# Contributing

Bug reports and focused pull requests are welcome.

## Development

Use Python 3.13 or newer:

```bash
python -m pip install -r requirements_test.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

The CI matrix tests the minimum supported Home Assistant generation and the
current Home Assistant release used by the test harness. Statement and branch
coverage must both remain at 100%. Coverage exclusions are accepted only for
genuinely unreachable code and require an explanation in the pull request.

## Benchmark protocol changes

Results are comparable only when the protocol and scoring formula are fixed.
Changes to any of the following require explicit review and normally a new
protocol or score version:

- sample counts or timing;
- controlled workload;
- measured Home Assistant pipelines;
- normalization thresholds or weights;
- ranking validation rules.

Do not add hardware throughput directly to the HA Performance Score. Hardware
belongs in secondary comparison metadata.

## Pull requests

- Keep changes narrowly scoped.
- Add or update tests.
- Update `README.md`, `README.de.md`, and `CHANGELOG.md` when behavior changes.
- Do not include real Home Assistant configuration, tokens, hostnames, or
  private diagnostics.
