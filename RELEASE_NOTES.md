# 0.6.1 GNR Usability Update

- Adds root-level `REQUIREMENTS.md` as the single requirement and acceptance index.
- Rewrites the README as a clean-directory workflow from Full Bundle download
	through GNR capture, package handoff, exact XML validation and output checks.
- Clearly distinguishes the ready-to-run Full Bundle from source-only GitHub
	checkout/archive downloads, which require explicit `--metadata`.
- Publishes a separate SHA-256 file so users can verify the downloaded archive.
- Fixes `sudo pack` handoff: the result archive is mode 0640 and is returned to
	the original sudo user, allowing the documented non-root `unpack` step.
- Retains the 0.6.0 GNR decode, series, summary, Data Quality and SHC-boundary behavior.

The qualified GNR boundary remains the seven GUID/size schemas observed on AVC01;
XML presence alone is not a hardware support claim. See [requirements](REQUIREMENTS.md),
[compatibility](docs/compatibility.md) and [qualification](docs/qualification.md).
