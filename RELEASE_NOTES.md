# v0.6.3 GNR Edition

Intel PMT Capture and Analysis Toolkit 0.6.3 为 GNR Linux 提供一套命令行工作流，
覆盖 PMT 设备发现、原始数据采集、完整性检查、结果打包、XML 验证、指标解码、
时间序列重建和统计分析。

## Download

下载 `pmt-raw-capture-0.6.3.tar.gz`，解压后即可运行。工具包包含采集、解码、
分析程序以及 GNR 所需的 XML registry。

第一次使用请从 [README](https://github.com/Jacky-code535/pmt-raw-capture#readme)
开始，完整命令参数和排障方法见
[使用指南](https://github.com/Jacky-code535/pmt-raw-capture/blob/main/docs/usage.md)。

## Main outputs

- `decoded.csv`：解码后的 PMT 值；
- `series.csv`：包含有效性状态的 value、delta 和 rate；
- `summary.csv`：mean、min、max、p95、standard deviation 和 CV；
- `data-quality.csv`：expected、observed、valid、invalid 和 missing 数量。

## Support boundary

正式验证范围是兼容性矩阵中的七组精确 `GUID + Size` schema。长时间采集前请查看
[GNR 兼容性矩阵](https://github.com/Jacky-code535/pmt-raw-capture/blob/main/docs/compatibility.md)。

0.6.3 简化了首次使用流程：只下载一个压缩包，本机采集后可直接验证和分析；只有
需要传输结果时才使用 `pack` 和 `unpack`。下载包只包含运行程序、用户文档、配置
样例和可选服务脚本，开发测试与构建资料保留在源码仓库。
