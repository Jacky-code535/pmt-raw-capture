# 离线工作流

适用版本：0.6.2 GNR Edition。旧版 raw v1 原始采集结果继续兼容。

## 流程

采集 → 原始归档 → 精确 XML 解码 → 序列重建 → 统计与拓扑视图 → 实验窗口与对照分析。

采集端只读 PMT，不计算指标。离线端默认使用内置 Python 解码器和匹配的平台 XML，无需其他项目的程序。更换 XML 或分析规则时，使用相同原始数据生成新的分析目录。

## 采集与归档

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id trial-001 \
  --interval 1 --samples 60 --cpu 2 --platform GNR --xml-version approved-revision
./pmt-capture archive --run-dir results/trial-001 --output archives/trial-001
```

`--cpu` 是 Linux 逻辑 CPU 编号，不是物理 core 或 PMT endpoint 编号。采样阶段执行 affinity 设置；后台启动和续采保留它。60 次、1 秒间隔的计划采样跨度为 59 秒，另加启动与最后一次读写时间。

```text
archives/trial-001/
  manifest.json
  metadata/platform.json
  metadata/endpoint.json
  metadata/capture_config.json
  raw/sample-000001/telem1.bin
  raw/sample-000001/telem2.bin
  raw/sample-000002/telem1.bin
  capture/trial-001/run.json
  capture/trial-001/manifest.ndjson
  capture/trial-001/snapshots/...
  logs/...
```

每个二进制文件的序号、endpoint、aggregator、GUID、长度、时间和内容指纹记录在 manifest 中。原始 v1 JSON gzip 同时保留，避免丢失逐样本状态和兼容性。归档目录必须是新目录；采集中不能归档。`--allow-partial` 接受样本数较少但已有快照全部有效的任务，不接受损坏或缺少 aggregator 的快照。

新任务的 `run.json` 保存采集器版本与源码指纹、采样间隔、平台/XML版本标签、DMI BIOS信息和 CPU 配置。无法读取的 DMI 信息为 null。开始/结束以逐快照时间为准；操作者提供的版本标签与实际观测信息分开保存。

## XML 解码

正式发布包已包含固定 XML 注册表。检查覆盖后指定原始任务目录和新输出目录：

```bash
./pmt-capture validate-platform --run-dir archives/trial-001/capture/trial-001
./pmt-capture analyze --run-dir archives/trial-001/capture/trial-001 \
  --output analysis/trial-001
