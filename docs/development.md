# Development

Current release: 0.6.0 GNR Edition.

## Tests

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Tests use synthetic PMT devices and temporary run directories. CI runs on Python
3.7, 3.10 and 3.13, including the extracted release package. Service installation
and hardware qualification are separate platform tests.

## Build

```bash
./scripts/build-package.sh
```

Output: `dist/pmt-raw-capture-0.6.0.tar.gz`. This source-only package omits platform data.
The approved release asset is built with `./scripts/build-full-package.sh`, which
adds the fixed platform-data XML registry and replaces the archive with the full package.

The archive uses the same layout as the repository. Its file list is defined in
`scripts/build-package.sh`; new distributed files must be added there. Generated
results, local configurations and caches are excluded.

Validate the extracted package:

```bash
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.6.0.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.6.0"
./pmt-capture --version
python3 -m unittest discover -s tests -v
```

## Release

1. Update `VERSION`, `TOOL_VERSION` and versioned documentation links.
2. Run tests and build the package.
3. Commit and push; wait for CI to pass.
4. Create the version tag and GitHub Release, attaching the `.tar.gz` from `dist/`.
5. Verify the README download link against the published asset.

## Distribution

Offline analysis defaults to the built-in `pmt.decode` package. No Go binary or
third-party Python package is required. The Full Bundle includes the fixed XML
registry described in [platform data](platform-data.md); explicit `--metadata`
still overrides it. Raw captures, EDP files and measurement results are excluded.

The optional `--decoder` compatibility path still accepts an external adapter:
one raw envelope on stdin, ordered `{index,result}` records on stdout, with exact
GUID/size confirmation. Optional `metrics[].known_invalid` is preserved.

Run `bash scripts/smoke_test.sh` for the hardware-independent integrated workflow.
The package builder recursively includes Python files under `src/pmt` and synthetic
fixtures under `tests/fixtures`; all other distributed files remain explicit.
Release authorization and dependency handling are described in
[release process](release-process.md).

This repository is public. No open-source license is currently assigned; source is
visible but no additional redistribution rights are granted. The approved Full Bundle
contains the fixed platform XML described in the release; raw captures are always shared separately.