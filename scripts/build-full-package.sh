#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
readonly PLATFORM_ROOT="${PMT_PLATFORM_DATA_ROOT:-${ROOT}/platform-data}"
readonly PLATFORM_COMMIT="${PMT_PLATFORM_DATA_COMMIT:-df82b1741dec619300707881114f6b17b5204f60}"
readonly NAME="pmt-raw-capture-${VERSION}"

git -C "${PLATFORM_ROOT}" cat-file -e "${PLATFORM_COMMIT}^{commit}"
if ! git -C "${PLATFORM_ROOT}" diff --quiet "${PLATFORM_COMMIT}" -- License Readme.md xml; then
    echo "platform data differs from ${PLATFORM_COMMIT}; commit or select the approved revision" >&2
    exit 1
fi

"${ROOT}/scripts/build-package.sh" >/dev/null
temporary="$(mktemp -d)"
trap 'rm -rf -- "${temporary}"' EXIT
tar -xzf "${ROOT}/dist/${NAME}.tar.gz" -C "${temporary}"
stage="${temporary}/${NAME}"
mkdir -p "${stage}/bundled-platform-data"
git -C "${PLATFORM_ROOT}" archive "${PLATFORM_COMMIT}" License Readme.md xml \
    | tar -x -C "${stage}/bundled-platform-data"
(cd "${stage}/bundled-platform-data" &&
    find License Readme.md xml -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)

cat >"${stage}/bundled-platform-data/SOURCE.txt" <<EOF
Intel PMT platform data approved for this full package
Commit: ${PLATFORM_COMMIT}
Source: approved Intel platform-data repository
Registry: bundled-platform-data/xml/pmt.xml
EOF

cat >"${stage}/BUNDLED_PLATFORM_DATA.md" <<EOF
# Bundled Intel PMT Platform Data

This full package includes the Intel PMT XML registry at commit
\`${PLATFORM_COMMIT}\`. \`validate-platform\` and \`analyze\` use the bundled
registry automatically when \`--metadata\` is omitted. An explicit
\`--metadata\` path takes precedence. \`bundled-platform-data/SHA256SUMS\`
covers every supplied platform-data file.

The GNR compatibility matrix contains seven hardware-validated schemas. The
complete registry contains 258 mappings; 220 schemas load with this decoder and
38 currently have definition-level blockers. Bundling the complete registry does
not imply that every mapped platform has passed qualification.
EOF

archive="${ROOT}/dist/${NAME}.tar.gz"
temporary_archive="${archive}.tmp"
tar -C "${temporary}" -czf "${temporary_archive}" "${NAME}"
mv "${temporary_archive}" "${archive}"
(cd "${ROOT}/dist" && sha256sum "${NAME}.tar.gz" >"${NAME}.tar.gz.sha256")
printf '%s\n' "${archive}"