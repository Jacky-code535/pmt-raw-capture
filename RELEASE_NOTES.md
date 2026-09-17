# 0.5.1 Full Bundle

- Built-in Python exact XML decoding replaces the mandatory external Go adapter.
- Capture, decode, processing and export are organized under `src/pmt`.
- Adds validated archive unpacking, explicit XML validation and JSON capture config.
- Preserves raw v1 snapshots, legacy command entrypoints and optional external decoding.
- Adds original synthetic end-to-end fixtures and package-level validation.
- Bundles the complete approved Intel PMT XML registry at platform-data commit
	`df82b1741dec619300707881114f6b17b5204f60`, including its Apache-2.0 license,
	source provenance and per-file SHA-256 manifest.
- Uses the bundled registry automatically for `validate-platform` and `analyze`;
	explicit `--metadata` remains available as an override.
- Validated the packaged workflow on the AVC01 GNR reference host: 30 complete
	snapshots, 36 PMT regions per snapshot, seven exact GUID/size schema matches,
	and 962,940 valid decoded rows.

A representative hardware run does not establish qualification for every platform. Fully expanded
CSV output can be much larger than the compressed capture; the qualification run
used about 1 GB for analysis from a roughly 1 MB raw run. See [qualification](docs/qualification.md),
[release process](docs/release-process.md) and [platform data](docs/platform-data.md).
