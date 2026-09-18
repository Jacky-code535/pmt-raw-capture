# 产品需求规格

## 1. 目的

Intel PMT Capture and Analysis Toolkit 用于在 GNR Linux 主机采集 Intel PMT
原始遥测，并在本机或独立分析主机上完成数据验证、XML 解码、时间序列重建和统计分析。

## 2. 运行环境

| ID | 需求 |
| --- | --- |
| `ENV-001` | 采集端应运行 Linux，并可访问 `/sys/class/intel_pmt/telem*`。 |
| `ENV-002` | 工具应支持 Python 3.7、3.10 和 3.13，且不依赖第三方 Python 包。 |
| `ENV-003` | 离线分析不应要求连接平台数据服务；所需 XML 应随发布包提供。 |

## 3. 采集与任务控制

| ID | 需求 |
| --- | --- |
| `CAP-001` | `inventory` 应列出每个 PMT region 的 AccessId、GUID 和 Size。 |
| `CAP-002` | `start` 应按指定 interval 和 sample count 采集所有已发现 region。 |
| `CAP-003` | 每份 snapshot 应保存时间、region 元数据、原始 payload 和完整状态。 |
| `CAP-004` | 任一 region 读取失败时，snapshot 不得标记为 complete。 |
| `CAP-005` | 新任务不得覆盖已有 run；每个实验应使用独立 run ID。 |
| `OPS-001` | 工具应支持前台和后台采集。 |
| `OPS-002` | `status` 应报告计划数、已尝试数、完整数、错误和运行状态。 |
| `OPS-003` | `stop` 应停止任务并保留已采数据；`resume` 应按原计划继续。 |

## 4. 数据完整性与归档

| ID | 需求 |
| --- | --- |
| `INT-001` | snapshot 应原子写入，避免将部分写入文件识别为有效样本。 |
| `INT-002` | 新 snapshot 应在 manifest 中记录 SHA-256。 |
| `INT-003` | `verify` 应检查格式、序列、region、payload 长度、哈希和计划样本数。 |
| `ARC-001` | `pack` 应在归档前执行验证，并默认拒绝不完整或损坏的 run。 |
| `ARC-002` | `unpack` 应拒绝路径穿越、链接、重复成员和超限归档。 |
| `ARC-003` | 归档和解包不得改变原始 snapshot 内容。 |

## 5. 平台数据与解码

| ID | 需求 |
| --- | --- |
| `XML-001` | 发布包应包含固定版本的 Intel PMT XML registry 及来源记录。 |
| `XML-002` | schema 应仅按精确 `GUID + Size` 匹配。 |
| `XML-003` | `validate-platform` 应分别报告 mapping 和 decoder schema 是否有效。 |
| `DEC-001` | `analyze` 应将原始 payload 解码为 metric、value 和 unit。 |
| `DEC-002` | 不支持的 schema、layout 或 formula 应明确失败，不得静默省略指标。 |
| `DEC-003` | 分析不得修改原始 run，并应记录输入、XML 和解码程序的内容指纹。 |

## 6. 分析输出

| ID | 需求 |
| --- | --- |
| `ANA-001` | `decoded.csv` 应保存解码观测值及其时间、endpoint、aggregator 和 schema 身份。 |
| `ANA-002` | `series.csv` 应区分 value、delta 和 rate，并标记 missing、reset、wrap 和 invalid。 |
| `ANA-003` | `summary.csv` 应提供 mean、min、max、p95、std、CV 和 valid count。 |
| `ANA-004` | `data-quality.csv` 应提供 expected、observed、valid、invalid 和 missing count。 |
| `ANA-005` | 提供 topology 时，工具应生成 system 到 aggregator 的分层视图，不得从 telem ID 猜测物理拓扑。 |
| `ANA-006` | 提供 events 时，工具应生成事件对齐、阶段统计和 failure window 输出。 |
| `ANA-007` | `compare` 应比较两次分析中身份匹配的 series。 |

## 7. 兼容性与可运维性

| ID | 需求 |
| --- | --- |
| `CMP-001` | 工具应继续读取既有 `intel-pmt-local-bulk/v1` run。 |
| `CMP-002` | 没有 SHA-256 字段的旧 manifest 应继续按旧格式验证。 |
| `OPS-004` | CLI 成功返回 0，操作失败返回 1，参数错误返回 2。 |
| `OPS-005` | 采集、验证和分析错误应包含可定位问题的上下文。 |
| `REL-001` | 发布包应包含运行代码、用户文档、配置示例、可选服务脚本和固定 XML。 |
| `REL-002` | 发布包解压后应能直接运行，不需要 pip 安装或构建步骤。 |

## 8. 当前范围

当前版本支持 GNR Linux OS 侧 PMT 采集与离线分析。已验证 schema 见
[GNR 兼容性矩阵](docs/compatibility.md)。SRF、OOB/Redfish 采集、SHC 日志解析、
自动异常检测和硬件故障归因不在当前范围内。

## 9. 发布验收

每个正式版本应满足：

1. 源码测试在 Python 3.7、3.10 和 3.13 全部通过；
2. 发布包无需构建即可显示版本和命令帮助；
3. 发布包包含固定 XML registry，且 XML 文件清单验证通过；
4. 代表性 GNR 主机完成三样本 discovery、capture、verify、validate 和 analyze；
5. `decoded.csv`、`series.csv`、`summary.csv` 和 `data-quality.csv` 成功生成；
6. 公开下载文件与完成 GNR 验证的文件一致。