```

按每个 aggregator 的精确 GUID + Size 匹配 XML。注册表及所需 schema 复制到 `provenance/xml/`；注册表引用必须位于其目录内。解码器由 XML 决定字段、位偏移和单位，Python 分析层不维护平台字段表。

`validate-platform` 和 `analyze` 默认自动使用包内 XML；`--metadata /path/to/xml/pmt.xml` 可覆盖。`--decoder` 仅保留旧外部适配器兼容入口，不是必需依赖。支持的 schema 与公式见[平台数据](platform-data.md)。

收到结果压缩包时，先执行 `./pmt-capture unpack capture.tar.gz --output replay`。输出 JSON 的 `run_dir` 就是分析输入目录。解包拒绝路径穿越、软/硬链接、特殊文件和重复成员，默认上限为 2 GiB 未压缩归档内容与 10,000 个成员。解包后验证原始快照；损坏数据不会作为成功结果保留。归档内嵌的 gzip 快照在后续读取时解压，因此该上限不是所有嵌套内容的内存上限。

`analysis.json` 记录原始文件、XML、解码器和分析程序的内容标识。输入策略、拓扑、事件 CSV 也复制到 provenance。旧版本原始数据优先使用 `attributes.CapturedAt`，避免早期 `CollectionTimestamp` 时间精度不同造成混淆。

## 输出

| 文件 | 内容 |
| --- | --- |
| `decoded.csv` | timestamp、endpoint、metric、value、unit，以及 aggregator、GUID、序号与拓扑标签；保留原始解码值 |
| `series.csv` | 重建序列，增加 measure 与 validity；无效值留空 |
| `summary.csv` | 每条序列的 mean、min、max、p95、std、cv、valid_count |
| `data-quality.csv` | 每条序列的 expected、observed、valid、invalid、missing 数量与 valid_rate |
| `view-system.csv` 等六个视图 | system、socket、die、module、endpoint、aggregator 范围内的序列 |
| `aligned.csv` | timestamp、phase、test_item、PMT metric、value 等 |
| `phase-summary.csv` | 每个阶段、测试项、状态的序列统计 |
| `failure-windows.csv` | 显式失败时间附近的样本及 relative_seconds |

序列身份包含 endpoint、aggregator、GUID、完整 XML 指标名、单位和拓扑标签。不同来源的同名指标保持独立。CSV 为长表；可在表格工具中按 scope、metric、measure 筛选或透视。

## 序列与统计

默认保留数值序列，不根据名称猜测计数器。对已经确认的累积整数计数器，可以传入 `--policies policies.json`：

```json
{
  "example.counter": {
    "kind": "counter",
    "bits": 64,
    "allow_wrap": false,
    "max_gap_seconds": 3,
    "invalid_values": []
  }
}
```

`example.counter` 要替换为 XML 解码后的完整指标名；策略应用于所有同名指标。只有确认位宽和整数累积语义后才能配置 counter。已经换算为浮点物理量的 XML 指标不能直接套用原始寄存器位宽。

计数器输出 value、delta 和 rate，差分在整数域计算，rate 使用该 aggregator 的真实时间差。首样本、缺样、时间倒退、过长间隔、无效标记和未解释的下降都有明确状态。下降默认标记 `reset_or_wrap`；只有显式开启 `allow_wrap` 才假设发生一次模回绕，无法据此识别多次回绕或区分复位。

统计使用有限且非空的数值：mean 为样本算术均值，std 为总体标准差（ddof=0），p95 在排序样本的 `(n-1)*0.95` 位置线性插值，cv 为 std/abs(mean)，均值为零时留空。valid_count 为统计纳入的样本数，不代表硬件健康认证。内置解码器不猜测 poison 常量；无效标记通过显式 `invalid_values` 策略排除。旧外部适配器还可提供 `known_invalid`。未知语义仍需平台验证。

不补零、不自动插值，不跨缺样计算速率。`data-quality.csv` 中 expected_count
取本次任务计划样本数；observed_count 是该序列实际生成的记录数，invalid_count
是存在记录但值不可用于统计的数量，missing_count 是计划数与观测数的差。
这些字段描述数据完整性，不是硬件健康结论。统计暂存使用 SQLite，避免将所有指标的全时序同时保存在 Python 内存中；精确 p95 每次仅加载一条序列。统计转换为 float64，原始整数值和计数器差分仍单独保留。

当前 GNR 发布采用严格解码：先运行 `validate-platform`，然后执行 `analyze`。
任一选中 schema 无法加载或公式无法执行时，分析整体失败并保留 raw，不输出缺少
部分指标却看似成功的结果。后续只有出现明确诊断需求时才考虑 best-effort 模式。

## 拓扑

传入 `--topology topology.csv`，使用已经确认的映射：

```csv
endpoint,aggregator,metric,system,socket,die,module
lab-host,telem1,,system-a,0,0,0
```

空 metric 表示该 aggregator 的默认映射；指定完整 metric 可覆盖它。重复映射报错。未提供映射时，system 使用 endpoint 标签作为本地分组，其余物理拓扑为 unknown；没有 endpoint→core 推断。

六个视图保留原始序列身份，scope 包含父级路径。它们是按拓扑组织的观测视图，不隐式执行跨 aggregator 的 sum。总功率、比率等空间派生指标需要平台确认可加性、分母和覆盖范围后增加公式规则。

## 实验对齐

需要实验阶段对齐时，可准备通用事件 CSV；该输入完全可选。

```csv
start,end,phase,test_item,status,failure_time
2026-09-10T10:00:00Z,2026-09-10T10:01:00Z,stress,test-001,failed,2026-09-10T10:00:45Z
```

```bash
./pmt-capture analyze --run-dir results/trial-001 \
  --metadata /path/to/xml/pmt.xml \
  --events events.csv --topology topology.csv --policies policies.json \
  --event-offset-seconds 0 --failure-before 5 --failure-after 10 \
  --output analysis/trial-001-aligned
```

时间戳必须带 UTC 偏移。阶段匹配使用 `[start,end)`；重叠事件各保留一行。失败窗口使用显式 failure_time，不从 failed 状态猜测失败瞬间。时钟偏移加到事件时间，正值表示事件对应更晚的 PMT 时间；时钟漂移或同步误差需另行测量。

正常/失败运行对照：

```bash
./pmt-capture compare --baseline analysis/normal --candidate analysis/failed \
  --by-test --output comparisons/normal-vs-failed.csv
```

对照按相同序列、phase 和 test_item 匹配，输出均值差、相对变化和两侧 valid_count。未匹配序列明确标记，不补零。比较要求相同 XML、解码器、分析实现、策略和拓扑输入；不同设置应先重新分析。变化表示相关性，不直接判定测试故障原因。不同主机 endpoint 保持独立，不自动视为同一硬件。