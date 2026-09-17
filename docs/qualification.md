# Hardware Qualification

## v0.5.1 Full Bundle Verification

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
does not claim support for every platform or XML revision. Platform XML, raw
captures, decoded CSV files, host addresses and internal paths are not included
in this repository or release package.