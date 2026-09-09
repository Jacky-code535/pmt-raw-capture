#!/usr/bin/env bash
# Shared helpers for field-kit scripts.

kit_root() {
    cd -- "$(dirname -- "${BASH_SOURCE[1]}")/.." && pwd
}

package_root() {
    local field_kit
    field_kit="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
    if [[ -f "${field_kit}/../install.sh" ]]; then
        cd -- "${field_kit}/.." && pwd
        return
    fi
    if [[ -f "/opt/pmt-system-debug/install.sh" ]]; then
        echo "/opt/pmt-system-debug"
        return
    fi
    cd -- "${field_kit}/.." && pwd
}

install_root() {
    if [[ -f /opt/pmt-system-debug/pmt_bulk_capture.py ]]; then
        echo "/opt/pmt-system-debug"
        return
    fi
    package_root
}

results_root() {
    echo "/var/lib/pmt-system-debug/results"
}

exports_root() {
    echo "/var/lib/pmt-system-debug/exports"
}

delivery_output_root() {
    local root
    root="$(package_root)"
    if [[ "${root}" != "/opt/pmt-system-debug" && -f "${root}/run.sh" ]]; then
        echo "${root}/output"
        return
    fi
    exports_root
}

say() {
    printf '%s\n' "$*"
}

say_err() {
    printf '错误: %s\n' "$*" >&2
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        say_err "请使用 root 运行，例如: sudo $0"
        exit 1
    fi
}

check_prerequisites() {
    local ok=1
    say "=== 运行前检查 ==="
    if [[ -d /sys/class/intel_pmt ]]; then
        local count
        count="$(find /sys/class/intel_pmt -maxdepth 1 -name 'telem*' 2>/dev/null | wc -l)"
        if [[ "${count}" -gt 0 ]]; then
            say "[通过] Intel PMT sysfs 已就绪（发现 ${count} 个 telem 节点）"
        else
            say_err "[未通过] /sys/class/intel_pmt 存在但没有 telem* 节点"
            ok=0
        fi
    else
        say_err "[未通过] 未找到 /sys/class/intel_pmt（本机可能不支持带内 PMT）"
        ok=0
    fi
    if command -v python3 >/dev/null; then
        if python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 7))'; then
            say "[通过] Python 3: $(python3 --version 2>&1)"
        else
            say_err "[未通过] 需要 Python 3.7 或更高版本"
            ok=0
        fi
    else
        say_err "[未通过] 未安装 python3"
        ok=0
    fi
    if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
        say "[通过] systemd 可用"
    else
        say_err "[未通过] 未找到 systemctl"
        ok=0
    fi
    local free_mb
    free_mb="$(df -m /var/lib 2>/dev/null | awk 'NR==2 {print $4}')"
    if [[ -n "${free_mb}" && "${free_mb}" -ge 500 ]]; then
        say "[通过] /var/lib 可用空间约 ${free_mb} MB"
    else
        say_err "[注意] /var/lib 可用空间不足 500 MB（当前: ${free_mb:-未知} MB），可能无法完成 10 小时采集"
        ok=0
    fi
    if [[ "${ok}" -eq 0 ]]; then
        say ""
        say_err "条件未满足，请先处理上述问题后再运行。"
        exit 1
    fi
    say ""
}

active_instance_conf() {
    local active_file="/etc/pmt-system-debug/active-instance"
    local conf instance newest=""
    if [[ -f "${active_file}" ]]; then
        instance="$(tr -d '[:space:]' <"${active_file}")"
        conf="/etc/pmt-system-debug/${instance}.conf"
        if [[ -n "${instance}" && -f "${conf}" ]]; then
            echo "${conf}"
            return
        fi
    fi
    for conf in /etc/pmt-system-debug/*.conf; do
        [[ -f "${conf}" ]] || continue
        if [[ -z "${newest}" || "${conf}" -nt "${newest}" ]]; then
            newest="${conf}"
        fi
    done
    [[ -n "${newest}" ]] || return 1
    echo "${newest}"
}

load_active_config() {
    local conf
    conf="$(active_instance_conf)" || return 1
    # shellcheck disable=SC1090
    source "${conf}"
    PMT_ACTIVE_CONF="${conf}"
    PMT_ACTIVE_INSTANCE="$(basename "${conf}" .conf)"
    PMT_ACTIVE_INTERVAL="${PMT_INTERVAL_SECONDS:-60}"
    PMT_ACTIVE_SAMPLES="${PMT_SAMPLES:-600}"
    return 0
}

active_progress() {
    load_active_config || return 1
    python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); print(data.get("CompletedFiles",0), data.get("RequestedSamples",0))' \
        "$(results_root)/${PMT_RUN_ID}/run.json"
}

service_is_active() {
    local instance="$1"
    systemctl is-active --quiet "pmt-bulk-capture@${instance}.service"
}

read_run_state() {
    local conf run_id
    load_active_config || return 1
    conf="${PMT_ACTIVE_CONF}"
    run_id="${PMT_RUN_ID}"
    local run_json
    run_json="$(results_root)/${run_id}/run.json"
    if [[ ! -f "${run_json}" ]]; then
        say_err "找不到运行记录: ${run_json}"
        return 1
    fi
    PMT_ACTIVE_RUN_ID="${run_id}"
    PMT_ACTIVE_RUN_JSON="${run_json}"
    PMT_ACTIVE_RUN_DIR="$(dirname "${run_json}")"
}
