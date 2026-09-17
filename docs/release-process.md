# Release Process

Version 0.5.0 is the current packaged release. Its representative hardware
qualification is recorded in [qualification](qualification.md).

## Local Gates

```bash
python3 -m unittest discover -s tests -v
bash scripts/build-package.sh
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.5.0.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.5.0"
python3 -m unittest discover -s tests -v
bash scripts/smoke_test.sh
```

Review the tar member list: no platform XML, measurement scripts, run results,
caches, credentials, private repository references or EDP source files. Only original
synthetic XML fixtures are included.

CI uses synthetic data. The manual package workflow validates and stores a tool-only
workflow artifact; GitHub Releases are created separately after the gates pass.
Raw hardware data and platform XML stay outside this repository; only a sanitized
qualification summary is published.

## Approved Publication

After approval, update VERSION, the collector version constant and release notes;
run all local gates and the supported Python CI matrix; review the exact source
diff and dependency pin; then publish the approved tool archive and verify its link.
Updating the platform pin is a separate reviewed change requiring run-scoped
validation and representative payload replay. Do not use an unpinned remote HEAD.

No open-source license has been selected for this project. This workflow does not
grant redistribution rights to the tool or internal platform data. License and
distribution scope must be approved before external release.