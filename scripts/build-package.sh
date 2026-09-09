#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
readonly NAME="pmt-raw-capture-${VERSION}"
readonly DIST="${ROOT}/dist"

temporary="$(mktemp -d)"
trap 'rm -rf -- "${temporary}"' EXIT
stage="${temporary}/${NAME}"

mkdir -p "${stage}" "${DIST}"
files=(
    VERSION README.md docs/usage.md docs/data-format.md
    docs/development.md docs/changelog.md docs/service.md .gitignore .github/workflows/test.yml
    pmt-capture src/pmt_capture_cli.py src/pmt_bulk_capture.py
    service/run.sh service/install.sh service/uninstall.sh scripts/build-package.sh
    service/configs/lab-host.conf.example service/systemd/pmt-bulk-capture@.service
    service/field-kit/start-capture.sh service/field-kit/show-progress.sh
    service/field-kit/pause-capture.sh service/field-kit/resume-capture.sh service/field-kit/pack-results.sh
    service/field-kit/lib/common.sh service/field-kit/lib/schedule.sh service/field-kit/lib/run_status.py
    tests/test_pmt_bulk_capture.py tests/test_engineer_cli.py tests/test_field_kit.py
)
if [[ -f "${ROOT}/LICENSE" ]]; then
    files+=(LICENSE)
fi
for file in "${files[@]}"; do
    mkdir -p "${stage}/$(dirname "${file}")"
    cp "${ROOT}/${file}" "${stage}/${file}"
done
chmod 0755 \
    "${stage}/pmt-capture" \
    "${stage}/service/"*.sh \
    "${stage}/scripts/build-package.sh" \
    "${stage}/service/field-kit/"*.sh

archive="${DIST}/${NAME}.tar.gz"
tar -C "${temporary}" -czf "${archive}" "${NAME}"

printf '%s\n' "${archive}"
