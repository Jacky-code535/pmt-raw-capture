# 操作指南

适用版本：**0.8.0 GNR Edition**。下载与最短路径见 [README](../README.md)。本文档是 **唯一** 的 CLI 与工作流说明：采集、停续、校验打包、跨机传输、离线分析、排障。指标公式与看板语义见 [指标与看板](report.md)。

旧版 `intel-pmt-local-bulk/v1` 原始任务继续兼容。

---

## 环境要求

| 要求 | 说明 |
| --- | --- |
| 运行位置 | 被测主机的 Linux OS（分析可在本机或拷贝后的分析机） |
| 软件 | Bash、Python 3.7+；解压需要 tar 和 gzip，无需安装 pip 包 |
| PMT 接口 | `/sys/class/intel_pmt/telem*`，区域中有 `guid`、`size`、`telem` |
| 权限和磁盘 | 能读取 PMT、写入本地结果目录，并有足够空间；采集示例使用 sudo |

工具自动发现 PMT 区域，设备数量取决于平台和驱动。采集无需网络；可选 `--cpu N`（Linux 逻辑 CPU，须在 cpuset 允许范围内，续采保留，记录在 `run.json` 的 `EffectiveCPUs`）、`--platform GNR`、`--xml-version REV`。systemd 部署见 [服务部署](service.md)。

---

## 工作流总览

```text
① start     → results/<run-id>/          （raw + run.json）
②（可选）   verify 或 pack → tar.gz       （跨机时）
③ analyze   → analysis/<run-id>/         （decoded、metrics、dashboard）
④ 浏览器打开 dashboard.html
```

本机可直接对 `results/<run-id>` 执行 `analyze`，不必打包。跨机时在采集端 `pack`，分析端 `unpack` 后再 `analyze`。

典型顺序：

```text
start →（status / stop / resume）→ verify 或 pack → 传输 → unpack → analyze
```

带内 bulk **最快采样间隔为 0.2 秒**（`--interval` 最小 **0.2**）。`--interval` 是相邻两份 **计划开始** 的间隔，不是读一份 snapshot 的耗时；实际读取时间见控制台 `duration_ms`。

---

## 命令参考

统一格式：`./pmt-capture <命令> [参数]`。总帮助 `--help`，子命令 `./pmt-capture <command> --help`。

| 命令 | 用途 | 示例 |
| --- | --- | --- |
| `inventory` | 查看当前机器的 PMT 区域 | `sudo ./pmt-capture inventory` |
| `start` | 新建任务并定时采集 | `--endpoint lab-host --duration-seconds 60 --interval 2 --run-id trial-001` |
| `status` | 进度、运行状态、上次检查 | `--run-dir results/trial-001`；加 `--json` |
| `stop` | 停止采集，保留已有 snapshot | `sudo ./pmt-capture stop --run-dir results/trial-001` |
| `resume` | 按 `run.json` 续采剩余份数 | `--run-dir results/trial-001`；可加 `--background` |
| `verify` | 只校验 raw，不打包 | `./pmt-capture verify --run-dir results/trial-001` |
| `pack` | 校验通过后打 tar.gz | `./pmt-capture pack --run-dir results/trial-001 --output archives` |
| `unpack` | 解包得到可分析的 run 目录 | `./pmt-capture unpack archives/pmt-capture-trial-001.tar.gz --output replay` |
| `analyze` | raw → decoded / metrics / dashboard | `./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001` |
| `report` | 从已有 decoded 目录生成 metrics | `./pmt-capture report --analysis-dir decoded/trial-001 --output reports/trial-001` |
| `view` | 从 metrics.csv 生成 HTML | `./pmt-capture view --input analysis/trial-001/metrics.csv --output core-view.html` |
| `dump` | 单份 gzip 快照转 JSON（不解码指标） | `sudo ./pmt-capture dump results/trial-001/snapshots/bulk-000001-*.json.gz` |

### 采集参数（`start`）

| 参数 | 含义 |
| --- | --- |
| `--endpoint lab-host` | 必填，机器标签；不是 IP/域名 |
| `--duration-seconds 60` | 大致时长；份数 N = ceil(T ÷ interval) |
| `--samples 30` | 计划份数；与 `--duration-seconds` **二选一** |
| `--interval 2` | 计划开始间隔（秒，可小数）；也可写 `--interval-seconds` |
| `--run-id trial-001` | 任务目录名；新实验换名，续采勿改 |
| `--output-root ./results` | 结果父目录，默认 `./results` |
| `--background` | 后台 detached；日志见 `console.log`；**重启后不自动续采** |
| `--cpu 2` | 采集进程绑 OS 逻辑 CPU 2 |
| `--experiment` / `--workload` / `--note` | 可选文字标签，不启动负载 |

机器标签与 run-id 使用英文字母、数字、`.`、`_`、`-`。多 telem 区域 **顺序** 读取，非同一瞬间原子快照；读写慢时实际墙钟间隔可能变长。

---

## 任务状态与长跑

```bash
sudo ./pmt-capture status --run-dir results/trial-001
```

常见字段：`collection: completed` 表示尝试次数已达计划；`busy: False` 表示未在采；`completed` 为已尝试份数，`complete` / `incomplete` 为完整与不完整份数。检查前 `verification: not_checked` 正常。`completed` 不保证每份读全。

