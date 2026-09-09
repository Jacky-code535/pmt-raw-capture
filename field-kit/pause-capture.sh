#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root

if ! read_run_state; then
    say_err "没有正在配置的任务。请先运行: sudo ${SCRIPT_DIR}/start-capture.sh"
    exit 1
fi

if ! service_is_active "${PMT_ACTIVE_INSTANCE}"; then
    say "后台服务当前未在运行。"
    "${SCRIPT_DIR}/show-progress.sh"
    exit 0
fi

systemctl stop "pmt-bulk-capture@${PMT_ACTIVE_INSTANCE}.service"
say "已暂停采集（已保存的数据不会删除）。"
say ""
say "续采请执行: sudo ${SCRIPT_DIR}/resume-capture.sh"
"${SCRIPT_DIR}/show-progress.sh"
