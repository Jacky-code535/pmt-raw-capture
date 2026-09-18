# 支持与问题反馈

## 支持范围

当前正式验证范围为 [GNR 兼容性矩阵](docs/compatibility.md) 中列出的精确
`GUID + Size` 组合。发布包中包含更多 XML 不代表对应平台已经通过验证。
遇到未知组合时请保留 `inventory` 输出。

## 提交问题前

先在解压后的发布包根目录运行：

```bash
./pmt-capture --version
sudo ./pmt-capture inventory > inventory.json
sudo ./pmt-capture status --run-dir results/trial-001 --json > status.json
sudo ./pmt-capture validate-platform --run-dir results/trial-001 > validation.json
```

问题描述应包含工具版本、Linux 内核版本、执行的完整命令、退出码和错误信息。
采集问题还应提供对应 `collector.log`。