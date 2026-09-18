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
    VERSION README.md SUPPORT.md docs/usage.md docs/data-format.md
    docs/development.md docs/changelog.md docs/service.md .gitignore .github/workflows/test.yml
    pmt-capture src/pmt_capture_cli.py src/pmt_bulk_capture.py
    src/pmt_analysis.py src/pmt_postprocess.py docs/offline.md
    service/run.sh service/install.sh service/uninstall.sh scripts/build-package.sh
    service/configs/lab-host.conf.example service/systemd/pmt-bulk-capture@.service
    service/field-kit/start-capture.sh service/field-kit/show-progress.sh
    service/field-kit/pause-capture.sh service/field-kit/resume-capture.sh service/field-kit/pack-results.sh
    service/field-kit/lib/common.sh service/field-kit/lib/schedule.sh service/field-kit/lib/run_status.py
    tests/test_pmt_bulk_capture.py tests/test_engineer_cli.py tests/test_field_kit.py
    tests/test_pmt_analysis.py tests/test_pmt_postprocess.py
    tests/test_native_decode.py tests/test_unpack.py
    tests/test_integrated_workflow.py config/defaults.json examples/capture_config.json
    scripts/smoke_test.sh scripts/build-full-package.sh
    docs/architecture.md docs/platform-data.md docs/release-process.md
    docs/compatibility.md
    RELEASE_NOTES.md .github/workflows/release.yml
)
while IFS= read -r -d '' file; do
    files+=("${file#"${ROOT}/"}")
done < <(find "${ROOT}/src/pmt" -type f -name '*.py' -print0)
while IFS= read -r -d '' file; do
    files+=("${file#"${ROOT}/"}")
done < <(find "${ROOT}/tests/fixtures" -type f \( -name '*.xml' -o -name '*.json' \) -print0)
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
    "${stage}/scripts/build-full-package.sh" \
    "${stage}/scripts/smoke_test.sh" \
    "${stage}/service/field-kit/"*.sh

archive="${DIST}/${NAME}.tar.gz"
tar -C "${temporary}" -czf "${archive}" "${NAME}"

printf '%s\n' "${archive}"
