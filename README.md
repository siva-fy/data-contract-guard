# Data Contract Guard

**Catch schema drift and bad records before a CSV becomes somebody else's problem.**

[![CI](https://github.com/siva-fy/data-contract-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/siva-fy/data-contract-guard/actions/workflows/ci.yml)

A command-line quality gate with explicit JSON contracts, reproducible freshness
checks, machine-readable findings and an exit code suitable for CI. Python
standard library only.

## Quick start

Requires Python 3.11+.

~~~bash
git clone https://github.com/siva-fy/data-contract-guard.git
cd data-contract-guard
python3 demo.py
python3 -m unittest discover -s tests -v
~~~

The demo checks a valid dataset and a deliberately broken dataset. The broken
fixture produces **6 issues**: duplicate ID, negative amount, unsupported
currency, stale timestamp, fractional integer and future timestamp.

## Use it as a gate

~~~bash
python3 contracts.py examples/orders.csv examples/orders.contract.json \
  --now 2026-01-02T12:00:00Z

# Deliberately returns exit code 1:
python3 contracts.py examples/broken_orders.csv examples/orders.contract.json \
  --now 2026-01-02T12:00:00Z
~~~

Exit **0** means the dataset passed; **1** means validation findings were
reported. Configuration/file errors also fail the command rather than silently
passing. Supply `--now` explicitly so historical backfills and CI reruns use the
same reference time.

~~~mermaid
flowchart LR
  A[CSV] --> C[Header and row validation]
  B[JSON contract v1] --> C
  D[Explicit reference time] --> C
  C --> E[JSON findings]
  C --> F[Pass or fail exit code]
~~~

## Contract format

~~~json
{
  "version": 1,
  "allow_extra_columns": false,
  "columns": {
    "order_id": {"type": "string", "unique": true},
    "amount_minor": {"type": "integer", "min": 0},
    "loaded_at": {"type": "timestamp", "max_age_hours": 24}
  }
}
~~~

Supported types: `string`, `integer`, finite `number`, timezone-aware `timestamp`.
Fields are nonnullable by default. Rules include `unique`, numeric `min`/`max`,
`enum` for non-timestamp fields, regex `pattern`, and timestamp `max_age_hours`.
Unknown rule names fail closed to catch typos. Missing, unexpected and duplicate
headers, malformed rows and empty datasets also fail.

Findings carry a logical CSV record number (header = 1), column and error code.
Quoted multiline records count as one record. No raw field values are copied into
the report. Uniqueness is checked after conversion: integer `01` and `1` collide.
Freshness exactly at the maximum age passes; future timestamps fail separately.

## Scope and tradeoffs

This is a deliberately small contract dialect, not a JSON Schema implementation
or a replacement for a full data observability platform. Uniqueness sets and
findings are held in memory. There is no cross-table validation, sampling,
distributed execution or alert delivery. Contract files and regex patterns
should be trusted configuration. Extend with bounded reporting and streaming
uniqueness storage before using very large datasets.

[Demo output](examples/demo-output.txt) includes the exact error locations.
Tests exercise schema changes, freshness boundaries, type errors, nullability,
duplicate headers, malformed rows and invalid contracts. CI covers Python 3.11–3.13.

Original AI-assisted portfolio project with synthetic CSVs.
[Provenance](PROVENANCE.md) · [MIT license](LICENSE) ·
[Python CSV documentation](https://docs.python.org/3/library/csv.html)
