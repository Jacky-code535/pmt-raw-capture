# Raw Bulk Format v1

`FormatVersion` is `intel-pmt-local-bulk/v1`. Each snapshot is UTF-8 JSON inside
gzip. All numeric payload bytes are preserved, including sentinel values.
There is no cryptographic integrity scheme. The `TelemetryData` envelope uses
common Redfish-style fields but is not a firmware-atomic Redfish snapshot.

## Snapshot

```json
{
  "FormatVersion": "intel-pmt-local-bulk/v1",
  "Capture": {
    "ToolVersion": "0.4.2",
    "RunId": "trial-001",
    "Endpoint": "lab-host",
    "Sequence": 1,
    "StartedAt": "2026-01-01T00:00:00.000000Z",
    "FinishedAt": "2026-01-01T00:00:00.001000Z",
    "DurationMilliseconds": 1.0,
    "ExpectedAggregators": 1,
    "CapturedAggregators": 1,
    "Complete": true,
    "Errors": []
  },
  "TelemetryData": [{
    "Guid": "0x00001234",
    "Size": 4,
    "CollectionTimestamp": "1767225600",
    "attributes": {
      "AccessId": "telem1",
      "CapturedAt": "2026-01-01T00:00:00.000500Z",
      "Source": "local-sysfs"
    },
    "Data": "AAAAAA=="
  }]
}
```

`Sequence` is one-based and increases across resume. `Guid` is normalized lower
case hexadecimal with a `0x` prefix. `Size` counts raw bytes, not Base64 text or
compressed bytes. `CollectionTimestamp` is a Unix-seconds string; `CapturedAt`
retains UTC microsecond formatting. Read order follows numeric access IDs.
Timestamps are host observations, not hardware event timestamps.

An incomplete snapshot still contains successful region reads. `Errors`
describes read/discovery problems and `Complete` is false. It counts toward the
requested number of attempts. Do not silently treat partial data as a full sample.

## Task Metadata

`run.json` records RunId, Endpoint, initial ToolVersion, CreatedAt, UpdatedAt,
SysfsRoot, IntervalSeconds, RequestedSamples, Inventory, Machine, Experiment,
Workload, Note, status and file counts. `ExpectedDurationSeconds` is a planning
estimate (`interval * samples`), not measured first-to-last duration.
Process identity fields are operational metadata, not proof a collector is alive.

`manifest.ndjson` contains one JSON object per published snapshot: Sequence,
Filename, CompressedBytes, StartedAt, FinishedAt, DurationMilliseconds,
ExpectedAggregators, CapturedAggregators, Complete, ErrorCount. Resume can rebuild
this derived file from validated snapshots. Hidden temporary files are ignored.

`collector.log` is JSON Lines with Time and Event (`start`, `snapshot`, `stopped`,
`completed`, `failed`) plus event fields. `verification.json` records the latest
verification and the run's UpdatedAt value. `result.json` and `result.txt` are
export summaries, not the primary raw evidence.

Result export requires regular files. `pack` rejects symbolic links in the
snapshot directory or export inputs, including dangling links, even when
`--allow-partial` is used. Keep the run directory unchanged while exporting.
The advisory run lock coordinates this tool's commands; it cannot prevent
other programs or users from changing files.

## Decoder Handoff

1. Decompress all snapshots, order by Sequence, and retain the real time gaps.
2. Check Capture.Complete and Errors before interpreting each sample.
3. Match each region's GUID and Size to approved platform metadata.
4. Base64-decode Data, then apply the external decoder's field layout and units.
5. Retain metadata/decoder versions alongside the resulting time series.

Changing only the decoder must not require recollecting raw data. Compatibility
with a particular decoder must still be tested; this release contains no decoder.