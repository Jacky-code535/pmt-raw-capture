# 0.5.0-dev Development Preview

- Built-in Python exact XML decoding replaces the mandatory external Go adapter.
- Capture, decode, processing and export are organized under `src/pmt`.
- Adds validated archive unpacking, explicit XML validation and JSON capture config.
- Preserves raw v1 snapshots, legacy command entrypoints and optional external decoding.
- Adds original synthetic end-to-end fixtures and package-level validation.

XML is supplied separately and is not distributed with this project. A representative
hardware replay does not establish qualification for every platform. No new hardware
overhead measurements are claimed for this refactored version. See
[release process](docs/release-process.md) and [platform data](docs/platform-data.md).