# Intel PMT Capture and Analysis Toolkit

这是一个运行在 **GNR Linux 主机**上的命令行工具，用于完成 Intel PMT 数据的发现、采集、完整性检查、打包、XML 解码和统计分析。它直接读取 Linux PMT sysfs，不修改硬件配置；分析结果为 CSV 和 JSON，可继续用于 Excel、Python 或其他数据工具。

当前版本：**0.6.1 GNR Edition**。运行需要 Python 3.7+、Bash、tar 和 gzip，不需要安装 pip 包、数据库服务或 Go 程序。正式验证范围见 [GNR 兼容性](docs/compatibility.md)。

## 已实现功能

| 阶段 | 命令 | 作用 | 主要输出 |
| --- | --- | --- | --- |
| 设备发现 | `inventory` | 列出主机上的 PMT 区域、GUID 和数据长度 | JSON inventory |
| 数据采集 | `start` | 按时间间隔读取所有 PMT 区域 | 原始 gzip snapshot、运行清单和日志 |
| 任务控制 | `status` / `stop` / `resume` | 查看、停止或继续前台及后台任务 | 任务状态 |
| 完整性检查 | `verify` | 检查快照数量、结构、长度和 SHA-256 | 验证报告 |
| 结果交接 | `pack` / `unpack` | 安全打包或解包一次采集 | 可传输的 tar.gz 结果包 |
| 平台验证 | `validate-platform` | 按精确 `GUID + Size` 检查 XML schema | JSON 验证报告 |
| 解码分析 | `analyze` | 解码 raw，重建序列并计算统计和数据质量 | `decoded.csv`、`series.csv`、`summary.csv`、`data-quality.csv` |
| 结果对比 | `compare` | 比较正常和异常 run 的统计结果 | 差异 CSV |

核心工作流：

```text
inventory -> start -> verify -> pack -> unpack
          -> validate-platform -> analyze
```

SRF、OOB/Redfish 采集、SHC 日志解析和自动故障归因不属于当前版本。详细边界见 [GNR 兼容性](docs/compatibility.md) 和[支持说明](SUPPORT.md)。

## 第一次使用

### 1. 获取工具

下载下面两个文件并放在 GNR 主机的同一目录。第一个是可运行工具包，第二个用于确认下载内容完整。

- [`pmt-raw-capture-0.6.1.tar.gz`](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz)
- [`pmt-raw-capture-0.6.1.tar.gz.sha256`](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz.sha256)

在一个新目录中执行：

```bash
mkdir -p "$HOME/pmt-0.6.1"
cd "$HOME/pmt-0.6.1"

curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz
curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz.sha256
sha256sum -c pmt-raw-capture-0.6.1.tar.gz.sha256
tar -xzf pmt-raw-capture-0.6.1.tar.gz
cd pmt-raw-capture-0.6.1

./pmt-capture --version
bash scripts/smoke_test.sh
```

预期：checksum 显示 `OK`，版本输出 `0.6.1`，smoke 显示 `Ran 2 tests` 和 `OK`。若主机不能访问 GitHub，可通过团队批准的渠道传输这两个文件，然后从 `sha256sum` 开始。

### 2. 完成首次三样本检查

以下命令在同一台 GNR 主机采集三份数据并生成分析结果。将 `gnr-host` 改为便于识别的机器名称：

```bash
cd "$HOME/pmt-0.6.1/pmt-raw-capture-0.6.1"
RUN_ID="gnr-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
ENDPOINT="gnr-host"

# 发现 PMT 区域
sudo ./pmt-capture inventory | tee "inventory-$RUN_ID.json"

# 每隔 2 秒采集一份，共 3 份
sudo ./pmt-capture start --endpoint "$ENDPOINT" --platform GNR \
  --run-id "$RUN_ID" --interval 2 --samples 3

# 检查并打包
sudo ./pmt-capture verify --run-dir "results/$RUN_ID"
sudo ./pmt-capture pack --run-dir "results/$RUN_ID" --output packages
ARCHIVE="packages/pmt-capture-$RUN_ID.tar.gz"
test -r "$ARCHIVE"

# 解包、验证平台并分析
REPLAY="replay-$RUN_ID"
ANALYSIS="analysis-$RUN_ID"
./pmt-capture unpack "$ARCHIVE" --output "$REPLAY"
./pmt-capture validate-platform --run-dir "$REPLAY/$RUN_ID" \
  | tee "validation-$RUN_ID.json"
./pmt-capture analyze --run-dir "$REPLAY/$RUN_ID" --output "$ANALYSIS"

# 检查四个核心输出非空
test -s "$ANALYSIS/decoded.csv"
test -s "$ANALYSIS/series.csv"
test -s "$ANALYSIS/summary.csv"
test -s "$ANALYSIS/data-quality.csv"
printf 'PASS: %s\n' "$ANALYSIS"
```

