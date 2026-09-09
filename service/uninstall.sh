#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf '%s\n' \
        'Usage: sudo ./uninstall.sh [--yes]' \
        'Stop and remove installed PMT systemd services and tools; keep collected data.' \
        'Standalone pmt-capture runs are not managed by this script.' \
        '  --yes       skip the confirmation prompt' \
        '  -h, --help  show this help without making changes'
}

if [[ "$#" -eq 1 && ( "$1" == "--help" || "$1" == "-h" ) ]]; then
    usage
    exit 0
fi
if [[ "$#" -gt 1 || ( "$#" -eq 1 && "$1" != "--yes" ) ]]; then
    usage >&2
    exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
    printf '错误: 请使用 sudo 运行，例如: sudo ./uninstall.sh\n' >&2
    exit 1
fi

if [[ "${1:-}" != "--yes" ]]; then
    read -r -p "停止所有已安装的 PMT 采集服务并卸载工具（保留数据）？[y/N]: " confirm
    [[ "${confirm:-N}" =~ ^[Yy]$ ]] || exit 0
fi

for config in /etc/pmt-system-debug/*.conf; do
    [[ -f "${config}" ]] || continue
    instance="$(basename "${config}" .conf)"
    systemctl disable --now "pmt-bulk-capture@${instance}.service"
done

rm -f /etc/systemd/system/pmt-bulk-capture@.service
rm -f /usr/share/applications/pmt-start-capture.desktop
rm -rf /opt/pmt-system-debug /etc/pmt-system-debug
systemctl daemon-reload

printf 'PMT 采集工具已卸载。\n'
printf '采集数据仍保留在 /var/lib/pmt-system-debug。\n'