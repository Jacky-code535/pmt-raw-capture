# Release Process

Version 0.6.3 GNR Edition is the current packaged release. Representative hardware
validation records are maintained outside the public repository.

## Local Gates

```bash
python3 -m unittest discover -s tests -v
bash scripts/build-full-package.sh
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.6.3.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.6.3"
./pmt-capture --version
./pmt-capture --help >/dev/null
python3 -m compileall -q src
(cd bundled-platform-data && sha256sum -c SHA256SUMS)
```

Review the tar member list: only the fixed approved `License`, `Readme.md` and
`xml/` tree may come from platform data. Measurement scripts, run results, caches,
credentials, alternate XML trees and EDP source files remain excluded.

CI uses synthetic data and builds the developer package. The approved release package
is built in the authorized environment from the pinned platform-data commit, then
validated on representative hardware before upload. Raw hardware data stays outside
this repository and Release.

## Approved Publication

After approval, update VERSION, the collector version constant and release notes;
run all local gates and the supported Python CI matrix; review the exact source
diff and dependency pin; then publish the approved tool archive and verify its link.
Updating the platform pin is a separate reviewed change requiring run-scoped
validation and representative payload replay. Do not use an unpinned remote HEAD.

No open-source license has been selected for this project. This workflow does not
grant redistribution rights to the tool or internal platform data. License and
distribution scope must be approved before external release.