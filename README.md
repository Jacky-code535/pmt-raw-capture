# Intel PMT Capture and Analysis Toolkit

在 **GNR Linux 主机**上 bulk 采集 Intel PMT 原始数据，使用包内 GNR XML 离线解码，生成长表指标 CSV 和逐 Core 看板。采集只读 Linux PMT sysfs，不修改硬件配置。

当前版本：**0.8.0 GNR Edition**。需要 Python 3.7+、Bash、tar 和 gzip。默认流程无需 pip 安装、数据库服务或联网。

**下载：[pmt-raw-capture-0.8.0.tar.gz](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz)**

## 工作流

```text
bulk raw → 内置 GNR XML → decoded.csv → metrics.csv → dashboard.html
```

| 结果 | 内容 |
| --- | --- |
| `decoded.csv` | 完整 XML 解码观测，保留原值、单位、时间、序号与来源 |
| `metrics.csv` | 相同长表组织方式；按确认的公式计算区间增量、速率、桶占比和加权平均估计 |
| `dashboard.html` | 可选择 PMT aggregator 和 XML 本地 Core 的离线关键指标趋势 |

原始 raw 始终保留。分析目录另有 `analysis.json` 和 `provenance/`，记录验证结果、XML、公式及输入指纹；默认不生成多层视图、事件分析、统计 CSV 或 Excel。

## 使用

### 1. 下载并解压

```bash
curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz
tar -xzf pmt-raw-capture-0.8.0.tar.gz
cd pmt-raw-capture-0.8.0
./pmt-capture --version
```

不能联网的主机可接收其他机器下载的压缩包。正式包内置七组已验证 GNR schema，见 [GNR 兼容性](docs/compatibility.md)。

### 2. 采集

每 2 秒一份，计划采集 60 秒：

```bash
sudo ./pmt-capture start --endpoint gnr-host --run-id trial-001 \
  --duration-seconds 60 --interval 2
```

`--duration-seconds` 与 `--samples` 二选一。首份立即采集，上例计划在第 0、2、…、58 秒启动，共 30 份。时长定义为计划采样窗口，不是硬截止时间；读取超时或机器繁忙可能延长实际完成时间。间隔支持正小数。

长任务可加 `--background`；`--cpu 2` 可将采集进程固定到 Linux 逻辑 CPU 2。

```bash
sudo ./pmt-capture status --run-dir results/trial-001
sudo ./pmt-capture stop --run-dir results/trial-001
sudo ./pmt-capture resume --run-dir results/trial-001 --background
```

续采沿用原计划，主机重启后需手动恢复。

### 3. 离线处理

采集结束后，在可读取 raw 的账户下运行：

```bash
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001
```

工具自动验证 raw、精确匹配 GUID + Size、解码、计算指标并生成看板。打开 `analysis/trial-001/dashboard.html` 即可查看。输出必须是新目录，失败不会覆盖已有结果或修改 raw。

跨主机处理时，用 `pack` / `unpack` 传输原始任务，见 [离线工作流](docs/offline.md)。

## 指标与可视化

metrics 与 decoded 都是一条指标观测占一行的长表，不是宽表。当前派生配置覆盖 CORE schema 的 47 项指标，包括温度、usage 增量、PVP 增量和速率、频率／电压加权估计、C6 桶占比及三类桶分布；其他 schema 的完整观测保留在 decoded 中。

相邻样本差分使用每个 aggregator 的真实时间。首个累计读数作为基线；缺样、无效输入和计数下降的派生值留空，并记录原因。usage 增量不是 CPU 利用率；桶加权频率和电压是估计值，相关尺度仍有平台验证边界。

看板从 metrics CSV 生成，显示七项关键趋势，独立 HTML 可离线打开。重新生成看板无需 raw、XML 或其他报告文件：

```bash
./pmt-capture view --input analysis/trial-001/metrics.csv --output core-view.html
```

## 文档

| 文档 | 内容 |
| --- | --- |
| [离线工作流](docs/offline.md) | 传输、解码、输出和兼容选项 |
| [指标与看板](docs/report.md) | 公式、长表字段、数据质量和可视化选型 |
| [使用指南](docs/usage.md) | 参数、任务状态与排障 |
| [产品需求规格](REQUIREMENTS.md) | 当前范围和验收要求 |
| [支持说明](SUPPORT.md) | 支持边界和问题反馈 |
| [更新记录](docs/changelog.md) | 版本变化 |

旧统计、事件对齐、对照分析与服务脚本保留兼容，不进入默认工作流。命令帮助：`./pmt-capture --help`。