# Intel PMT Capture and Analysis Toolkit

面向 GNR Linux 主机的 Intel PMT **采集、打包、解包、XML 解码和统计工具**。现场只读 raw telemetry，离线使用内置 Python 解码器生成时间序列、统计摘要和数据质量表。运行依赖 Python 3.7+，无需 pip 包或 Go 可执行文件。

当前版本为 **0.6.1 GNR Edition**。发布包内置固定版本的已批准 Intel PMT XML registry；`validate-platform` 和 `analyze` 默认自动使用它，也可用 `--metadata` 覆盖。

项目入口：[需求与验收](REQUIREMENTS.md) · [GNR 兼容性](docs/compatibility.md) · [实施计划](docs/gnr-plan.md) · [已知限制](docs/qualification.md)

## 先选择正确的下载文件

普通使用者必须下载 **Release Full Bundle**，不要使用 GitHub 自动生成的 `Source code (zip/tar.gz)`，也不要直接 `git clone` 后照下面的无参数 XML 命令运行。源码仓库不提交 platform XML；Full Bundle 才包含 `bundled-platform-data/xml/pmt.xml`。

- [下载 v0.6.1 Full Bundle](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz)
- [下载 SHA-256 文件](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz.sha256)

在 GNR 主机上从一个新目录开始：

```bash
mkdir -p "$HOME/pmt-0.6.1"
cd "$HOME/pmt-0.6.1"

curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz
curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.6.1/pmt-raw-capture-0.6.1.tar.gz.sha256
sha256sum -c pmt-raw-capture-0.6.1.tar.gz.sha256
tar -xzf pmt-raw-capture-0.6.1.tar.gz
cd pmt-raw-capture-0.6.1

./pmt-capture --version
test -f bundled-platform-data/xml/pmt.xml
bash scripts/smoke_test.sh
```

预期：版本输出 `0.6.1`，`test` 没有报错，smoke 显示 `Ran 2 tests` 和 `OK`。若没有 `curl`，可从 Release 页面下载两个文件后从 `sha256sum` 开始。

## GNR 三样本完整复现

以下命令在**同一台 GNR 主机**完成采集和分析，先排除跨机器传输与权限变量：

```bash
cd "$HOME/pmt-0.6.1/pmt-raw-capture-0.6.1"
RUN_ID="gnr-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
ENDPOINT="gnr-host"

# 1. 发现 PMT 区域；同时保存 inventory 便于问题反馈
sudo ./pmt-capture inventory | tee "inventory-$RUN_ID.json"

# 2. 每隔 2 秒采集一份，共 3 份
sudo ./pmt-capture start --endpoint "$ENDPOINT" --platform GNR \
  --run-id "$RUN_ID" --interval 2 --samples 3

# 3. 检查并打包；sudo pack 会把归档所有权交还给当前登录用户
sudo ./pmt-capture verify --run-dir "results/$RUN_ID"
sudo ./pmt-capture pack --run-dir "results/$RUN_ID" --output packages
ARCHIVE="packages/pmt-capture-$RUN_ID.tar.gz"
test -r "$ARCHIVE"

# 4. 用 Full Bundle 内置 XML 解包、验证并分析
REPLAY="replay-$RUN_ID"
ANALYSIS="analysis-$RUN_ID"
./pmt-capture unpack "$ARCHIVE" --output "$REPLAY"
./pmt-capture validate-platform --run-dir "$REPLAY/$RUN_ID" \
  | tee "validation-$RUN_ID.json"
./pmt-capture analyze --run-dir "$REPLAY/$RUN_ID" --output "$ANALYSIS"

# 5. 检查四个核心输出非空
test -s "$ANALYSIS/decoded.csv"
test -s "$ANALYSIS/series.csv"
test -s "$ANALYSIS/summary.csv"
test -s "$ANALYSIS/data-quality.csv"
printf 'PASS: %s\n' "$ANALYSIS"
```

采集期间应看到三行 `"complete":true`。`verify` 应显示 `AllObservedFilesValid: true` 和 `RequestedSampleCountReached: true`；`validate-platform` 应显示 `mapping_valid: true` 和 `valid: true`；最后应打印 `PASS`。不同 GNR inventory 的 decoded 行数可能不同，不应硬编码为 AVC01 的行数。

如果失败，保留 `inventory-*.json`、`validation-*.json`、`results/<run-id>/collector.log` 和终端错误。不要用相近 GUID 的 XML 代替精确映射。常见问题见[使用指南](docs/usage.md)。

## 源码开发者

`git clone` 得到的是 source-only checkout。运行 XML 命令时必须显式提供完整 registry：

```bash
./pmt-capture validate-platform --run-dir results/<run-id> \
  --metadata /approved/platform-data/xml/pmt.xml
./pmt-capture analyze --run-dir results/<run-id> \
  --metadata /approved/platform-data/xml/pmt.xml --output analysis/<run-id>
```

仓库名和压缩包名继续保留 `pmt-raw-capture`，避免破坏已有链接和脚本。历史版本见 [Releases](https://github.com/Jacky-code535/pmt-raw-capture/releases)。

## 开始采集

被测主机需运行 Linux，并提供 `/sys/class/intel_pmt/telem*` 设备节点。

解压并查看 PMT 设备：

```bash
tar -xzf pmt-raw-capture-0.6.1.tar.gz
cd pmt-raw-capture-0.6.1
sudo ./pmt-capture inventory
```

每隔 10 秒采集一份，共三份。将 `lab-host` 替换为机器标签：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id trial-001 \
  --interval 10 --samples 3
```

三份快照分别在约第 0、10、20 秒开始采集。整个任务耗时约 20 秒加上最后一份的读写时间；单份采集耗时见输出中的 `duration_ms`。数据保存在 `results/trial-001/`。

检查并打包结果：

```bash
sudo ./pmt-capture pack --run-dir ./results/trial-001 --output ./output
```

生成的 **`output/pmt-capture-trial-001.tar.gz`** 即为本次实验的结果包。

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
| [使用指南](docs/usage.md) | 参数、任务状态、结果文件与排障 |
| [数据格式](docs/data-format.md) | 快照字段与解码接口 |
| [离线工作流](docs/offline.md) | XML 解码、序列重建、统计、拓扑和实验对齐 |
| [架构](docs/architecture.md) | 模块边界、数据流与兼容性 |
| [平台数据](docs/platform-data.md) | XML 输入要求、验证和解码范围 |
| [GNR 兼容性](docs/compatibility.md) | 已验证 GUID、XML 版本和支持边界 |
| [0.6.0 项目计划](docs/gnr-plan.md) | 精简范围、阶段验收和后续工作 |
| [SHC 预留接口](docs/shc-integration.md) | 后续集成边界，当前版本不启用 |
| [硬件资格记录](docs/qualification.md) | AVC01 真实 GNR 采集、解包、解码和统计结果 |
| [发布流程](docs/release-process.md) | 包构建、依赖边界和发布审批 |
| [服务部署](docs/service.md) | systemd 安装、开机启动和菜单操作 |
| [开发说明](docs/development.md) | 测试、构建与发布 |
| [更新记录](docs/changelog.md) | 各版本变更 |

## 仓库结构

```text
pmt-capture     命令行入口
src/pmt/        capture / decode / process / export 模块与 CLI
config/         JSON 采集默认值
examples/       可执行的采集配置样例
docs/           使用与开发文档
service/        可选的 systemd 部署及菜单
scripts/        工具包构建脚本
tests/          自动化测试
```

命令帮助：`./pmt-capture --help`。Full Bundle 包含批准的 XML；raw 和分析结果始终与工具包分开保存。