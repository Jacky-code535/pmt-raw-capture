# 支持与问题反馈

## 支持范围

当前正式验证范围为 [GNR 兼容性矩阵](docs/compatibility.md) 中列出的精确
`GUID + Size` 组合。发布包中包含更多 XML 不代表对应平台已经通过验证。
遇到未知组合时应保留 `inventory` 输出，不要手工选择相近 XML。

## 提交问题前

先在解压后的发布包根目录运行：

```bash
./pmt-capture --version
sha256sum -c ../pmt-raw-capture-0.6.1.tar.gz.sha256
bash scripts/smoke_test.sh
sudo ./pmt-capture inventory > inventory.json
sudo ./pmt-capture status --run-dir results/<run-id> --json > status.json
./pmt-capture validate-platform --run-dir results/<run-id> > validation.json
```

问题描述应包含工具版本、Linux 内核版本、执行的完整命令、退出码和错误信息。
采集问题还应提供对应 `collector.log`。若 `validate-platform` 已失败，不要继续用近似
schema 解码。

## 数据处理

raw snapshot、inventory、validation、日志和分析结果可能包含平台或实验信息。只通过
团队批准的私有渠道传输，不要上传到公共 GitHub Issue、源码仓库或 Release。公共 Issue
只用于不含平台数据的通用软件问题。

## 分发边界

源码仓库当前未附加开源许可证，公开可见不等于获得复制或再分发授权。发布包
还包含采用独立许可证的 Intel PMT platform data。工具和发布包仅应在已批准的
组织与用途范围内分享；对外分发前必须完成相应许可审批。