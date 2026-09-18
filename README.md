# Intel PMT Capture and Analysis Toolkit

这是一个运行在 **GNR Linux 主机**上的命令行工具，用于完成 Intel PMT 数据的发现、采集、完整性检查、打包、XML 解码和统计分析。它直接读取 Linux PMT sysfs，不修改硬件配置；分析结果为 CSV 和 JSON，可继续用于 Excel、Python 或其他数据工具。

当前版本：**0.6.4 GNR Edition**。运行需要 Python 3.7+、Bash、tar 和 gzip，不需要安装 pip 包、数据库服务或 Go 程序。正式验证范围见 [GNR 兼容性](docs/compatibility.md)。

## 已实现功能

| 阶段 | 命令 | 作用 | 主要输出 |
| --- | --- | --- | --- |
| 设备发现 | `inventory` | 列出主机上的 PMT 区域、GUID 和数据长度 | JSON inventory |
| 数据采集 | `start` | 按时间间隔读取所有 PMT 区域 | 原始 gzip snapshot、运行清单和日志 |
| 任务控制 | `status` / `stop` / `resume` | 查看、停止或继续前台及后台任务 | 任务状态 |
| 完整性检查 | `verify` | 检查快照数量、结构、长度和 SHA-256 | 验证报告 |
| 结果归档 | `pack` / `unpack` | 为跨主机离线分析创建或展开归档 | tar.gz 结果包 |
| 平台验证 | `validate-platform` | 按精确 `GUID + Size` 检查 XML schema | JSON 验证报告 |
| 解码分析 | `analyze` | 解码 raw，重建序列并计算统计和数据质量 | `decoded.csv`、`series.csv`、`summary.csv`、`data-quality.csv` |
| 结果对比 | `compare` | 比较正常和异常 run 的统计结果 | 差异 CSV |

核心工作流：

```text
inventory -> start -> verify -> validate-platform -> analyze
```

本机分析可直接读取 run 目录。跨主机离线分析时，在采集端使用 `pack` 创建归档，在分析端使用 `unpack` 展开归档。SRF、OOB/Redfish 采集、SHC 日志解析和自动故障归因不属于当前版本。

## 第一次使用

### 1. 下载并解压

下载 [`pmt-raw-capture-0.6.4.tar.gz`](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.4/pmt-raw-capture-0.6.4.tar.gz)，放到 GNR 主机后执行：

```bash
mkdir -p "$HOME/pmt-0.6.4"
cd "$HOME/pmt-0.6.4"

curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.4/pmt-raw-capture-0.6.4.tar.gz
tar -xzf pmt-raw-capture-0.6.4.tar.gz
cd pmt-raw-capture-0.6.4

./pmt-capture --version
```

预期版本输出为 `0.6.4`。如果主机不能访问 GitHub，可以先在其他机器下载，再将压缩包传到 GNR 主机。

### 2. 完成首次三样本检查

以下命令在同一台 GNR 主机采集三份数据并生成分析结果。将 `gnr-host` 改为便于识别的机器名称：

```bash
cd "$HOME/pmt-0.6.4/pmt-raw-capture-0.6.4"
RUN_ID="gnr-test-$(date -u +%Y%m%dT%H%M%SZ)"
ENDPOINT="gnr-host"

# 发现 PMT 区域
sudo ./pmt-capture inventory | tee "inventory-$RUN_ID.json"

# 每隔 2 秒采集一份，共 3 份
sudo ./pmt-capture start --endpoint "$ENDPOINT" --platform GNR \
  --run-id "$RUN_ID" --interval 2 --samples 3

# 检查采集结果
sudo ./pmt-capture verify --run-dir "results/$RUN_ID"

# 验证平台并分析
ANALYSIS="analysis-$RUN_ID"
sudo ./pmt-capture validate-platform --run-dir "results/$RUN_ID" \
  | tee "validation-$RUN_ID.json"
sudo ./pmt-capture analyze --run-dir "results/$RUN_ID" --output "$ANALYSIS"
```

完成后，分析结果位于 `analysis-<run-id>/`。其中 `decoded.csv` 是解码数据，`series.csv` 是时间序列，`summary.csv` 是统计摘要，`data-quality.csv` 是数据质量汇总。

