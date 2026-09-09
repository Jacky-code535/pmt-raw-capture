#!/usr/bin/env bash
# Interactive and environment-driven capture schedule (interval + sample count).

# shellcheck disable=SC2034
PMT_PLAN_INTERVAL=60
PMT_PLAN_SAMPLES=600

format_duration_cn() {
    local total_sec="$1"
    local hours=$((total_sec / 3600))
    local mins=$(((total_sec % 3600) / 60))
    local secs=$((total_sec % 60))
    if [[ "${hours}" -gt 0 ]]; then
        printf '约 %d 小时 %d 分钟' "${hours}" "${mins}"
    elif [[ "${mins}" -gt 0 ]]; then
        printf '约 %d 分钟' "${mins}"
    else
        printf '约 %d 秒' "${secs}"
    fi
}

plan_total_seconds() {
    local interval="$1"
    local samples="$2"
    echo $((interval * samples))
}

describe_plan() {
    local interval="$1"
    local samples="$2"
    local total
    total="$(plan_total_seconds "${interval}" "${samples}")"
    say "  · 每隔 ${interval} 秒采集 1 份"
    say "  · 共 ${samples} 份"
    say "  · 计划总时长 $(format_duration_cn "${total}")（按 间隔×份数 估算；首次可能多等最多 1 分钟对齐整分）"
}

validate_plan() {
    local interval="$1"
    local samples="$2"
    if [[ ! "${interval}" =~ ^[0-9]+$ ]] || [[ "${interval}" -lt 1 ]]; then
        say_err "采集间隔必须是 ≥1 的整数（秒）"
        return 1
    fi
    if [[ ! "${samples}" =~ ^[0-9]+$ ]] || [[ "${samples}" -lt 1 ]]; then
        say_err "采集份数必须是 ≥1 的整数"
        return 1
    fi
    if [[ "${interval}" -lt 10 ]]; then
        say_err "[注意] 间隔小于 10 秒时负载较高，仅建议在工程师指导下使用。"
    fi
    return 0
}

samples_for_hours() {
    python3 -c 'import math,sys; hours=float(sys.argv[1]); interval=int(sys.argv[2]); assert math.isfinite(hours) and hours>0 and interval>0, "hours and interval must be positive"; print(max(1,math.ceil(hours*3600/interval)))' "$1" "$2"
}

apply_env_plan() {
    if [[ -n "${PMT_INTERVAL_SECONDS:-}" ]]; then
        PMT_PLAN_INTERVAL="${PMT_INTERVAL_SECONDS}"
    fi
    if [[ -n "${PMT_SAMPLES:-}" ]]; then
        PMT_PLAN_SAMPLES="${PMT_SAMPLES}"
    fi
    if [[ -n "${PMT_TOTAL_HOURS:-}" ]]; then
        local secs
        secs="$(samples_for_hours "${PMT_TOTAL_HOURS}" "${PMT_PLAN_INTERVAL}")" || return 1
        PMT_PLAN_SAMPLES="${secs}"
    fi
}

prompt_capture_plan() {
    apply_env_plan || return 1
    if [[ -n "${PMT_INTERVAL_SECONDS:-}" || -n "${PMT_SAMPLES:-}" || -n "${PMT_TOTAL_HOURS:-}" ]]; then
        validate_plan "${PMT_PLAN_INTERVAL}" "${PMT_PLAN_SAMPLES}" || return 1
        say "=== 采集计划（来自环境变量）==="
        describe_plan "${PMT_PLAN_INTERVAL}" "${PMT_PLAN_SAMPLES}"
        say ""
        return 0
    fi

    say "=== 采集计划 ==="
    say "请选择（回车=默认标准 10 小时任务）："
    say "  1) 标准：每 60 秒 1 次，600 次（约 10 小时）"
    say "  2) 试跑：每 60 秒 1 次，3 次（约 3 分钟，确认机器可用）"
    say "  3) 自定义间隔与总时长"
    say "  4) 自定义间隔与份数"
    read -r -p "选择 [1]: " choice
    choice="${choice:-1}"

    case "${choice}" in
        1)
            PMT_PLAN_INTERVAL=60
            PMT_PLAN_SAMPLES=600
            ;;
        2)
            PMT_PLAN_INTERVAL=60
            PMT_PLAN_SAMPLES=3
            ;;
        3)
            read -r -p "每隔多少秒采集一次？[60]: " PMT_PLAN_INTERVAL
            PMT_PLAN_INTERVAL="${PMT_PLAN_INTERVAL:-60}"
            read -r -p "计划总时长大约多少小时？[10]: " hours
            hours="${hours:-10}"
            PMT_PLAN_SAMPLES="$(samples_for_hours "${hours}" "${PMT_PLAN_INTERVAL}")" || return 1
            ;;
        4)
            read -r -p "每隔多少秒采集一次？[60]: " PMT_PLAN_INTERVAL
            PMT_PLAN_INTERVAL="${PMT_PLAN_INTERVAL:-60}"
            read -r -p "一共采集多少份？[600]: " PMT_PLAN_SAMPLES
            PMT_PLAN_SAMPLES="${PMT_PLAN_SAMPLES:-600}"
            ;;
        *)
            say_err "无效选择: ${choice}"
            return 1
            ;;
    esac

    validate_plan "${PMT_PLAN_INTERVAL}" "${PMT_PLAN_SAMPLES}" || return 1
    say ""
    describe_plan "${PMT_PLAN_INTERVAL}" "${PMT_PLAN_SAMPLES}"
    say ""
}
