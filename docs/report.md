# 指标与看板

0.8.0 默认流程：raw → XML 解码 → decoded 长表 → metrics 长表 → Core HTML。全程使用 Python 标准库，默认不生成 Excel。

## 长表契约

decoded 保存原始 XML 解码值；metrics 不改成宽表，一条来源明确的指标观测占一行。两者保留 `timestamp, endpoint, metric, value, unit, sequence, aggregator, guid` 及拓扑、measure、validity 列。

metrics 的名称如 `C0.pvp64_rate`，额外记录 `core, physical_core, interval_start, interval_seconds, title, notes, numerator, denominator`。区间终点为 timestamp；瞬时量的起终点相同。numerator、denominator 用于正确汇总速率和桶加权结果，不是额外的 CSV。

当前 [GNR 配置](../config/metrics-gnr.json) 对精确 CORE GUID `0x22473996`、14496 字节定义 64 个 XML 槽位和每槽位 47 项指标。该槽位数不等于物理启用 Core 数。其他 schema 的解码值完整保存在 decoded；尚无确认公式的字段不自动猜测派生含义。

## 计算

| 原始量 | 区间处理 | 输出 |
| --- | --- | --- |
| 温度 | 当前解码值 | C |
| usage 累计量 | 本次减上次 | 实验性 usage 增量，不是利用率 |
| PVP 64/1024 累计事件 | 本次减上次；再除以实际时间差 | count、count/s |
| 频率、电压、温度各桶累计驻留量 | 每桶本次减上次 | 作为分布与加权平均的输入 |
| 桶分布 | 100 × 某桶增量 / 全部桶增量之和 | % |
| 平均频率／电压估计 | Σ(桶增量 × 桶代表值) / Σ桶增量 | MHz、mV |

配置包含含 C6 和非 C6 两种频率估计；频率 r0 为 C6，按 0 MHz 纳入含 C6 平均。电压 r0 为低于 602 mV，不是 C6。开放区间使用配置中注明的近似代表值。

公式参考 inband dashboard 的指标含义，但时间窗口不同：这里用相邻采样区间，在线 Prometheus 使用滚动 `increase` / `rate` 并具有边界外推语义。因此不能把两者的点值当成相同结果。直方图时间尺度尚待平台确认，桶占比和加权估计携带 `provisional` 状态。

## 数据质量

首个累计读数作为基线。缺输入、缺样、时间倒退、间隔超过配置阈值、计数下降、heartbeat 不更新或数据丢失计数改变时，受影响的派生值留空并记录 validity。零是实际数值，不代表缺失或 Core 未启用。不补零、不插值、不猜复位与回绕。

所有已配置指标、所有采样点都保存在 metrics。计算按采样序号流式进行，输入必须按递增序号组织；无需构建六层视图或全量统计数据库。

## 看板

```bash
./pmt-capture view --input analysis/trial-001/metrics.csv --output core-view.html
```

看板生成只读取这一张 CSV，不依赖 raw、XML、摘要 CSV、Excel 或外部服务。HTML 内嵌选定数据，JavaScript 通过 SVG polyline 和 circle 绘图；无需 CDN，移动端自动单列显示。

默认显示温度、usage 增量、PVP64/PVP1024 速率、含 C6 频率估计、电压估计和 C6 桶占比。横轴使用实际 UTC 时间，悬停点显示时间、序号、值与质量。每条序列最多约 600 个实际样本点，保留末点；跨被省略的无效点不连接折线。降采样不保留所有短峰值，完整数据以 metrics CSV 为准。

## 可视化选型

| 方式 | 适用场景 | 部署要求 |
| --- | --- | --- |
| 自包含 HTML（本版） | 单次实验离线交付、直接打开结果 | 无服务，无联网依赖 |
| Plotly 或 ECharts 自包含 HTML | 更丰富的缩放、框选、图例与曲线比较 | 打包固定版本的图表库，可继续离线 |
| Grafana | 多主机、持续采集、多人共享、告警 | Grafana 服务、数据源和导入流程 |

当前优先使用离线 HTML。以后增强交互时，可替换图表库而不改变 metrics 数据契约。Grafana 可由部署脚本安装，但它不是单个静态 HTML；通常需把历史指标导入 PostgreSQL 等数据源，或通过 CSV 数据源插件读取可访问的文件服务。已有区间速率不应在 Grafana 中再次计算 rate。

本包不安装 Grafana，也不启动网络服务。旧 Excel 实现仍留在源码中作兼容测试，默认命令不再调用。