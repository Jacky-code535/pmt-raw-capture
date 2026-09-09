#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly KIT="${ROOT}/field-kit"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    printf 'Optional systemd menu: sudo ./run.sh\nEngineer CLI: ./pmt-capture --help\n'
    exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
    printf '错误: 请使用 sudo 运行，例如: sudo ./run.sh\n' >&2
    exit 1
fi

run_action() {
    if "$@"; then
        return 0
    else
        printf '操作未完成，请检查上述信息。\n' >&2
    fi
}

while true; do
    cat <<'EOF'

=== Intel PMT 本地采集 ===
1) 开始新采集或继续未完成任务
2) 查看采集状态
3) 暂停采集
4) 继续采集
5) 完成检查并打包结果
6) 卸载工具（保留采集数据）
7) 退出
EOF
    read -r -p "选择 [1]: " choice || exit 0
    choice="${choice:-1}"
    case "${choice}" in
        1) run_action "${KIT}/start-capture.sh" ;;
        2) run_action "${KIT}/show-progress.sh" ;;
        3) run_action "${KIT}/pause-capture.sh" ;;
        4) run_action "${KIT}/resume-capture.sh" ;;
        5) run_action "${KIT}/pack-results.sh" ;;
        6) run_action "${ROOT}/uninstall.sh"; exit 0 ;;
        7) exit 0 ;;
        *) printf '错误: 无效选择: %s\n' "${choice}" >&2 ;;
    esac
done