采集期间应看到三行 `"complete":true`。`verify` 应显示 `AllObservedFilesValid: true` 和 `RequestedSampleCountReached: true`；`validate-platform` 应显示 `mapping_valid: true` 和 `valid: true`；最后应打印 `PASS`。不同 GNR inventory 的 decoded 行数可能不同，不应硬编码为 AVC01 的行数。

如果失败，保留 `inventory-*.json`、`validation-*.json`、`results/<run-id>/collector.log` 和终端错误。不要用相近 GUID 的 XML 代替精确映射。排查方法见[使用指南](docs/usage.md)，交接方法见[同事使用与介绍指南](docs/colleague-guide.md)。

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

## 如何理解这个 GitHub 仓库

如果你是**工具使用者**，只需要关注以下入口：

1. 本 README：了解功能并完成第一次三样本检查；
2. [同事使用与介绍指南](docs/colleague-guide.md)：了解交接方式和正式采集前的责任；
3. [使用指南](docs/usage.md)：查询完整参数、后台采集和常见问题；
4. [GNR 兼容性](docs/compatibility.md)：确认当前主机是否在正式验证范围内；
5. [支持说明](SUPPORT.md)：准备问题材料并确认数据分享边界。

使用者不需要阅读 `src/`、`scripts/`、`service/` 或 `tests/`。这些目录用于开发、
构建、可选服务部署和自动测试。

如果你是**工具维护者**，主要实现位置如下：

| 路径 | 已实现内容 |
| --- | --- |
| `pmt-capture`、`src/pmt/cli.py` | 命令入口和参数检查 |
| `src/pmt/capture/` | PMT 发现、定时采集、任务状态、停止/恢复、快照验证和打包 |
| `src/pmt/decode/` | XML registry 读取、精确 schema 选择、位域和公式解码 |
| `src/pmt/process/` | counter 重建、有效性处理、统计和数据质量 |
| `src/pmt/export/` | CSV 输出、拓扑映射和安全解包 |
| `src/pmt/pipeline.py` | validate/analyze 的端到端处理和 provenance |
| `tests/` | 单元测试、恶意归档检查和完整 CLI 工作流测试 |
| `.github/workflows/` | Python 3.7、3.10、3.13 自动验证 |

批准的 platform XML 随正式发布包提供，不保存在源码目录中。这样可以让源码开发与
经过审批的平台数据版本分别管理。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [同事使用与介绍指南](docs/colleague-guide.md) | 工具能力、首次验收、责任边界和可转发介绍 |
| [使用指南](docs/usage.md) | 参数、任务状态、结果文件与排障 |
| [支持说明](SUPPORT.md) | 支持范围、问题反馈所需信息和数据分发边界 |
| [数据格式](docs/data-format.md) | 快照字段与解码接口 |
| [离线工作流](docs/offline.md) | XML 解码、序列重建、统计、拓扑和实验对齐 |
| [架构](docs/architecture.md) | 模块边界、数据流与兼容性 |
| [平台数据](docs/platform-data.md) | XML 输入要求、验证和解码范围 |
| [GNR 兼容性](docs/compatibility.md) | 已验证 GUID、XML 版本和支持边界 |
| [需求与验收](REQUIREMENTS.md) | 支持范围、需求状态和发布门槛 |
| [GNR 版本记录](docs/gnr-plan.md) | 0.6.x 范围、设计决策和阶段验收 |
| [SHC 预留接口](docs/shc-integration.md) | 后续集成边界，当前版本不启用 |
| [硬件资格记录](docs/qualification.md) | AVC01 真实 GNR 采集、解包、解码和统计结果 |
| [发布流程](docs/release-process.md) | 包构建、依赖边界和发布审批 |
| [服务部署](docs/service.md) | systemd 安装、开机启动和菜单操作 |
| [开发说明](docs/development.md) | 测试、构建与发布 |
| [更新记录](docs/changelog.md) | 各版本变更 |

命令帮助：`./pmt-capture --help`。正式发布包包含批准的 XML；raw 和分析结果始终与工具包分开保存。