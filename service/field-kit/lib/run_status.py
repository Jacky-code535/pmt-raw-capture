#!/usr/bin/env python3
"""Print capture progress and write a simple result.txt for field operators."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from pmt_capture_cli import status_report


def parse_zulu(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_duration_cn(total_sec: float) -> str:
    total_sec = max(0, int(total_sec))
    hours, rem = divmod(total_sec, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        return f"约 {hours} 小时 {mins} 分钟"
    if mins:
        return f"约 {mins} 分钟"
    return f"约 {secs} 秒"


def main() -> int:
    run_json = Path(sys.argv[1])
    instance = sys.argv[2]
    service_active = sys.argv[3] == "1"
    write_result = len(sys.argv) > 4 and sys.argv[4] == "--write-result"

    data = json.loads(run_json.read_text(encoding="utf-8"))
    interval = float(data.get("IntervalSeconds", 60))
    requested = int(data.get("RequestedSamples", 0))
    completed = int(data.get("CompletedFiles", 0))
    complete = int(data.get("CompleteFiles", 0))
    incomplete = int(data.get("IncompleteFiles", 0))
    status = data.get("Status", "unknown")
    endpoint = data.get("Endpoint", "")
    run_id = data.get("RunId", "")
    created = data.get("CreatedAt", "")
    updated = data.get("UpdatedAt", "")
    verification = status_report(run_json.parent)["verification"]

    plan_sec = interval * requested
    remaining = max(0, requested - completed)
    eta_sec = remaining * interval if service_active and remaining else 0

    print("=== PMT 采集进度 ===")
    print(f"服务实例: pmt-bulk-capture@{instance}.service")
    print(f"服务器标识: {endpoint}")
    print(f"运行 ID: {run_id}")
    print(f"计划: 每 {int(interval)} 秒 1 份 × {requested} 份 = {format_duration_cn(plan_sec)}")
    print(f"状态: {status}")
    print(f"文件校验: {verification}")
    print(f"进度: {completed} / {requested} 份")
    print(f"完整: {complete} 份 | 不完整: {incomplete} 份")
    if created:
        print(f"开始时间(UTC): {created}")
    if updated:
        print(f"最近更新(UTC): {updated}")
    if service_active and remaining > 0:
        print(f"预计剩余: {format_duration_cn(eta_sec)}（按当前间隔估算，不含停机时间）")
    print(f"结果目录: {run_json.parent}")

    if status == "failed":
        verdict = "INCOMPLETE"
        hint = "采集程序异常停止。请打包当前结果并联系支持同事。"
    elif requested > 0 and completed >= requested and incomplete == 0:
        verdict = "COMPLETE"
        hint = "采集已完成，可以执行: pack-results.sh"
    elif incomplete > 0:
        verdict = "INCOMPLETE"
        hint = "存在不完整文件，请联系支持同事后再打包。"
    elif not service_active and completed < requested:
        verdict = "PAUSED"
        hint = "任务未完成且服务未运行。请执行 resume-capture.sh；勿重复 start-capture.sh 以免新建任务。"
    else:
        verdict = "RUNNING"
        hint = "仍在采集，可关闭终端，后台会继续运行。"

    print("")
    print(f"结论: {hint}")

    if write_result:
        lines = [
            "Intel PMT 本地采集 — 现场结果摘要",
            f"COLLECTION STATUS: {verdict}",
            f"VERIFICATION STATUS: {verification}",
            f"进度: {completed}/{requested}",
            f"计划: 每{int(interval)}秒 × {requested}份",
            f"服务: {'运行中' if service_active else '未运行'}",
            f"目录: {run_json.parent}",
            "",
            hint,
        ]
        result_path = run_json.parent / "result.txt"
        result_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写入: {result_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
