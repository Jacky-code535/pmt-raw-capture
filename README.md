# PMT Raw Capture

Linux Intel PMT **采集、压缩归档、解包、XML 解码和分析工具**。现场只读 raw telemetry，离线使用内置 Python 解码器完成指标转换、序列重建、统计和实验对齐。字段和单位来自平台 XML；物理拓扑使用显式映射。运行依赖 Python 3.7+，无需 pip 包或 Go 可执行文件。

当前版本为 **0.5.0**。XML 注册表由使用者单独提供，不包含在本仓库或工具包中。

**[下载完整工具包 v0.5.0](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.5.0/pmt-raw-capture-0.5.0.tar.gz)**

## 完整工具快速开始

在当前源码目录或解压后的 0.5.0 工具目录执行：

```bash
# 合成数据 smoke，不需要 PMT 硬件、平台 XML 或 root
bash scripts/smoke_test.sh

# 在提供 PMT sysfs 的被测机上采集
./pmt-capture start --config examples/capture_config.json
./pmt-capture pack --run-dir results/trial-001 --output packages

# 在分析机上解包并分析，也可直接分析原始 results 目录
./pmt-capture unpack packages/pmt-capture-trial-001.tar.gz --output replay
./pmt-capture validate-platform --run-dir replay/trial-001 --metadata /path/to/pmt.xml
./pmt-capture analyze --run-dir replay/trial-001 --metadata /path/to/pmt.xml \
  --output analysis/trial-001
```

采集权限不足时，只对采集命令使用 `sudo`。操作者决定何时执行 `start`，用 `--interval` 控制相邻样本的计划启动间隔，用 `--samples` 控制计划样本数，并可随时执行 `stop`。配置采用 JSON；路径相对于配置文件目录解析，命令行显式值优先。不自动加载默认配置，输出目录和 run ID 不可复用。平台匹配使用精确 **GUID + Size**，不是根据机器标签猜测。XML 要求见[平台数据](docs/platform-data.md)，完整命令和输出见[离线工作流](docs/offline.md)。

下载后将压缩包放到被测主机。v0.4.3 仅含旧采集器；历史版本见 [Releases](https://github.com/Jacky-code535/pmt-raw-capture/releases)。

## 开始采集

被测主机需运行 Linux，并提供 `/sys/class/intel_pmt/telem*` 设备节点。

解压并查看 PMT 设备：

```bash
tar -xzf pmt-raw-capture-0.5.0.tar.gz
cd pmt-raw-capture-0.5.0
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
  --metadata /path/to/pmt.xml \
  --topology topology.csv --policies policies.json --events experiment-events.csv \
  --output analysis/run-20260910
```

`analyze` 在新目录下生成多层输出（长表 CSV，便于筛选或透视）：

| 输出 | 含义 |
| --- | --- |
| `decoded.csv` | 解码后的观测值：`timestamp`、`endpoint`、`metric`、`value`、`unit`，以及 aggregator、GUID、序号与拓扑列 |
| `series.csv` | 序列重建结果：在 decoded 基础上增加 `measure`（`value` / `delta` / `rate`）与 `validity`（缺样、回绕、无效标记等） |
| `summary.csv` | 每条序列统计：`mean`、`min`、`max`、`p95`、`std`、`cv`、`valid_count` |
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

命令帮助：`./pmt-capture --help`。XML、raw 和分析结果独立保存，不随工具源码分发。