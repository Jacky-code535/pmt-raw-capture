# Architecture

The command pipeline is capture -> pack -> unpack -> validate-platform -> analyze -> compare.
Analysis can also read an existing run directly. `archive` produces per-sample binary
payloads and a replayable copy of the original capture format.

| Package | Responsibility |
| --- | --- |
| `pmt.capture` | sysfs discovery/readout, scheduling, CPU affinity, atomic gzip writes, run verification, JSON settings |
| `pmt.decode` | registry selection, XML layout parsing, bit extraction, restricted arithmetic, unit labels |
| `pmt.process` | explicit counter reconstruction, finite-value statistics, SQLite staging, event alignment |
| `pmt.export` | CSV writers, endpoint/topology mapping, validated archive extraction |
| `pmt.pipeline` | immutable input handling, XML freezing, output staging and provenance |
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
- Keep original observations separate from validity-filtered series and summaries.
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