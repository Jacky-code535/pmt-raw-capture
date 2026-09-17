# 0.6.0 GNR Edition

- Product name is now **Intel PMT Capture and Analysis Toolkit**. Repository,
	archive and CLI names remain compatible with existing scripts.
- Focuses the supported workflow on GNR: inventory, capture, verify, pack,
	unpack, exact XML validation, analysis and summary.
- Adds a SHA-256 value for every new compressed snapshot and verifies it before
	packaging or analysis. Existing v1 runs without this optional field remain readable.
- Adds `data-quality.csv` with expected, observed, valid, invalid and missing
	counts plus valid rate and first/last timestamps for each series.
- Keeps decode strict after run-scoped XML validation. Unsupported definitions
	fail explicitly instead of producing a partial result with silently missing metrics.
- Keeps SHC as a documented future integration boundary with no runtime dependency.
- Bundles the approved registry at platform-data commit
	`df82b1741dec619300707881114f6b17b5204f60` with source provenance and SHA-256 manifest.
- Validates the release workflow on AVC01: 3/3 complete snapshots, 3/3 snapshot
	hashes, seven exact schemas, 96,294 decoded rows and 32,098 complete quality series.

The qualified GNR boundary is the seven GUID/size schemas observed on AVC01; XML
presence alone is not a hardware support claim. Fully expanded CSV can be much
larger than the compressed capture. See [compatibility](docs/compatibility.md),
[qualification](docs/qualification.md) and [release process](docs/release-process.md).
