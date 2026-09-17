# v0.6.1 GNR Edition

Intel PMT Capture and Analysis Toolkit 0.6.1 为 GNR Linux 提供一套命令行工作流，
覆盖 PMT 设备发现、原始数据采集、完整性检查、结果打包、XML 验证、指标解码、
时间序列重建和统计分析。

## Download

请下载以下两个文件：

- `pmt-raw-capture-0.6.1.tar.gz`：包含已批准 XML registry 的可运行工具包；
- `pmt-raw-capture-0.6.1.tar.gz.sha256`：用于验证下载内容的 checksum。

第一次使用请从 [README](https://github.com/Jacky-code535/pmt-raw-capture#readme)
开始。团队交接、准备条件和可直接转发的介绍见
[同事使用与介绍指南](https://github.com/Jacky-code535/pmt-raw-capture/blob/main/docs/colleague-guide.md)。

## Main outputs

- `decoded.csv`：解码后的 PMT 值；
- `series.csv`：包含有效性状态的 value、delta 和 rate；
- `summary.csv`：mean、min、max、p95、standard deviation 和 CV；
- `data-quality.csv`：expected、observed、valid、invalid 和 missing 数量。

## Support boundary

正式验证范围是 AVC01 上观察到的七组精确 `GUID + Size` schema。发布包中存在 XML
不代表对应平台已经通过资格验证。长时间采集前请查看
[GNR 兼容性矩阵](https://github.com/Jacky-code535/pmt-raw-capture/blob/main/docs/compatibility.md)。

本版本提供独立 SHA-256 文件。通过 `sudo pack` 生成的结果包会以 `0640` 权限交还给
原 sudo 用户，后续可直接由该用户解包和分析。
