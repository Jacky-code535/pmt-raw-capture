# avc01 完整流程样例（2026-09-30）

在 **avc01** 上用 **pmt-raw-capture 0.8.0 正式包**（含 `bundled-platform-data`）执行：**采集 → verify → analyze → pack**。本目录为当时命令的 **完整落盘结果**（另含命令日志）。

## 环境

| 项 | 值 |
| --- | --- |
| 主机 | avc01（SSH `root@10.239.89.15`） |
| 工具 | `./pmt-capture --version` → **0.8.0**（见 [tool-version.txt](tool-version.txt)） |
| 内核/架构 | 见 [host-uname.txt](host-uname.txt) |
| PMT 设备 | 见 [inventory-head.txt](inventory-head.txt)（`inventory` 前几行） |
| Run ID | **`repo-example-20260930`** |
| 采集参数 | `--endpoint avc01`，**5** 份，`--interval 2`，`--cpu 2` |

## 执行的命令（顺序）

在解压后的 `pmt-raw-capture-0.8.0/` 目录下：

```bash
# 1. 查看 telem（摘要写入 inventory-head.txt）
sudo ./pmt-capture inventory | head -5

# 2. 采集 raw（stdout 见 start.log）
sudo ./pmt-capture start --endpoint avc01 --run-id repo-example-20260930 \
  --samples 5 --interval 2 --cpu 2

# 3. 校验 raw（输出见 verify.log）
./pmt-capture verify --run-dir results/repo-example-20260930

# 4. 离线分析（需正式包内 bundled GNR XML；stdout 见 analyze.log）
./pmt-capture analyze --run-dir results/repo-example-20260930 \
  --output analysis/repo-example-20260930

# 5. 打包交付（见 pack.log）
./pmt-capture pack --run-dir results/repo-example-20260930 --output archives
```

说明：须使用 **GitHub Release 的 full tar**（`build-full-package.sh` 产物，含 `bundled-platform-data/`）。仅开发者包（无 bundled XML）时 `analyze` 需自行提供 `--metadata`。

## 本目录文件与目录

```text
avc01-repo-example-20260930/
  README.md                 ← 本说明
  tool-version.txt          ← 工具版本
  host-uname.txt            ← uname -a
  inventory-head.txt        ← inventory 摘要
  start.log                 ← start 终端 JSON 行
  verify.log                ← verify JSON
  analyze.log               ← analyze JSON 摘要
  pack.log                  ← pack 输出路径
  results/repo-example-20260930/
    run.json                ← 采集参数与状态
    manifest.ndjson
    collector.log
    snapshots/bulk-*.json.gz ← 5 份 raw（intel-pmt-local-bulk/v1）
  analysis/repo-example-20260930/
    decoded.csv             ← 160 490 行（含 DEADBEEF 等原值）
    metrics.csv             ← 90 240 行派生指标
    dashboard.html          ← 离线 Core 看板
    analysis.json
    provenance/             ← run.json 副本 + 冻结 XML
  archives/
    pmt-capture-repo-example-20260930.tar.gz  ← pack 归档（与 results 等价交付）
```

## 校验摘要（verify）

- **5 / 5** snapshot 有效，`AllObservedFilesValid: true`
- 详见 [verify.log](verify.log)

## 分析摘要（analyze）

- **decoded_rows**: 160 490  
- **metric_rows**: 90 240  
- 详见 [analyze.log](analyze.log)

## 复现

1. 在 avc01（或同类 GNR 机）解压 [pmt-raw-capture-0.8.0.tar.gz](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz)（须为 **含 bundled XML** 的 Release 资产）。  
2. 按上文命令重新跑一遍；或在本机用 `archives/pmt-capture-repo-example-20260930.tar.gz` 做 `unpack` 后再 `analyze`（见 [操作指南](../docs/guide.md)）。

操作说明见仓库 [docs/guide.md](../docs/guide.md)；指标含义见 [docs/report.md](../docs/report.md)。
