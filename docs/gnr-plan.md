# GNR 工具计划与验收

## 目标

0.6.x GNR Edition 提供以下完整工作流：

```text
inventory -> capture -> verify/pack -> unpack -> validate-platform -> analyze
```

当前不扩展 SRF、OOB、Grafana、异常检测或自动故障结论。SHC 仅保留通用时间事件接口，不引入 SHC 依赖。

## Phase 0：冻结 GNR 范围与需求基线

| 要求 | 状态 | 验收方式 |
| --- | --- | --- |
| GNR PMT discovery 与多区域采集 | 已完成 | `inventory` 和三次短采集 |
| 独立 run、停止、续采和状态查询 | 已完成 | CLI 集成测试和实际主机测试 |
| raw 打包、解包和离线重放 | 已完成 | pack/unpack/verify 闭环 |
| 固定 XML、精确 GUID + Size 匹配 | 已完成 | run-scoped `validate-platform` |
| 内置解码、series 和 summary | 已完成 | `analyze` 输出检查 |
| snapshot SHA-256 | 0.6.0 完成 | 修改文件后 `verify` 必须失败 |
| Data Quality | 0.6.0 完成 | `data-quality.csv` 与 series 对账 |
| GNR 硬件资格边界 | 0.6.0 固化 | 见兼容性与资格记录 |
| 发布包可复现入口 | 0.6.1 完成 | 根目录 requirement、checksum、README 闭环 |
| SHC adapter | 预留 | 不影响当前采集和分析 |

GNR 支持仅指[兼容性](compatibility.md)中列出的已验证 inventory。registry 中存在其他 GNR mapping 不等于已经通过硬件资格测试。

## Phase 1：Run Package 与完整性

保留 `intel-pmt-local-bulk/v1`，不重写为 continuous binary。每次 snapshot 已包含原始 payload、GUID、Size、采集时间、完整状态和错误信息；独立 gzip 文件更适合中断后保留已完成样本。

0.6.0 为每个新 snapshot 在 `manifest.ndjson` 增加 SHA-256。`verify`、`pack` 和 `analyze` 会在读取前检查 run；旧 manifest 没有 SHA 字段时继续按原有结构校验，保持向后兼容。

验收条件：

1. 新 run 不覆盖已有目录；
2. 修改 snapshot 后校验失败；
3. pack/unpack 后原始 snapshot 哈希不变；
4. analyze 不修改 raw run；
5. 中断和不完整样本不会伪装成完整采集。

## Phase 2：Decode 错误策略

当前不增加 best-effort 模式。GNR 正式流程先执行 run-scoped `validate-platform`，确认本次 inventory 的全部 schema 可加载，再执行严格 `analyze`。任何 GUID、Size、schema 或公式错误都使分析失败，已保存 raw 不受影响。

这样比“跳过失败 metric 后继续”更适合当前阶段：用户不会得到缺少部分指标但看似成功的结果，也不需要理解额外模式。只有将来遇到明确的现场诊断需求，才评估逐 metric 错误隔离。

## Phase 3：Data Quality 与统计

保留 `summary.csv` 的现有字段和统计定义，新增一张轻量 `data-quality.csv`，用于回答每条序列是否采齐、是否存在不可用于统计的值。

| 字段 | 含义 |
| --- | --- |
| `expected_count` | run 计划样本数 |
| `observed_count` | 该序列实际生成的记录数 |
| `valid_count` | 可参与统计的有限数值数量 |
| `invalid_count` | 有记录但值不可参与统计的数量 |
| `missing_count` | 计划数减去观测数，最小为 0 |
| `valid_rate` | valid_count / expected_count |
| `first_timestamp` / `last_timestamp` | 该序列观测时间范围 |

这是一张数据完整性表，不判断硬件健康。counter 的首个 delta/rate 没有前值，因此对应记录会计入 invalid，这是正常时间序列语义。

## 同事使用验收

在一台 GNR 主机上执行 README 的三次短采集流程，应满足：

1. `inventory` 至少发现一个 PMT 区域；
2. 三份 snapshot 均为 complete；
3. `pack` 和 `unpack` 成功；
4. `validate-platform` 的 `mapping_valid` 和 `valid` 均为 true；
5. `analyze` 生成非空 `decoded.csv`、`series.csv`、`summary.csv` 和 `data-quality.csv`；
6. `analysis.json` 记录 raw、XML 和 decoder 的内容指纹。

如果本机 GUID + Size 不在兼容矩阵中，应保存 `inventory` 输出并联系工具维护者，不应手工选择近似 XML。

## 后续顺序

1. 收集其他 GNR inventory，并逐组完成 run-scoped schema 与真实 payload 验证；
2. 把通过的 inventory 增加到兼容矩阵；
3. 根据真实使用反馈改善错误信息和输出规模；
4. SHC 数据结构明确后，实现独立 adapter，将事件转换为现有通用事件格式；
5. SRF 和其他平台另立资格任务，不阻塞 GNR 工具使用。