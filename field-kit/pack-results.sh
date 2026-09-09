#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

require_root

if ! read_run_state; then
    say_err "找不到可打包的采集任务。"
    exit 1
fi

if service_is_active "${PMT_ACTIVE_INSTANCE}"; then
    say_err "请先暂停采集，再打包当前数据。"
    exit 1
fi

options=()
if ! python3 "$(package_root)/pmt_capture_cli.py" verify --run-dir "${PMT_ACTIVE_RUN_DIR}"; then
    read -r -p "校验未通过，仍导出诊断数据？[y/N]: " force
    [[ "${force:-N}" =~ ^[Yy]$ ]] || exit 1
    options+=(--allow-partial)
fi

out_dir="$(delivery_output_root)"
archive="$(python3 "$(package_root)/pmt_capture_cli.py" pack \
    --run-dir "${PMT_ACTIVE_RUN_DIR}" --output "${out_dir}" "${options[@]}")"
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    chown "${SUDO_USER}" "${out_dir}" "${archive}"
fi
say ""
say "=== 打包完成 ==="
say "${archive}"
say ""
say "请将此文件发给分析同事，并附上 field-kit/USER-GUIDE.zh-CN.md。"
