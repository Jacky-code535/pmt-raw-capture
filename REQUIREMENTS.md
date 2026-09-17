# 需求与验收

本文件汇总当前产品需求及其验收状态。设计与版本记录见 [GNR 版本记录](docs/gnr-plan.md)，已验证硬件范围见 [GNR 兼容性](docs/compatibility.md)，真实主机证据见 [硬件资格记录](docs/qualification.md)。

## 支持的工作流

正式发布包支持在 GNR Linux 主机上独立完成：

```text
PMT discovery -> capture -> verify -> package -> unpack
-> exact XML validation -> decode -> series -> summary/data quality
```

## 需求状态

| ID | Requirement | 状态 | 实现/输出 | 验收证据 |
| --- | --- | --- | --- | --- |
| `REQ-GNR-001` | 自动发现 Linux PMT sysfs 区域并记录 AccessId、GUID、Size | 完成 | `inventory`、`run.json.Inventory` | discovery 单测、AVC01 36 regions |
| `REQ-CAP-001` | 按 interval 和 sample count 采集所有区域 | 完成 | `start`、`snapshots/` | capture 单测、AVC01 3/3 和 30/30 |
| `REQ-CAP-002` | 支持 status、stop、resume 和后台运行 | 完成 | CLI lifecycle | CLI/process 集成测试 |
| `REQ-CAP-003` | 单区域失败不得伪装成完整 snapshot | 完成 | `Capture.Complete/Errors` | incomplete/error 单测 |
| `REQ-RUN-001` | 每次使用独立 run ID，不覆盖旧 run | 完成 | `results/<run-id>` | existing-run 拒绝逻辑 |
| `REQ-RUN-002` | 新 snapshot 记录 SHA-256，打包和分析前校验 | 完成 | `manifest.ndjson.SHA256` | 篡改拒绝与旧格式兼容测试 |
| `REQ-RUN-003` | raw 可打包、安全解包并离线重放 | 完成 | `pack`、`unpack`、`archive` | traversal/link/size 集成测试 |
| `REQ-XML-001` | XML 采用固定版本并记录来源与内容哈希 | 完成 | bundled registry、`analysis.json` | 798 文件 SHA 清单 |
| `REQ-XML-002` | 只按精确 GUID + Size 选择 schema | 完成 | `validate-platform` | decoder/schema 单测、GNR 7/7 |
| `REQ-DEC-001` | raw 离线解码为 metric、value、unit | 完成 | `decoded.csv` | synthetic 和 AVC01 回归 |
| `REQ-DEC-002` | schema 或公式错误明确失败，不静默丢 metric | 完成 | strict `analyze` | unsupported formula 测试 |
| `REQ-SER-001` | 生成统一 series，并明确 missing/reset/wrap 等状态 | 完成 | `series.csv` | reconstruction 单测 |
| `REQ-STAT-001` | 生成 mean/min/max/p95/std/CV/valid_count | 完成 | `summary.csv` | 手算统计单测 |
| `REQ-QUAL-001` | 输出 observed/valid/invalid/missing 数据质量 | 完成 | `data-quality.csv` | 汇总测试、AVC01 32,098 series |
| `REQ-TOP-001` | 支持显式 topology，不从 telem ID 猜物理层级 | 完成 | topology CSV、scope views | topology 单测 |
| `REQ-REL-001` | 发布包可独立运行并通过 Python 3.7/3.10/3.13 | 完成 | GitHub Release、CI | extracted-package CI |
| `REQ-UX-001` | 普通用户只按 README 可完成三样本闭环 | 0.6.1 完成 | README exact workflow | 非 root handoff 测试、GNR replay |
| `REQ-SHC-001` | 为 SHC 保留通用时间事件输入边界 | 预留 | `--events`、adapter contract | [SHC 预留说明](docs/shc-integration.md) |

## 不支持的范围

- SRF 和其他平台资格；
- SHC log parser、自动 phase 识别和故障归因；
- OOB/Redfish collector；
- Grafana、Parquet 和异常检测模型；
- 对未确认 metric 的自动空间聚合。

以上功能不属于当前 GNR 版本的支持范围。

## 发布硬门槛

1. 源码和解压后的发布包全部自动测试通过；
2. Python 3.7、3.10、3.13 CI 通过；
3. bundled platform-data SHA 清单全部通过；
4. 最终发布字节在 GNR 完成三样本 capture-to-analysis；
5. 公开下载资产与已验证本地资产逐字节一致；
6. README 中的下载、权限、输出路径和预期结果经过新目录复现。