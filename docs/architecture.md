# Architecture

The default pipeline is start -> analyze: raw -> decoded.csv -> metrics.csv -> dashboard.html.
Verification and exact XML validation are internal steps. Pack/unpack are optional
transport helpers; archive, compare and extended analysis remain compatibility paths.

| Package | Responsibility |
| --- | --- |
| `pmt.capture` | sysfs discovery/readout, scheduling, CPU affinity, atomic gzip writes, run verification, JSON settings |
| `pmt.decode` | registry selection, XML layout parsing, bit extraction, restricted arithmetic, unit labels |
| `pmt.process` | explicit counter reconstruction, finite-value statistics, SQLite staging, event alignment |
| `pmt.export` | CSV writers, endpoint/topology mapping, validated archive extraction |
| `pmt.pipeline` | immutable input handling, XML freezing, output staging and provenance |
| `pmt.metrics` | streaming long-form metric export using explicit GNR definitions |
| `pmt.report` | shared metric evaluation; legacy rollups and Excel implementation |
| `pmt.core_view` | CSV-only standalone HTML with inline JavaScript/SVG |
| `pmt.cli` | commands and collector lifecycle |

The root executable works from a checkout or an extracted package. Top-level legacy
Python modules remain compatibility imports; the implementation lives in `src/pmt`.
The tool uses Python's standard library and Linux sysfs. Analysis is offline after
XML provisioning and does not fetch schema updates while running.

## Contracts

- Preserve `intel-pmt-local-bulk/v1` envelopes and base64 payload bytes.
- Select schemas by exact GUID and byte size, never by a platform label alone.
- Do not infer physical cores from endpoint or aggregator identifiers.
- Do not silently turn counters into rates without an explicit policy.
- Keep complete XML observations separate from derived metrics, both in long form.
- Retain interval validity without inferring hardware health; do not generate extra summary CSVs by default.
- Publish analysis only after all snapshots succeed; failed staging directories are removed.
- Record input hashes, frozen XML, source hashes and the available platform Git revision.

Scope views retain individual series; they do not sum incompatible measurements.
EDP-like statistics describe output organization, not identical EDP formulas or
normalization. Event correlation is time-based evidence, not automatic fault diagnosis.

## Tests

The existing flat unittest suite is retained for compatibility. `test_native_decode.py`
covers schema/bit/formula behavior, `test_unpack.py` covers archive rejection, and
`test_integrated_workflow.py` runs actual CLI subprocesses from capture through analysis,
comparison and event alignment. Fixtures are original synthetic data. Hardware
qualification and performance measurements are separate from these tests.