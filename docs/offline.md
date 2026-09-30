# 离线工作流

适用版本：0.8.0 GNR Edition。旧版 `intel-pmt-local-bulk/v1` 原始任务继续兼容。

## 采集与传输

```bash
sudo ./pmt-capture start --endpoint gnr-host --run-id trial-001 \
  --duration-seconds 60 --interval 2
./pmt-capture pack --run-dir results/trial-001 --output archives
```

本机分析可直接使用 run 目录，不必打包。跨主机时传输生成的 tar.gz，然后解包：

```bash
./pmt-capture unpack archives/pmt-capture-trial-001.tar.gz --output replay
```

解包返回的 `run_dir` 为分析输入。解包拒绝路径穿越、链接、特殊文件和重复成员，并验证原始快照；默认限制 2 GiB 外层未压缩内容和 10,000 个成员。

## 处理

```bash
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001
```

正式包自动使用固定版本中选取的七组 GNR schema，按精确 GUID + Size 匹配。raw 验证与 schema 检查在分析内部执行；不匹配、解码失败或指标生成失败时，不发布半成品目录，raw 保持不变。

```text
analysis/trial-001/
  decoded.csv
  metrics.csv
  dashboard.html
  analysis.json
  provenance/
```

| 文件 | 内容 |
| --- | --- |
| `decoded.csv` | 全部非保留 XML 指标的解码值、时间、单位、序号、endpoint、aggregator 和 GUID |
| `metrics.csv` | 长表派生指标，保留同类来源列，并增加 Core、实际计算区间、公式类型和质量状态 |
| `dashboard.html` | 七项关键 Core 趋势，直接离线打开 |
| `analysis.json`、`provenance/` | raw 验证结果、输入指纹、实际 XML、指标配置与运行信息 |

当前 metrics 的派生范围是 CORE schema；其他 schema 不丢失，保存在 decoded 中。看板选择的是 XML 本地槽位，不能由 `telemN` 或零读数猜测 Linux CPU、物理 Core 或启用状态。

## 分步处理

```bash
./pmt-capture analyze --run-dir results/trial-001 --output decoded/trial-001 --decode-only
./pmt-capture report --analysis-dir decoded/trial-001 --output reports/trial-001
./pmt-capture view --input reports/trial-001/metrics.csv --output core-view.html
```

`--decode-only` 只生成完整解码 CSV 和追溯信息。`report` 从 decoded 和其追溯信息计算 metrics，不再生成 Excel。`view` 只需要 metrics CSV。

没有 CORE schema 的原始任务可使用 `--decode-only`；默认指标处理会明确报错，不伪造 Core 指标。源码／基础包需要 `--metadata /path/to/pmt.xml`；正式下载包无需该参数。

## 保留的辅助功能

`inventory`、`status`、`stop`、`resume`、`verify`、`pack`、`unpack` 可单独使用。`--allow-partial` 允许少于计划数量但已存快照全部有效的任务，不接受损坏输入。

旧版多层统计、策略和事件分析需显式添加 `analyze --legacy-analysis`，默认不生成 metrics 或 HTML；其 CSV 格式保留兼容。`compare` 仅适用于这种旧统计输出。`archive` 的逐区域二进制导出与外部 `--decoder` 接口同样保留兼容，不是新流程必需步骤。

指标计算和可视化说明见 [指标与看板](report.md)。