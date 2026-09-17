# 同事使用与介绍指南

本文用于把 Intel PMT Capture and Analysis Toolkit 交给新的使用者。首次使用只需阅读
[README](../README.md) 和本文，不需要了解源码结构。

## 一句话介绍

Intel PMT Capture and Analysis Toolkit 是一个面向 GNR Linux 主机的命令行工具，
可以采集 Intel PMT 原始遥测，验证数据完整性，按平台 XML 解码，并输出可用于筛选、
绘图和对比的 CSV 结果。

## 它解决什么问题

一次完整使用包含以下阶段：

```text
发现 PMT 设备
  -> 定时采集原始数据
  -> 检查并打包采集结果
  -> 验证平台 XML 是否精确匹配
  -> 解码指标并重建时间序列
  -> 输出统计摘要和数据质量
```

| 需求 | 工具提供的能力 |
| --- | --- |
| 确认主机暴露了哪些 PMT 数据 | `inventory` 输出区域、GUID 和 Size |
| 进行短时间或长时间采集 | `start` 支持采样间隔、样本数和后台运行 |
| 中途查看、停止和恢复 | `status`、`stop`、`resume` |
| 判断采集是否完整 | `verify` 检查快照数量、结构、长度和 SHA-256 |
| 把一次采集交给其他人分析 | `pack` 生成独立结果包，`unpack` 安全解包 |
| 确认当前平台可否解码 | `validate-platform` 按精确 `GUID + Size` 验证 |
| 生成可读数据 | `analyze` 输出 decoded、series、summary 和 data-quality CSV |
| 比较正常与异常实验 | `compare` 输出两次分析之间的统计差异 |

工具不会修改 BIOS、PMT 配置或实验负载，也不会自动判断硬件故障根因。

## 使用者需要准备什么

| 项目 | 要求 | 为什么需要 |
| --- | --- | --- |
| 主机 | GNR Linux，存在 `/sys/class/intel_pmt/telem*` | 这是采集数据来源 |
| 权限 | 可以使用 `sudo` 读取 PMT | 普通用户通常不能直接读取设备节点 |
| 软件 | Python 3.7+、Bash、tar、gzip、sha256sum | 工具运行和解包所需，无需 pip 安装 |
| 磁盘 | 能保存计划样本和分析 CSV | 长时间采集前需自行确认容量 |
| 文件 | 发布包及其 `.sha256` 文件 | 工具、解码器和批准的 XML 均在发布包中 |

当前正式验证范围是 [GNR 兼容性矩阵](compatibility.md) 中的七组 `GUID + Size`。
其他 inventory 即使能被发现，也不自动代表已经通过解码验证。

## 第一次使用的验收标准

按 [README 第一次使用](../README.md) 完成三样本检查。成功时应同时满足：

1. 下载 checksum 显示 `OK`，工具版本为 `0.6.1`；
2. smoke test 显示两项测试通过；
3. 采集输出三行 `"complete":true`；
4. `verify` 显示所有观测文件有效且达到计划样本数；
5. `validate-platform` 的 `mapping_valid` 和 `valid` 都为 `true`；
6. `decoded.csv`、`series.csv`、`summary.csv` 和 `data-quality.csv` 均非空。

首次三样本检查通过后，再根据实验时长调整 `--interval` 和 `--samples`。例如每分钟
一份、持续约十小时：

```bash
sudo ./pmt-capture start --endpoint <machine-name> \
  --run-id <experiment-id> --platform GNR \
  --interval 60 --samples 600 --background
sudo ./pmt-capture status --run-dir results/<experiment-id>
```

## 结果怎么交接

采集完成后执行：

```bash
sudo ./pmt-capture verify --run-dir results/<experiment-id>
sudo ./pmt-capture pack --run-dir results/<experiment-id> --output packages
```

交接内容应包括：

- `packages/pmt-capture-<experiment-id>.tar.gz`；
- 工具版本和主机名称；
- 采集起止时间、采样间隔和计划样本数；
- 测试项目、负载和失败时间等实验背景；
- 中途暂停、重启、磁盘不足或 PMT 读取错误等异常记录。

结果包和日志可能包含平台或实验信息，只能通过团队批准的私有渠道交接。

## 角色与责任

工具维护者负责：

- 发布经过 checksum、自动测试和 GNR 实机验证的工具包；
- 维护支持矩阵、XML 版本、解码逻辑和已知限制；
- 根据完整的问题材料判断是工具缺陷、平台差异还是数据问题。

使用者负责：

- 确认目标主机、权限、磁盘和实验窗口；
- 使用唯一的 run ID，并记录实验条件；
- 先完成三样本检查，再启动长时间采集；
- 不用相近 XML 替代失败的精确 schema 匹配；
- 通过批准渠道传输 raw 数据和日志。

## 可直接转发的介绍文字

```text
我们使用 Intel PMT Capture and Analysis Toolkit 0.6.1 在 GNR Linux 主机采集和
分析 Intel PMT 遥测。工具直接读取 Linux PMT sysfs，不修改硬件配置，不需要安装
额外 Python 包。它可以完成设备发现、定时采集、完整性检查、结果打包、XML 精确匹配、
指标解码、时间序列重建、统计摘要和数据质量输出。

请先下载 pmt-raw-capture-0.6.1.tar.gz 及对应的 .sha256 文件，按照 README 完成
三样本检查。三样本通过后再配置正式采样间隔和样本数。遇到问题时请保留 inventory、
validation、collector.log、完整命令和错误信息；不要将 raw 数据上传到公共 GitHub。
```

## 出现问题时

先查看[使用指南的常见问题](usage.md)和[支持说明](../SUPPORT.md)。反馈时至少提供：

- `./pmt-capture --version` 输出；
- Linux 内核版本；
- 执行的完整命令和退出码；
- `inventory-*.json`、`validation-*.json` 和 `collector.log`；
- 问题发生时间及实验是否仍在运行。

若材料包含平台数据，使用团队批准的私有渠道，不要放入公共 Issue。