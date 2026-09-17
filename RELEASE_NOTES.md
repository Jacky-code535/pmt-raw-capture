# 0.5.0

- Built-in Python exact XML decoding replaces the mandatory external Go adapter.
- Capture, decode, processing and export are organized under `src/pmt`.
- Adds validated archive unpacking, explicit XML validation and JSON capture config.
- Preserves raw v1 snapshots, legacy command entrypoints and optional external decoding.
- Adds original synthetic end-to-end fixtures and package-level validation.
- Validated the packaged workflow on the AVC01 GNR reference host: 30 complete
	snapshots, 36 PMT regions per snapshot, seven exact GUID/size schema matches,
	and 962,940 valid decoded rows.

XML is supplied separately and is not distributed with this project. A representative
hardware run does not establish qualification for every platform. Fully expanded
CSV output can be much larger than the compressed capture; the qualification run
used about 1 GB for analysis from a roughly 1 MB raw run. See [qualification](docs/qualification.md),
[release process](docs/release-process.md) and [platform data](docs/platform-data.md).
