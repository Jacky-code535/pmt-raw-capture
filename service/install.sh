#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PACKAGE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENDPOINT=""
INSTANCE=""
RUN_ID=""
INTERVAL_SECONDS=60
SAMPLES=600
START=1
readonly OUTPUT_ROOT="/var/lib/pmt-system-debug/results"

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage:
  sudo ./install.sh <endpoint>
  sudo ./install.sh --endpoint <name> [options]

Options:
  --instance <name>    systemd instance name (default: endpoint in lowercase)
  --run-id <name>      output run ID (default: endpoint plus UTC timestamp)
  --interval <seconds> sampling interval (default: 60)
  --samples <count>    number of Bulk files (default: 600)
  --no-start           install only; do not start capture
  -h, --help           show this help
EOF
}

while (($#)); do
    case "$1" in
        --endpoint)
            ENDPOINT="${2:?missing value for --endpoint}"
            shift 2
            ;;
        --instance)
            INSTANCE="${2:?missing value for --instance}"
            shift 2
            ;;
        --run-id)
            RUN_ID="${2:?missing value for --run-id}"
            shift 2
            ;;
        --interval)
            INTERVAL_SECONDS="${2:?missing value for --interval}"
            shift 2
            ;;
        --samples)
            SAMPLES="${2:?missing value for --samples}"
            shift 2
            ;;
        --no-start)
            START=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            die "unknown option: $1"
            ;;
        *)
            [[ -z "${ENDPOINT}" ]] || die "unexpected argument: $1"
            ENDPOINT="$1"
            shift
            ;;
    esac
done

[[ -n "${ENDPOINT}" ]] || {
    usage >&2
    exit 2
}
if [[ -z "${INSTANCE}" ]]; then
    INSTANCE="$(printf '%s' "${ENDPOINT}" | tr '[:upper:]_' '[:lower:]-')"
fi
if [[ -z "${RUN_ID}" ]]; then
    RUN_ID="${INSTANCE}-$(date -u +%Y%m%dT%H%M%SZ)"
fi

[[ "${EUID}" -eq 0 ]] || die "run as root"
[[ "${INSTANCE}" =~ ^[A-Za-z0-9.-]+$ ]] \
    || die "PMT_INSTANCE contains unsupported characters"
[[ "${ENDPOINT}" =~ ^[A-Za-z0-9_.-]+$ ]] \
    || die "PMT_ENDPOINT contains unsupported characters"
[[ "${RUN_ID}" =~ ^[A-Za-z0-9_.-]+$ ]] \
    || die "PMT_RUN_ID contains unsupported characters"
[[ "${RUN_ID}" != "." && "${RUN_ID}" != ".." ]] || die "invalid run ID"
[[ "${INTERVAL_SECONDS}" =~ ^[0-9]+$ && "${INTERVAL_SECONDS}" -ge 1 ]] \
    || die "interval must be a positive integer (seconds)"
[[ "${SAMPLES}" =~ ^[0-9]+$ && "${SAMPLES}" -ge 1 ]] \
    || die "samples must be a positive integer"
[[ -d /sys/class/intel_pmt ]] || die "Intel PMT sysfs is unavailable"
PYTHON_BIN="$(command -v python3)" || die "python3 is required"
"${PYTHON_BIN}" -c 'import sys; raise SystemExit(sys.version_info < (3, 7))' \
    || die "Python 3.7 or newer is required"
command -v systemctl >/dev/null || die "systemctl is required"
[[ -d /run/systemd/system ]] || die "systemd must be running"
[[ ! -e "${OUTPUT_ROOT}/${RUN_ID}" ]] || die "run already exists; use resume instead"
active_units="$(systemctl list-units 'pmt-bulk-capture@*.service' --state=active,activating,deactivating --no-legend --plain)"
[[ -z "${active_units}" ]] || die "stop active PMT services before installing or changing a task"

EXPECTED_AGGREGATORS="$(
    "${PYTHON_BIN}" "${PACKAGE_ROOT}/src/pmt_bulk_capture.py" inventory \
        --sysfs-root /sys/class/intel_pmt |
        "${PYTHON_BIN}" -c 'import json,sys; print(len(json.load(sys.stdin)))'
)"
[[ "${EXPECTED_AGGREGATORS}" -gt 0 ]] \
    || die "no Intel PMT aggregators discovered"

install -d -m 0755 /opt/pmt-system-debug
install -d -m 0750 /etc/pmt-system-debug
install -d -m 0750 "${OUTPUT_ROOT}"
install -d -m 0750 /var/lib/pmt-system-debug/exports
if [[ "${PACKAGE_ROOT}" != "/opt/pmt-system-debug" ]]; then
    install -d -m 0755 /opt/pmt-system-debug/src /opt/pmt-system-debug/docs
    install -m 0644 "${PACKAGE_ROOT}/src/"*.py /opt/pmt-system-debug/src/
    install -m 0755 "${PACKAGE_ROOT}/pmt-capture" /opt/pmt-system-debug/
    cp -a "${SCRIPT_DIR}" /opt/pmt-system-debug/
    install -m 0644 "${PACKAGE_ROOT}/docs/"*.md /opt/pmt-system-debug/docs/
    install -m 0644 "${PACKAGE_ROOT}/VERSION" "${PACKAGE_ROOT}/README.md" /opt/pmt-system-debug/
fi
ln -sfn "${PYTHON_BIN}" /opt/pmt-system-debug/python3
install -m 0644 \
    "${SCRIPT_DIR}/systemd/pmt-bulk-capture@.service" \
    /etc/systemd/system/pmt-bulk-capture@.service

config="/etc/pmt-system-debug/${INSTANCE}.conf"
umask 027
{
    printf 'PMT_ENDPOINT=%s\n' "${ENDPOINT}"
    printf 'PMT_RUN_ID=%s\n' "${RUN_ID}"
    printf 'PMT_OUTPUT_ROOT=%s\n' "${OUTPUT_ROOT}"
    printf 'PMT_EXPECTED_AGGREGATORS=%s\n' "${EXPECTED_AGGREGATORS}"
    printf 'PMT_INTERVAL_SECONDS=%s\n' "${INTERVAL_SECONDS}"
    printf 'PMT_SAMPLES=%s\n' "${SAMPLES}"
} >"${config}"
chmod 0640 "${config}"
printf '%s\n' "${INSTANCE}" > /etc/pmt-system-debug/active-instance
chmod 0640 /etc/pmt-system-debug/active-instance

systemctl daemon-reload
if [[ "${START}" == "1" ]]; then
    systemctl enable "pmt-bulk-capture@${INSTANCE}.service"
    systemctl restart "pmt-bulk-capture@${INSTANCE}.service"
fi

printf 'installed instance=%s endpoint=%s aggregators=%s run=%s\n' \
    "${INSTANCE}" "${ENDPOINT}" "${EXPECTED_AGGREGATORS}" "${RUN_ID}"
printf 'config=%s output=%s started=%s\n' \
    "${config}" "${OUTPUT_ROOT}/${RUN_ID}" "${START}"
if [[ "${START}" == "1" ]]; then
    printf 'status: systemctl status pmt-bulk-capture@%s.service\n' \
        "${INSTANCE}"
fi
