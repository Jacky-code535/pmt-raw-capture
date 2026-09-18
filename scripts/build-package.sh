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
    VERSION README.md REQUIREMENTS.md SUPPORT.md docs/usage.md docs/data-format.md
    docs/changelog.md docs/service.md
    pmt-capture src/pmt_capture_cli.py src/pmt_bulk_capture.py
    src/pmt_analysis.py src/pmt_postprocess.py docs/offline.md
    service/run.sh service/install.sh service/uninstall.sh
    service/configs/lab-host.conf.example service/systemd/pmt-bulk-capture@.service
    service/field-kit/start-capture.sh service/field-kit/show-progress.sh
    service/field-kit/pause-capture.sh service/field-kit/resume-capture.sh service/field-kit/pack-results.sh
    service/field-kit/lib/common.sh service/field-kit/lib/schedule.sh service/field-kit/lib/run_status.py
    config/defaults.json examples/capture_config.json
    docs/architecture.md docs/platform-data.md
    docs/compatibility.md
)
while IFS= read -r -d '' file; do
    files+=("${file#"${ROOT}/"}")
done < <(find "${ROOT}/src/pmt" -type f -name '*.py' -print0)
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
    "${stage}/service/field-kit/"*.sh

archive="${DIST}/${NAME}.tar.gz"
tar -C "${temporary}" -czf "${archive}" "${NAME}"

printf '%s\n' "${archive}"
