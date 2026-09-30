#!/usr/bin/env bash
# 在 avc01 上于 pmt-raw-capture-0.8.0/ 目录内执行（2026-09-30 样例）。
set -euo pipefail
RUN_ID=repo-example-20260930
sudo ./pmt-capture inventory | head -5
sudo ./pmt-capture start --endpoint avc01 --run-id "$RUN_ID" --samples 5 --interval 2 --cpu 2
./pmt-capture verify --run-dir "results/$RUN_ID"
./pmt-capture analyze --run-dir "results/$RUN_ID" --output "analysis/$RUN_ID"
mkdir -p archives
./pmt-capture pack --run-dir "results/$RUN_ID" --output archives
