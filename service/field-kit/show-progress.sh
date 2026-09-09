#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root

if ! read_run_state; then
    say_err "尚未安装或未开始采集。请先运行: sudo ${SCRIPT_DIR}/start-capture.sh"
    exit 1
fi

active_flag=0
if service_is_active "${PMT_ACTIVE_INSTANCE}"; then
    active_flag=1
fi

python3 "${SCRIPT_DIR}/lib/run_status.py" \
    "${PMT_ACTIVE_RUN_JSON}" \
    "${PMT_ACTIVE_INSTANCE}" \
    "${active_flag}" \
    --write-result

if [[ "${active_flag}" -eq 1 ]]; then
    say ""
    say "后台服务: 运行中"
else
    say ""
    say "后台服务: 未运行"
    if [[ -f "${PMT_ACTIVE_RUN_JSON}" ]]; then
        completed="$(python3 -c "import json; print(json.load(open('${PMT_ACTIVE_RUN_JSON}')).get('CompletedFiles',0))")"
        requested="$(python3 -c "import json; print(json.load(open('${PMT_ACTIVE_RUN_JSON}')).get('RequestedSamples',0))")"
        if [[ "${completed}" -lt "${requested}" ]]; then
            say "可执行: sudo ${SCRIPT_DIR}/resume-capture.sh"
        fi
    fi
fi
