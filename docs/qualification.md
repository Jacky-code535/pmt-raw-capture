# Hardware Qualification

## v0.6.1 README and Permission Verification

The v0.6.1 release-package workflow was exercised on AVC01 with separate privilege
contexts. User `intel` extracted and smoke-tested the package, root performed the
PMT operations with the sudo caller identity, and `intel` then unpacked, validated
and analyzed the result without elevated privileges.

| Check | Result |
| --- | --- |
| Download checksum file | Pass |
| Release-package XML presence and smoke | Pass; 2/2 tests |
| Capture completeness | 3/3 snapshots; 36/36 regions each |
| Sudo pack handoff | `0640 intel:intel`; readable by caller |
| XML matching | 7/7 observed GUID + Size schemas valid |
| Data Quality | 32,098 series; all had 3 valid, 0 invalid and 0 missing values |
| Non-root unpack and analysis | Pass |

This verifies the README's same-host path and closes the root-owned `0600` archive
problem present in v0.6.0. A source checkout requires an explicit `--metadata`
path; only the release package supplies the default registry.

## v0.6.0 GNR Edition Release Verification

The v0.6.0 final release package was transferred to AVC01 and exercised using
the same commands documented for users: inventory/capture, verify, pack, unpack,
run-scoped XML validation and analysis. No explicit `--metadata` path was used.

| Check | Result |
| --- | --- |
| Capture completeness | 3/3 snapshots; 36/36 regions each |
| Snapshot integrity | 3/3 manifest SHA-256 values present and verified |
| XML matching | 7/7 observed GUID + Size schemas valid |
| Decoded output | 96,294 rows |
| Data Quality | 32,098 series; every series expected 3 and had 3 valid values |
| Invalid or missing series values | 0 invalid; 0 missing |
| Pack and safe unpack verification | Pass |

This short run is the release-artifact acceptance gate. The longer 30-snapshot
run below remains the representative duration and output-volume qualification.

## v0.5.1 Release Package Verification

The final package includes all 798 tracked platform-data files from commit
`df82b1741dec619300707881114f6b17b5204f60`. On AVC01, the package automatically
selected its bundled registry without `--metadata`: 3/3 snapshots were complete,
all seven observed GUID/size schemas validated, and 96,294 decoded rows were valid.

The full registry contains 258 mappings. The decoder loads 220 schemas; 38 have
definition-level blockers. These unrelated definitions do not affect the seven
schemas observed in the AVC01 qualification run.

## AVC01 GNR End-to-End Run

On 2026-09-17, the v0.5.0 candidate package built from commit `813d88e` was
exercised on the AVC01 GNR reference host using its installed platform XML.
The run used 30 samples at a 2-second interval and required all 36 discovered
PMT regions in every snapshot.

The validated path was:

```text
package extraction -> package smoke test -> inventory -> capture -> verify
-> pack -> safe unpack -> exact XML validation -> built-in decode -> statistics
```

| Check | Result |
| --- | --- |
| Package SHA-256 preserved across transfer | Pass |
| Package smoke test | 2/2 pass |
| Capture completeness | 30/30 snapshots; 36/36 regions each |
| Raw records | 1,080 |
| Per-snapshot capture duration | 153.727-166.193 ms |
| XML matching | 7/7 observed GUID + Size schemas valid |
| Decoded output | 962,940 rows; 32,098 rows in every sequence |
| Series validity | 962,940 `valid` rows |
| Summary coverage | 32,098 series, each with 30 valid values |
| Pack and safe unpack verification | Pass |

The compressed raw run was about 1 MB and its shareable archive was about
0.85 MB. Fully expanded CSV analysis was about 1 GB because multiple long-form
views retain each decoded observation. Capacity planning should therefore use
the expanded output size rather than only the capture archive size.

This is representative qualification for the tested GNR inventory and XML. It
does not claim support for every platform or XML revision. Raw captures, decoded
CSV files, host addresses and internal paths are not included in the repository
or release package. The approved XML registry is included only in the release package;
its content is not committed to this source repository.