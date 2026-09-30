# v0.8.0 GNR Edition

将默认流程收敛为 bulk raw → 内置 GNR XML → decoded 长表 → metrics 长表 → Core 看板。

**下载：[pmt-raw-capture-0.8.0.tar.gz](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz)**

## 主要变化

- 新增 `start --duration-seconds`，与 `--samples` 二选一；间隔支持正小数。
- `analyze` 默认在同一目录生成 `decoded.csv`、`metrics.csv` 和 `dashboard.html`，另保留追溯信息。
- metrics 保持长表，包含已配置 Core 指标的区间增量、速率、桶占比和加权频率／电压估计。
- 不再默认生成多层视图、统计／事件 CSV 和 Excel，无需安装 XlsxWriter。
- 新增 `view --input metrics.csv --output view.html`，仅凭指标 CSV 重建离线看板。
- 看板使用真实时间轴，跨被省略的无效点断线；支持桌面和移动端。
- 包内仅保留七组已验证 GNR schema 及依赖，来自同一固定版本，schema 内容不变。

## 使用

```bash
sudo ./pmt-capture start --endpoint gnr-host --run-id trial-001 --duration-seconds 60 --interval 2
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001
```

打开 `analysis/trial-001/dashboard.html`。60 秒、2 秒间隔计划在第 0 至 58 秒启动 30 份采样；不是硬截止时间。长任务可加 `--background`。

## 兼容与边界

旧 raw v1 继续兼容。旧多层分析需显式使用 `--legacy-analysis`；只要原始解码表可用 `--decode-only`。`report` 现在生成长表 metrics 和 HTML，不再生成 Excel。

完整解码覆盖七组 GNR schema；派生配置目前覆盖 CORE 的 47 项指标。其他 schema 的观测保留在 decoded，不声称已完成全部语义转换。看板展示其中七项关键趋势，最多约 600 个实际显示点，完整时序在 CSV。

直方图加权值仍为 provisional 估计；usage 增量不是 CPU 利用率；离线相邻区间不是在线 Prometheus 五分钟滚动窗口。本版不部署 Grafana，不扩展硬件资格范围。

验证包含源码测试、真实 GNR raw 回放、完整输入的合成规模测试、包内 XML 检查和桌面／移动端浏览器检查。真实 raw 回放不等于重新上机采集；本次未进行新的硬件长跑。

使用说明见 [README](https://github.com/Jacky-code535/pmt-raw-capture#readme)。
