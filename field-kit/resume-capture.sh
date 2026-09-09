#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root

if ! read_run_state; then
    say_err "找不到可继续的任务。请先运行: sudo ${SCRIPT_DIR}/start-capture.sh"
    exit 1
fi

completed="$(python3 -c "import json; print(json.load(open('${PMT_ACTIVE_RUN_JSON}')).get('CompletedFiles',0))")"
requested="$(python3 -c "import json; print(json.load(open('${PMT_ACTIVE_RUN_JSON}')).get('RequestedSamples',0))")"

if [[ "${completed}" -ge "${requested}" ]]; then
    say "任务已满 ${completed}/${requested} 份，无需继续。"
    exit 0
fi

if service_is_active "${PMT_ACTIVE_INSTANCE}"; then
    say "服务已在运行中。"
    "${SCRIPT_DIR}/show-progress.sh"
    exit 0
fi

systemctl start "pmt-bulk-capture@${PMT_ACTIVE_INSTANCE}.service"
say "已从第 ${completed} 份之后继续采集（目标共 ${requested} 份）。"
say "说明: 使用同一 run-id，不会重复已完成的份数。"
"${SCRIPT_DIR}/show-progress.sh"
