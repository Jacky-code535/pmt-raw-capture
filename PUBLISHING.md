# Private Repository and Release Handoff

## Approval First

Confirm ownership and employer/IP authorization before uploading code or PMT
information, including to a personal private repository. The intended repository
is `Jacky-code535/pmt-raw-capture`, with private visibility and access limited to
approved colleagues. Do not change visibility or redistribute without approval.

No open-source license has been selected. Access to this repository does not
grant general reuse or redistribution rights. If the authorized owner approves
a license, add its text as `LICENSE`; the build script will include it.

## Use the Clean Source Package

The development directory may contain private historical results and local
decoder work. **Do not upload that directory wholesale.** Build the allowlisted
package, then extract it into a new empty directory outside the development tree:

```bash
./build-package.sh
mkdir -p ../pmt-release-staging
tar -xzf dist/pmt-system-debug-0.4.2.tar.gz -C ../pmt-release-staging
cd ../pmt-release-staging/pmt-system-debug-0.4.2
python3 -m unittest discover -s tests -v
```

The package contains CLI/core code, optional service/menu scripts, generic
configuration, one main usage README, optional service and data-format references,
maintainer notes, tests, `.gitignore`, and GitHub Actions. It excludes duplicate
quick-start/public/full guides,
collected results, exports, binaries, platform-specific configurations, replay
assets, Go decoder sources and their local dependency paths.

The build also writes `dist/pmt-system-debug-0.4.2.tar.gz.sha256`; attach both
files to the release. From `dist/`, check it with
`sha256sum -c pmt-system-debug-0.4.2.tar.gz.sha256`.
After adding an approved LICENSE, rebuild the archive and checksum.
Review every file before uploading, including notes
and metadata in any examples you add. The allowlist is a packaging boundary,
not an automated legal or confidentiality review.

## Upload After Review

Create an empty **private** repository on GitHub. In the clean extracted directory, run the
following yourself after approval, replacing the remote with your repository:

```bash
git init -b main
git add .
git diff --cached --stat
git diff --cached
git commit -m "Initial raw PMT collector release"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Wait for CI to pass. Create a `v0.4.2` release and attach the tarball and checksum.
State which platform/kernel and actual hardware workflows you tested. Do not
describe synthetic tests as hardware qualification. No commit, branch, remote,
or public push is performed by the build script.

The included CI runs on Python 3.7, 3.10 and 3.13, tests an extracted distribution,
and checks the checksum. A root-only menu regression runs separately with sudo.
Synthetic tests do not qualify real PMT hardware, decoder compatibility,
systemd installation, reboot recovery or sustained disk usage.

Invite only approved collaborators, with read access where supported. An owner
must decide invitations; do not embed passwords or tokens in commands, source,
issues or release notes. Experiments and raw results belong in a separately
approved data-transfer channel, not in this repository or release assets.

## Contribution Checks

Use synthetic inputs in regression tests; do not submit real raw captures or
machine-specific secrets. Preserve raw format compatibility or explicitly
version changes. Run `python3 -m unittest discover -s tests -v` and test the
extracted archive before releasing. If adding a public file, update both the
build allowlist and `.gitignore` as appropriate.