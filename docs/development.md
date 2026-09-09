# Development

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

Output: `dist/pmt-raw-capture-0.4.3.tar.gz`.

The archive uses the same layout as the repository. Its file list is defined in
`scripts/build-package.sh`; new distributed files must be added there. Generated
results, local configurations and caches are excluded.

Validate the extracted package:

```bash
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.4.3.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.4.3"
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

This repository is private. No open-source license is currently assigned;
external redistribution requires the owner's approval. Raw captures are shared
through the team's data-transfer channel, separately from source releases.