# Intel PMT Capture and Analysis Toolkit

在 **GNR Linux 主机**上定时读取 **带内 PMT**（`/sys/class/intel_pmt/telem`*），保存 **raw 快照**，再用包内 **GNR XML** 离线解码，得到 **CSV 长表** 和 **离线 HTML 看板**。采集只读 sysfs，**不修改** BIOS/BMC/硬件配置。

当前版本：**0.8.0 GNR Edition**。需要 Python 3.7+、Bash、tar、gzip；**默认流程不需要 pip、数据库或联网**。

**下载：[pmt-raw-capture-0.8.0.tar.gz](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz)**

---

## 工具用途

- 在 **待测 GNR 主机的 Linux OS** 上，按间隔读取 **带内 PMT**（`/sys/class/intel_pmt/telem`*），保存 **raw**，再离线解码为 **decoded.csv / metrics.csv / dashboard.html**。
- 面向 **单次或长跑实验**：保留 raw、跨机器分析、离线交付 HTML；解码按 **GUID + Size** 精确匹配包内 GNR XML。
- **运行位置**：解压后的目录在 **待测机**上执行 `pmt-capture`。

**范围**：仅 **Linux 带内 sysfs**；BMC Redfish、持续 Prometheus/Grafana 监控见 Intel-PMT 仓库的 otel + 看板。

包内 **七组已验证 GNR schema**，见 [GNR 兼容性](docs/compatibility.md)。

---



## 默认工作流（三步）

```text
① start   → results/<run-id>/     （gzip raw 快照 + run.json）
② analyze → analysis/<run-id>/    （decoded.csv、metrics.csv、dashboard.html）
③ 浏览器打开 dashboard.html      （无需服务器）
```


| 输出                            | 含义                                                         |
| ----------------------------- | ---------------------------------------------------------- |
| `results/.../snapshots/`      | 每份采样的 **raw**（decode 前永久保留）                                |
| `decoded.csv`                 | **全部** XML 字段解码长表（含 DEADBEEF 等原值）                          |
| `metrics.csv`                 | 按 [GNR 配置](config/metrics-gnr.json) **派生** 的长表（增量、速率、桶占比等） |
| `dashboard.html`              | 从 metrics 生成的 **7 条** 关键趋势（离线 HTML）                        |
| `analysis.json`、`provenance/` | 校验结果、XML 指纹、公式来源                                           |


需要旧版多 CSV（summary、series、六层 view 等）时，analyze 加 `--legacy-analysis`，见 [操作指南](docs/guide.md)。

---



## 1. 安装

在 **待测 GNR 主机**上（不能联网时可从 Dev 拷贝 tar 包）：

```bash
curl -fL -O https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.8.0/pmt-raw-capture-0.8.0.tar.gz
tar -xzf pmt-raw-capture-0.8.0.tar.gz
cd pmt-raw-capture-0.8.0
./pmt-capture --version    # 应显示 0.8.0
```

首次建议确认 PMT 设备可见：

```bash
sudo ./pmt-capture inventory | head
```

---



## 2. 采集（`start`）



### 2.1 最短示例（约 1 分钟）

**计划**：每 **2 秒** 开始采 **1 份**，持续约 **60 秒**（共 **30 份**）。

```bash
sudo ./pmt-capture start --endpoint gnr-host --run-id trial-001 \
  --duration-seconds 60 --interval 2
```

- `--endpoint`：机器标签（字符串），写入 CSV，便于区分实验机。
- `--run-id`：本次实验目录名，结果在 `results/trial-001/`。
- 需要 **root/sudo**：读 `/sys/class/intel_pmt/`。



### 2.2 采多久：`--duration-seconds` 与 `--interval`

用 `--duration-seconds T` 表示希望覆盖的大致时长（秒），用 `--interval` 表示相邻两份 snapshot **计划开始** 的间隔（秒，可小数）。工具按 **N = ceil(T ÷ interval)** 计算一共采多少份。

示例：`--duration-seconds 60 --interval 2` → **30 份**。

（高级用法：也可只写 `--samples N`，与 `--duration-seconds` **二选一**。）

### 2.3 采样间隔

带内 bulk 采集的 **最快采样间隔为 0.2 秒**（`--interval` 最小 **0.2**，可更大）。

### 2.4 长任务：`--background`（后台采集）


