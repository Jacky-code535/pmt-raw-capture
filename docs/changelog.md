# Changelog

## 0.4.3

- Reorganize the repository into src, docs, service, scripts and tests.
- Add a direct download link and a short capture workflow to the README.
- Rename the release archive to pmt-raw-capture-0.4.3.tar.gz.
- Remove the separate SHA checksum asset and setup step.
- Keep CLI commands, raw bulk v1 and installed data directories unchanged.

## 0.4.2

- Reject symbolic links in result export inputs, including the snapshots
  directory and dangling links, even for partial exports. Prevent a successful
  verification from producing an archive that silently omits linked snapshots.
- Add regression coverage for linked snapshots, directories and task files.
- Expand the colleague-facing README with private-repository access, checksum
  verification, acceptance criteria, permissions, handoff and troubleshooting.
- Generate a SHA-256 checksum alongside each allowlisted source archive.
- Preserve the raw bulk v1 format and existing command-line interface.

## 0.4.1

- Consolidate colleague-facing instructions in one Chinese README: environment,
  commands, parameters, result paths and optional script roles.
- Keep duplicate guides out of the distribution and update service installation
  to use the same document list. Preserve CLI, menu and raw bulk v1 compatibility.
- Explain command and option behavior in CLI help.
- Handle uninstall help without prompting and reject unknown arguments.
- Test the shell entrypoint from inventory through capture, packaging and dump;
  check version consistency and non-interactive script help.

## 0.4.0

- CLI-first inventory/start/status/stop/resume/verify/pack/dump commands.
- Explicit run directories, required sample count, optional detached operation.
- Resume from the stored plan; recover manifests and counts from saved snapshots.
- Per-run locking, PID-aware stop, responsive interval waits, direct event logs.
- Separate collection and verification status; locked exports and partial bundles.
- Fix inherited menu schedules and menu exit on command failure.
- Protect active services from installation; retain data during confirmed uninstall.
- Clean source packaging, generic examples, CI and public-facing documentation.
- Keep raw bulk v1 and the legacy core command interface; no collection-time
  decoding dependency or cryptographic integrity chain.