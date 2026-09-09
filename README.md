# PMT Raw Capture

Intel PMT 原始遥测采集工具。在 Linux 上读取 `/sys/class/intel_pmt/telem*`，按指定间隔保存 gzip 压缩的 JSON 快照，支持后台采集、停止续采、数据校验和归档导出。

采集阶段保留原始字节，不依赖 XML 或解码器。输出格式见 [DATA-FORMAT.md](DATA-FORMAT.md)。

[下载 v0.4.2](https://github.com/Jacky-code535/pmt-raw-capture/releases/tag/v0.4.2) | [更新记录](CHANGELOG.md) | [CI](https://github.com/Jacky-code535/pmt-raw-capture/actions)

## 下载

从 Release 的 Assets 下载 `pmt-system-debug-0.4.2.tar.gz` 和 `pmt-system-debug-0.4.2.tar.gz.sha256`，放到被测主机的同一目录，然后校验：

```bash
sha256sum -c pmt-system-debug-0.4.2.tar.gz.sha256
```

预期显示 `pmt-system-debug-0.4.2.tar.gz: OK`。校验失败时重新下载。

## 环境要求

| 要求 | 说明 |
| --- | --- |
| 运行位置 | 被测主机的 Linux OS |
| 软件 | Bash、Python 3.7+；解压需要 tar 和 gzip，无需安装 pip 包 |
| PMT 接口 | `/sys/class/intel_pmt/telem*`，区域中有 `guid`、`size`、`telem` |
| 权限和磁盘 | 能读取 PMT、写入本地结果目录，并有足够空间；以下采集示例使用 sudo |

工具自动发现 PMT 区域，设备数量取决于平台和驱动。采集无需网络连接；systemd 仅用于可选的服务部署。

## 快速开始

### 解压并查看设备

```bash
tar -xzf pmt-system-debug-0.4.2.tar.gz
cd pmt-system-debug-0.4.2
python3 --version
./pmt-capture --version
sudo ./pmt-capture inventory
```

版本应显示 `0.4.2`。`inventory` 列出各区域的 AccessId、GUID、字节数和路径。

### 采集三份快照

将 `lab-host` 替换为机器标签。以下命令每隔 10 秒采集一份，共三份：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id trial-001 \
  --interval 10 --samples 3 --output-root ./results
```

第一份立即采集，三份约需 20 秒加读写时间。控制台逐份输出 `sequence`、`file`、
`complete` 和 `duration_ms`。默认前台运行，保持终端打开；Ctrl+C 可停止。

采集结束后查看状态：

```bash
sudo ./pmt-capture status --run-dir ./results/trial-001
```

预期为 `collection: completed`、`busy: False`、`completed: 3`、`complete: 3`、
`incomplete: 0`；检查前 `verification: not_checked` 是正常的。
`completed` 表示尝试了多少份，并不保证每一份都读取完整。

### 校验并打包

```bash
sudo ./pmt-capture pack --run-dir ./results/trial-001 --output ./output
```

`pack` 检查快照格式、区域信息、数据长度、序列和采样份数，通过后生成
`output/pmt-capture-trial-001.tar.gz`。包内 `result.txt` 记录 `Collection: COMPLETE` 和快照份数。
先用三份试采确认平台读取和分析端解码正常，再开始长时间采集。

## 命令参考

统一格式：`./pmt-capture 命令 参数`。查看总帮助用 `--help`，查看版本用 `--version`。

| 命令 | 用途 | 参数或示例 |
| --- | --- | --- |
| `inventory` | 查看当前机器的 PMT 区域 | `sudo ./pmt-capture inventory` |
| `start` | 新建任务并定时采集 | 见上面的三份试采命令 |
| `status` | 查看进度、运行状态和上次检查结果 | `--run-dir ./results/trial-001`；加 `--json` 输出 JSON |
| `stop` | 请求停止采集，保留已有数据 | `--run-dir ./results/trial-001` |
| `resume` | 按原参数继续采剩余份数 | `--run-dir ./results/trial-001`；可加 `--background` |
| `verify` | 只检查结果，不打包 | `--run-dir ./results/trial-001` |
| `pack` | 检查并打包整次任务 | `--run-dir ./results/trial-001 --output ./output` |
| `dump` | 将单份压缩快照输出为 JSON，不解码指标 | `sudo ./pmt-capture dump ./results/trial-001/snapshots/bulk-000001-*.json.gz` |

详细选项：`./pmt-capture <command> --help`。

### 采集参数

| 参数 | 含义 |
| --- | --- |
| `--endpoint lab-host` | 必填，机器标签；不是网络地址 |
| `--samples 3` | 必填，计划采样份数，正整数 |
| `--interval 10` | 采样间隔，单位秒，可为正小数，默认 60；也可写 `--interval-seconds` |
| `--run-id trial-001` | 本次任务名；省略时自动生成。新实验换名字，续采不要改目录名 |
| `--output-root ./results` | 结果父目录，默认当前目录下的 `results` |
| `--background` | 后台运行，可断开终端；不会在重启后自动恢复 |
| `--experiment` / `--workload` / `--note` | 可选实验标签、负载标签和备注，仅记录文字，不启动负载 |

机器标签和任务名使用英文字母、数字、点、下划线或连字符。采样不是硬实时；
读写慢时实际间隔可能变长。多个 PMT 区域按顺序读取，不是同一瞬间的原子快照。

## 长时间采集

每分钟一份，共 600 份，约 10 小时：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id experiment-001 \
  --interval 60 --samples 600 --output-root ./results --background
sudo ./pmt-capture status --run-dir ./results/experiment-001
```

停止任务后，用 `status` 确认 `busy: False`：

```bash
sudo ./pmt-capture stop --run-dir ./results/experiment-001
sudo ./pmt-capture status --run-dir ./results/experiment-001
```

需要继续时运行：

```bash
sudo ./pmt-capture resume --run-dir ./results/experiment-001 --background
```

续采沿用原间隔和目标份数，不补造停机期间的数据。采完后用 `pack` 打包对应任务目录。
`completed/requested` 是已尝试份数和计划份数，`incomplete` 是读取不完整的份数。
`collection: completed` 表示尝试次数已达目标；最终以 `pack` 检查成功为准。

每次实验使用独立的 `--run-id`，`--run-dir` 指向完整任务目录。保持目录名称和内容不变；
PMT 区域、GUID 或 Size 改变后应新建任务。主机重启后，CLI 任务需要在 PMT 接口恢复后手动续采。

长时间运行时可用 `df -h ./results` 检查剩余空间。启动前的空间估算不预留磁盘。

## 结果文件

| 路径 | 内容 |
| --- | --- |
| `results/<run-id>/snapshots/bulk-*.json.gz` | 每轮原始数据，含 GUID、长度、时间戳和 Base64 编码的原始字节 |
| `results/<run-id>/run.json` | 机器信息、采集参数和任务状态 |
| `results/<run-id>/manifest.ndjson` | 每份快照的文件名和采集摘要 |
| `results/<run-id>/collector.log` | 采集事件；后台启动输出另见 `console.log` |
| `output/pmt-capture-<run-id>.tar.gz` | 交付包，含快照、日志、检查报告和 `result.txt` 摘要 |

分析端按 `GUID + Size` 选择平台元数据并解码。交接时附上工具版本、平台与内核、实验负载、
采集时间范围及暂停记录。数据字段见 [DATA-FORMAT.md](DATA-FORMAT.md)。

结果包包含主机信息、实验备注和原始遥测，应通过团队的数据传输渠道交接，不提交到源码仓库、
Issues 或 Release。如需由当前用户传输 root 创建的归档：

```bash
sudo chown "$(id -u):$(id -g)" ./output/pmt-capture-trial-001.tar.gz
```

## 服务部署与脚本

| 脚本 | 用途 |
| --- | --- |
| `run.sh` | 可选的 systemd 服务菜单，管理安装的任务，不管理普通 CLI 任务 |
| `install.sh` | 将工具安装到 `/opt/pmt-system-debug` 并创建采集服务；默认立即启动 |
| `uninstall.sh` | 停止并卸载已安装的服务和工具，保留采集数据；不停止独立 CLI 任务 |
| `build-package.sh` | 维护者生成工具发布包到 `dist/`，不是打包实验结果 |
| `pmt_capture_cli.py` / `pmt_bulk_capture.py` | 命令行和采集核心实现，通常无需直接调用 |
| `field-kit/*.sh` | 菜单调用的辅助脚本，具体用途见可选服务说明 |

服务部署和开机续采配置见 [systemd 文档](field-kit/USER-GUIDE.zh-CN.md)。

## 常见问题

| 情况 | 处理 |
| --- | --- |
| 找不到 PMT 区域或读取失败 | 检查驱动节点和读取权限；工具不会自动配置 BIOS 或加载驱动 |
| 任务目录已存在 | 新实验更换 `--run-id`，原任务使用 `resume` |
| 后台没开始或中途停止 | 用 `status` 看 `last_error`，再看任务目录中的 `console.log`、`collector.log` 和磁盘空间 |
| 未采满也需要交付 | 停止后执行 `pack ... --allow-partial`，不完整结果包带 `-partial`，仅供诊断 |
| 同名结果包已存在 | 更换 `pack --output` 目录；工具不会覆盖旧包 |
| `cannot pack symbolic link` | 任务目录必须包含实际文件；恢复符号链接指向的真实文件后再打包，`--allow-partial` 不绕过此检查 |
| `run is busy` | 任务正在采集或被其他命令锁定；先停止并确认 `busy: False`，不要删除锁文件 |
| `complete` 小于 `completed` | 至少一轮读取不完整；查看日志和快照内 `Capture.Errors`，不能把采够次数当作数据完整 |
| `Permission denied` | 确认执行权限和读取权限；对 PMT 读取及 root 所有的任务使用 sudo，勿放宽整个目录权限 |
| 检查报告显示 `stale` | 任务在上次检查之后变化；停止任务后重新 `verify` 或直接 `pack` |

命令退出码：0 成功，1 操作或检查失败，2 参数错误。正常提前停止也返回 0，不代表采满。

## 开发

```bash
python3 -m unittest discover -s tests -v
./build-package.sh
```

构建产物位于 `dist/`，包含白名单源码压缩包及 SHA-256 校验文件。
CI 在 Python 3.7、3.10、3.13 上运行测试，并验证解压后的发布包。
测试使用模拟 PMT 数据；真实硬件、systemd 安装、重启和长时间采集需在目标平台验证。

发布流程及分发权限见 [PUBLISHING.md](PUBLISHING.md)。