| 模式                    | 终端                 | SSH 断开                  | 适用        |
| --------------------- | ------------------ | ----------------------- | --------- |
| **不加** `--background` | **一直占用**，直到采完      | 通常 **会打断** 采集           | 短任务（几分钟内） |
| **加** `--background`  | 启动后 **立刻返回** shell | 采集 **继续**（子进程 detached） | 数小时长跑     |


后台启动后终端会打印 **PID** 和 run 目录；采集输出在 `results/<run-id>/console.log`（可用 `tail -f` 跟踪）。**主机重启后不会自动续采**，PMT 恢复后需手动 `resume`。

示例（600 份 × 60 秒间隔，约 10 小时量级）：

```bash
sudo ./pmt-capture start --endpoint gnr-host --run-id experiment-001 \
  --interval 60 --samples 600 --background

sudo ./pmt-capture status --run-dir results/experiment-001
sudo ./pmt-capture stop --run-dir results/experiment-001
sudo ./pmt-capture resume --run-dir results/experiment-001 --background
tail -f results/experiment-001/console.log
```

子命令说明见 **§2.6** 或 `./pmt-capture status|stop|resume --help`；全参数见 [操作指南](docs/guide.md)。

### 2.5 `--cpu N`（采集进程绑 OS 逻辑 CPU）

```bash
sudo ./pmt-capture start ... --cpu 2
```

将 **pmt-capture 进程** 绑到 **Linux 逻辑 CPU N**（`sched_setaffinity`），`resume` 时从 `run.json` 沿用同一 N。仍读取 inventory 中 **全部** telem；与 XML **Core 编号**、PTAT 绑核无关（负载请单独 `taskset`）。

### 2.6 采集中常用命令

```bash
sudo ./pmt-capture status --run-dir results/trial-001
sudo ./pmt-capture stop --run-dir results/trial-001
sudo ./pmt-capture resume --run-dir results/trial-001 --background
sudo ./pmt-capture verify --run-dir results/trial-001
```

`verify` 检查 snapshot 数量、结构与 SHA；业务侧 poison/有效性见 [指标与看板](docs/report.md)。

---



## 3. 离线分析（`analyze`）

在 **能读 raw 目录** 的账户下（待测机或分析机均可）：

```bash
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001
```

- `--output` 必须是 **新目录**；失败不会覆盖已有分析或修改 raw。
- 成功后用浏览器打开 `analysis/trial-001/dashboard.html`（可拷贝到本机打开）。

跨主机：在采集端 `pack`，在分析端 `unpack`，见 [操作指南](docs/guide.md)。

仅要解码、不要 metrics/看板：

```bash
./pmt-capture analyze --run-dir results/trial-001 --output analysis/trial-001 --decode-only
```

---



## 4. 指标与看板（简要）

- **decoded**：XML 原样解码；**DEADBEEF、恒 0** 等仍会出现在 value 列。
- **metrics**：对 CORE schema（`0x22473996` / 14496 B）等 **已配置** 的 **47 项派生**（温度、usage 增量、PVP 速率、桶占比、加权频/压等）；公式见 [report.md](docs/report.md)。
- **usage 增量**为实验性计数差分；桶加权频/压为 **估计值**（公式见 report.md）。

仅从已有 metrics 重新生成 HTML：

```bash
./pmt-capture view --input analysis/trial-001/metrics.csv --output core-view.html
```

---



## 文档与支持


| 文档                               | 内容                            |
| -------------------------------- | ----------------------------- |
| [操作指南](docs/guide.md)            | 采集、pack/unpack、analyze、排障、legacy |
| [指标与看板](docs/report.md)          | 公式、validity、与 Grafana 差异      |
| [数据格式](docs/data-format.md)      | raw 快照字段                      |
| [GNR 兼容性](docs/compatibility.md) | Qualified GUID 列表             |
| [产品需求规格](REQUIREMENTS.md)        | 范围与验收                         |
| [支持说明](SUPPORT.md)               | 反馈问题时需附的信息                    |
| [更新记录](docs/changelog.md)        | 版本变更                          |


命令行帮助：`./pmt-capture --help`，`./pmt-capture start --help`。

旧版统计、事件对齐（`--events`）、`compare`、systemd 安装脚本仍保留兼容，**不在默认 README 流程中**；需要时见 [操作指南](docs/guide.md) 与 [服务部署](docs/service.md)。