长跑示例（600 份 × 60 s，约 10 小时）：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id experiment-001 \
  --interval 60 --samples 600 --background
sudo ./pmt-capture status --run-dir results/experiment-001
sudo ./pmt-capture stop --run-dir results/experiment-001
sudo ./pmt-capture resume --run-dir results/experiment-001 --background
tail -f results/experiment-001/console.log
```

续采沿用原间隔与目标份数，**不补**停机期间数据。每次实验独立 `--run-id`；GUID/Size 变化应新建任务。PMT 恢复后需 **手动** `resume`。可用 `df -h results` 看磁盘。

---

## 校验、打包与 `--allow-partial`

**`verify` 与 `pack`**：同一套 raw 校验。`verify` 只写/打印 `verification.json`；`pack` 通过后生成 `output/pmt-capture-<run-id>.tar.gz`，包内 `result.txt` 含 `Collection: COMPLETE` 与份数摘要。

**`--allow-partial`**（可用于 `verify`、`pack`、`analyze`）：

- 计划份数 **未采满**，但 **已存每一份 snapshot 均完整且有效** 时仍可通过。
- **不接受** 损坏或无效快照。
- 典型：压测中途 `stop` 后仍要交付 raw 或分析。`pack` 包名带 `-partial`，仅供诊断，不作正式满采结果。

未采满且不加 `--allow-partial` 时，`verify` / `pack` / 默认 `analyze` 会失败并提示加该选项。

通过 `sudo` 执行 `pack` 时，归档可归属最初 sudo 调用用户（`0640`），便于普通用户 scp。结果包含主机与遥测，走团队传输渠道，勿提交仓库/Issues/Release。

---

## 跨机传输

```bash
./pmt-capture pack --run-dir results/trial-001 --output archives
./pmt-capture unpack archives/pmt-capture-trial-001.tar.gz --output replay
```

`unpack` 输出 JSON 含 `run_dir`，作为 `analyze --run-dir` 输入。解包拒绝路径穿越、符号链接、特殊文件与重复成员；默认限制外层未压缩 **2 GiB**、**10 000** 成员。

---

## 离线分析

```bash
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001
```

- `--output` 必须是 **新目录**；失败不覆盖已有分析、不修改 raw。
- 正式下载包使用内置七组 GNR schema（精确 **GUID + Size**）。解码/指标失败时不发布半成品目录。
- 无 CORE schema 时可 `--decode-only`；默认 metrics 会明确报错，不伪造 Core 指标。
- 源码/开发者包需 `--metadata /path/to/pmt.xml`；正式 tar 无需。

仅解码：

```bash
./pmt-capture analyze --run-dir results/trial-001 --output decoded/trial-001 --decode-only
```

分步 metrics / HTML：

```bash
./pmt-capture report --analysis-dir decoded/trial-001 --output reports/trial-001
./pmt-capture view --input reports/trial-001/metrics.csv --output core-view.html
```

分析目录通常含 `decoded.csv`、`metrics.csv`、`dashboard.html`、`analysis.json`、`provenance/`。字段与派生范围（CORE `0x22473996` / 14496 B 等）见 [指标与看板](report.md)。raw 字段见 [数据格式](data-format.md)。

---

## 采集结果文件（run 目录）

| 路径 | 内容 |
| --- | --- |
| `snapshots/bulk-*.json.gz` | 每份 raw（GUID、长度、时间戳、Base64 载荷） |
| `run.json` | 机器信息、采集参数、状态 |
| `manifest.ndjson` | 文件名、SHA-256、摘要 |
| `collector.log` | 采集事件；后台另有 `console.log` |

---

## 旧版与兼容

- `analyze --legacy-analysis`：summary、series、六层 view、策略/事件等旧 CSV；默认流程不生成。
- `compare`：仅适用于 legacy 统计输出。
- `archive`、外部 `--decoder`：保留兼容，非默认步骤。

---

## 常见问题

| 情况 | 处理 |
| --- | --- |
| 找不到 PMT 或读取失败 | 平台、驱动、`inventory`、权限 |
| 任务目录已存在 | 新实验换 `--run-id`；原任务 `resume` |
| 后台未起或中途停 | `status` 看 `last_error`；查 `console.log`、`collector.log`、磁盘 |
| 未采满也要交付/分析 | `pack` / `analyze` 加 `--allow-partial` |
| 同名结果包已存在 | 换 `pack --output`；不覆盖 |
| `cannot pack symbolic link` | run 目录须为实体文件；`--allow-partial` 不绕过 |
| `run is busy` | 正在采或被锁定；先 `stop`，勿删锁文件 |
| `complete` < `completed` | 有不完整快照；查日志与 `Capture.Errors` |
| `Permission denied` | root 创建的任务用 sudo 操作 |
| 检查报告 `stale` | 任务已变；停止后重新 `verify` 或 `pack` |

退出码：**0** 成功，**1** 失败，**2** 参数错误。正常提前 `stop` 也为 0，不代表采满。

---

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [指标与看板](report.md) | 公式、validity、HTML 与 Grafana |
| [数据格式](data-format.md) | bulk 快照与 manifest |
| [GNR 兼容性](compatibility.md) | Qualified GUID |
| [服务部署](service.md) | systemd、field-kit |
