# 产品需求规格

## 1. 核心流程

GNR Linux bulk 采集 → 包内 XML 离线解码 → decoded 长表 → metrics 长表 → 逐 Core 可视化。

| ID | 需求 |
| --- | --- |
| CAP-001 | 支持自定义采样间隔，以及计划时长或样本数；首份立即采集 |
| CAP-002 | 读取所有发现的 PMT region，保留原始 payload、身份、逐区域时间和采集状态 |
| XML-001 | 正式包内置固定版本中选取的七组 GNR schema 及依赖，按精确 GUID + Size 匹配 |
| DEC-001 | decoded.csv 完整保留非保留 XML 指标的解码值、单位、时间、序号及来源 |
| MET-001 | metrics.csv 保持长表；对确认的指标计算区间增量、速率、桶占比或加权估计 |
| MET-002 | 首样本、缺样、计数下降和无效输入有明确状态；不补零、不猜复位或回绕 |
| VIS-001 | 看板从 metrics.csv 生成，支持选择 aggregator 和 XML 本地 Core |
| VIS-002 | HTML 可独立离线打开，展示关键趋势；完整指标和时间序列保留在 CSV |

## 2. 输出与边界

默认分析目录仅有两个 CSV：decoded.csv、metrics.csv；另有 dashboard.html、analysis.json 和 provenance/。不默认生成多层视图、统计／质量摘要 CSV、事件分析或 Excel。

当前完整解码覆盖 [GNR 兼容性矩阵](docs/compatibility.md) 的七组 schema；派生配置覆盖 CORE 的 47 项指标，不代表其他 schema 已完成语义转换。指标公式与有效性边界见 [指标与看板](docs/report.md)。

累计量差分使用同一来源的相邻采样。频率与电压按桶增量加权估计，不能称为瞬时测量值。离线窗口不等同于在线 Prometheus 滚动窗口。物理拓扑仅接受已确认映射，不能由 telem 编号或零读数推断。

## 3. 可靠性与辅助功能

| ID | 需求 |
| --- | --- |
| ENV-001 | Python 3.7、3.10、3.13；默认流程不依赖第三方 Python 包、数据库服务或网络 |
| INT-001 | 原子写入与结果目录暂存；失败不发布半成品，不覆盖已有结果 |
| INT-002 | 自动验证快照结构、完整性与原始内容指纹；错配 XML 或公式失败应明确报错 |
| OPS-001 | 保留后台采集、状态、停止、续采、绑核、日志与元数据 |
| ARC-001 | 保留 pack/unpack；拒绝危险归档，不改变原始快照内容 |
| CMP-001 | 继续读取既有 intel-pmt-local-bulk/v1 run |
| CMP-002 | 旧统计、事件、compare、外部 decoder 与服务脚本仅保留兼容入口 |
| REL-001 | 正式包解压后直接运行，包含用户文档、配置和固定 GNR XML |

## 4. 验收

1. 支持的 Python CI 矩阵通过，默认流程测试不依赖 XlsxWriter。
2. 采样参数合法性、raw 完整性、XML 精确匹配和失败清理有回归测试。
3. 公式测试覆盖实际时间差、整数增量、桶加权以及无效区间。
4. 发布包包含且可加载七组 GNR schema，来源和文件清单可核查。
5. 真实 GNR raw 回放生成完整 decoded、metrics 和看板；硬件采集复验与回放分开记录。
6. CSV-only 看板重建及桌面／移动端浏览器检查通过。
7. 公开下载包与完成验证的包一致。

SRF、OOB/Redfish、SHC、自动故障归因、Grafana 服务部署和新平台公式不在本版范围内。