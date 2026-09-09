#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=lib/schedule.sh
source "${SCRIPT_DIR}/lib/schedule.sh"

require_root
check_prerequisites

ROOT="$(package_root)"
if [[ ! -f "${ROOT}/install.sh" ]]; then
    say_err "找不到安装脚本 install.sh（当前包目录: ${ROOT}）"
    exit 1
fi

if progress="$(active_progress 2>/dev/null)"; then
    read -r completed requested <<<"${progress}"
    if [[ "${completed}" -lt "${requested}" ]]; then
        say "检测到未完成的采集任务（${completed}/${requested} 份）。"
        say "  1) 继续原任务（推荐，从下一份接着采）"
        say "  2) 开始全新任务（新 run-id，与旧数据分开）"
        say "  3) 取消"
        read -r -p "选择 [1]: " action
        action="${action:-1}"
        case "${action}" in
            1)
                exec "${SCRIPT_DIR}/resume-capture.sh"
                ;;
            2)
                say ""
                ;;
            3)
                say "已取消。"
                exit 0
                ;;
            *)
                say_err "无效选择"
                exit 1
                ;;
        esac
    fi
fi

default_name="$(hostname -s 2>/dev/null || hostname)"
default_name="$(printf '%s' "${default_name}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')"

ENDPOINT="${PMT_ENDPOINT:-}"
if [[ -z "${ENDPOINT}" ]]; then
    say "服务器标识用于区分不同机器的结果（字母、数字、下划线、点、横线）。"
    read -r -p "请输入标识 [默认: ${default_name}]: " ENDPOINT
    ENDPOINT="${ENDPOINT:-${default_name}}"
fi

if [[ ! "${ENDPOINT}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    say_err "标识含有非法字符: ${ENDPOINT}"
    exit 1
fi

prompt_capture_plan || exit 1

say "标识: ${ENDPOINT}"
say ""
say "说明:"
say "  · 采集在后台运行，可关闭终端。"
say "  · 需要暂停: sudo ${SCRIPT_DIR}/pause-capture.sh"
say "  · 暂停后可续采: sudo ${SCRIPT_DIR}/resume-capture.sh（已采数据保留）"
say "  · 重启服务器后若已安装服务，一般会自动续采（同一任务）"
read -r -p "确认开始？[Y/n]: " confirm
confirm="${confirm:-Y}"
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    say "已取消。"
    exit 0
fi

say ""
"${ROOT}/install.sh" \
    --endpoint "${ENDPOINT}" \
    --interval "${PMT_PLAN_INTERVAL}" \
    --samples "${PMT_PLAN_SAMPLES}"

say ""
say "=== 已开始后台采集 ==="
"${SCRIPT_DIR}/show-progress.sh" || true
say ""
say "暂停: sudo ${SCRIPT_DIR}/pause-capture.sh"
say "续采: sudo ${SCRIPT_DIR}/resume-capture.sh"
say "打包: sudo ${SCRIPT_DIR}/pack-results.sh（完成后）"
say "说明: ${SCRIPT_DIR}/USER-GUIDE.zh-CN.md"