跨主机离线分析的归档与解包命令见[使用指南](docs/usage.md)。

## 后台采集

每分钟一份，共 600 份，约 10 小时：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id experiment-001 \
  --interval 60 --samples 600 --background
sudo ./pmt-capture status --run-dir ./results/experiment-001
```

停止与续采：

```bash
sudo ./pmt-capture stop --run-dir ./results/experiment-001
sudo ./pmt-capture resume --run-dir ./results/experiment-001 --background
```

`stop` 后用 `status` 确认 `busy: False` 再续采或打包。续采沿用原计划，保留已采数据；主机重启后需手动续采。

## 离线后解析与指标

采集端**不**内置平台指标表，也不会在采集中解码 CSV。完整流程与 EDP 类似：**raw 永久保留 → XML 解码 → 时间序列重建 → 统计与分层视图 →（可选）与实验时间轴对齐**。

```bash
# 可选：记录平台/XML 标签与 BIOS，便于 10h 长跑追溯
sudo ./pmt-capture start --endpoint gnr-rack-01 --run-id run-20260910 \
  --interval 60 --samples 600 --cpu 2 --platform GNR --xml-version approved-rev

./pmt-capture archive --run-dir results/run-20260910 --output archives/run-20260910

./pmt-capture analyze --run-dir results/run-20260910 \
  --topology topology.csv --policies policies.json --events experiment-events.csv \
  --output analysis/run-20260910
```

`analyze` 在新目录下生成多层输出（长表 CSV，便于筛选或透视）：

| 输出 | 含义 |
| --- | --- |
| `decoded.csv` | 解码后的观测值：`timestamp`、`endpoint`、`metric`、`value`、`unit`，以及 aggregator、GUID、序号与拓扑列 |
| `series.csv` | 序列重建结果：在 decoded 基础上增加 `measure`（`value` / `delta` / `rate`）与 `validity`（缺样、回绕、无效标记等） |
| `summary.csv` | 每条序列统计：`mean`、`min`、`max`、`p95`、`std`、`cv`、`valid_count` |
| `data-quality.csv` | 每条序列的计划数、观测数、有效数、无效数、缺失数和有效率 |
| `view-system.csv` … `view-aggregator.csv` | 按 **system → socket → die → module → endpoint → aggregator** 分 scope 的序列视图（需 `topology.csv`；不假设 endpoint 等于 CPU core） |
| `aligned.csv` | 与可选实验事件 CSV 对齐：`timestamp`、`phase`、`test_item`、PMT 指标与 `value` |
| `phase-summary.csv` | 每个 phase / test_item / status 的序列统计 |
| `failure-windows.csv` | 显式 `failure_time` 前后窗口内的样本 |
| `analysis.json` | 原始快照、XML、解码器与分析程序的内容指纹与统计语义说明 |

正常与失败 run 对照：`./pmt-capture compare --baseline analysis/normal --candidate analysis/failed --by-test --output diff.csv`。

指标集合随平台 XML 变化，具体字段名以解码结果为准。拓扑视图不隐式求和，`valid_count` 不代表硬件健康；平台无效标记需要显式策略。XML 未定义的 FIVR 派生状态不会自动生成。

## 文档

| 文档 | 内容 |
| --- | --- |
| [产品需求规格](REQUIREMENTS.md) | 功能需求、数据契约、兼容性和发布验收标准 |
| [使用指南](docs/usage.md) | 参数、任务状态、结果文件与排障 |
| [支持说明](SUPPORT.md) | 支持范围和问题反馈所需信息 |
| [数据格式](docs/data-format.md) | 快照字段与解码接口 |
| [离线工作流](docs/offline.md) | XML 解码、序列重建、统计、拓扑和实验对齐 |
| [架构](docs/architecture.md) | 模块边界、数据流与兼容性 |
| [平台数据](docs/platform-data.md) | XML 输入要求、验证和解码范围 |
| [GNR 兼容性](docs/compatibility.md) | 已验证 GUID、XML 版本和支持边界 |
| [服务部署](docs/service.md) | systemd 安装、开机启动和菜单操作 |
| [更新记录](docs/changelog.md) | 各版本变更 |

命令帮助：`./pmt-capture --help`。