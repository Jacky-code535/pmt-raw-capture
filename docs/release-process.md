# Release Process

Version 0.5.0-dev is a public development preview. The latest packaged release
remains v0.4.3 until the full-tool release gates and review are complete.

## Local Gates

```bash
python3 -m unittest discover -s tests -v
bash scripts/build-package.sh
stage=$(mktemp -d)
tar -xzf dist/pmt-raw-capture-0.5.0-dev.tar.gz -C "$stage"
cd "$stage/pmt-raw-capture-0.5.0-dev"
python3 -m unittest discover -s tests -v
bash scripts/smoke_test.sh
```

Review the tar member list: no platform XML, measurement scripts, run results,
caches, credentials, private repository references or EDP source files. Only original
synthetic XML fixtures are included.

CI uses synthetic data and does not initialize the private submodule. The manual
package workflow validates and stores a tool-only workflow artifact; it does not
create a GitHub Release. Local hardware replay evidence stays outside this repository.

## Approved Publication

After approval, update VERSION, the collector version constant and release notes;
run all local gates and the supported Python CI matrix; review the exact source
diff and dependency pin; then publish the approved tool archive and verify its link.
Updating the platform pin is a separate reviewed change requiring run-scoped
validation and representative payload replay. Do not use an unpinned remote HEAD.

No open-source license has been selected for this project. This workflow does not
grant redistribution rights to the tool or internal platform data. License and
distribution scope must be approved before external release.