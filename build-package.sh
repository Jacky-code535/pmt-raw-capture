#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly VERSION="$(tr -d '[:space:]' <"${ROOT}/VERSION")"
readonly NAME="pmt-system-debug-${VERSION}"
readonly DIST="${ROOT}/dist"

temporary="$(mktemp -d)"
trap 'rm -rf -- "${temporary}"' EXIT
stage="${temporary}/${NAME}"

mkdir -p "${stage}" "${DIST}"
files=(
    VERSION README.md DATA-FORMAT.md
    PUBLISHING.md CHANGELOG.md .gitignore .github/workflows/test.yml
    pmt-capture pmt_capture_cli.py pmt_bulk_capture.py run.sh install.sh uninstall.sh
    build-package.sh configs/lab-host.conf.example systemd/pmt-bulk-capture@.service
    field-kit/USER-GUIDE.zh-CN.md field-kit/start-capture.sh field-kit/show-progress.sh
    field-kit/pause-capture.sh field-kit/resume-capture.sh field-kit/pack-results.sh
    field-kit/lib/common.sh field-kit/lib/schedule.sh field-kit/lib/run_status.py
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
    "${stage}/pmt_bulk_capture.py" \
    "${stage}/run.sh" \
    "${stage}/install.sh" \
    "${stage}/uninstall.sh" \
    "${stage}/build-package.sh" \
    "${stage}/field-kit/"*.sh

archive="${DIST}/${NAME}.tar.gz"
tar -C "${temporary}" -czf "${archive}" "${NAME}"

pushd "${DIST}" >/dev/null
sha256sum "${NAME}.tar.gz" >"${NAME}.tar.gz.sha256"
popd >/dev/null

printf '%s\n' "${archive}"
printf '%s\n' "${archive}.sha256"
