# Release Process

Version 0.8.0 GNR Edition is the packaged release. Representative hardware
validation records are maintained outside the public repository.

## Local Gates

```bash
python3 -m unittest discover -s tests -v
bash scripts/build-full-package.sh
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.8.0.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.8.0"
./pmt-capture --version
./pmt-capture --help >/dev/null
python3 -m compileall -q src
(cd bundled-platform-data && sha256sum -c SHA256SUMS)
```

Review the tar member list: only the fixed approved `License`, `Readme.md`, seven
GNR schema sets and their generated subset registry may come from platform data. Measurement scripts, run results, caches,
credentials, alternate XML trees and EDP source files remain excluded.

CI uses synthetic data and builds the developer package. The approved release package
is built in the authorized environment from the pinned platform-data commit, then
validated on representative hardware before upload. Raw hardware data stays outside
this repository and Release.

Run `python3 scripts/qualify-report-scale.py --samples 600 --output-root /path/to/new-directory`
on an offline host. It supplies every configured metric input and checks 10,828,800
long-form rows, with no Excel dependency. It does not independently qualify 600 raw
hardware snapshots or the platform's histogram units. Real raw replay, desktop/mobile
browser checks and release-asset extraction remain separate gates. State clearly
whether fresh hardware acquisition was performed or existing raw was replayed.

## Approved Publication

After approval, update VERSION, the collector version constant and release notes;
run all local gates and the supported Python CI matrix; review the exact source
diff and dependency pin; then publish the approved tool archive and verify its link.
Updating the platform pin is a separate reviewed change requiring run-scoped
validation and representative payload replay. Do not use an unpinned remote HEAD.

No open-source license has been selected for this project. This workflow does not
grant redistribution rights to the tool or internal platform data. License and
distribution scope must be approved before external release.