# PMT Raw Capture

在 Linux 上定时采集 Intel PMT 原始数据，保存到本地，实验结束后交给分析端解码。
不需要 XML 或 decoder，不自动上传数据，也不判断硬件健康。当前版本：**0.4.2**。

这是给获准同事使用的**原始数据采集工具**，不是 PMT 解码器或健康诊断系统。
普通使用只需运行 `pmt-capture`，不用先运行安装器、菜单或其他脚本。

完整流程：取得发布包 → 在待测机器确认 PMT 接口 → 三份试采 → 检查并打包 →
确认分析端能读取后再进行长实验。所有采集命令都在**待测机器的 Linux OS**中执行。

## 0. 获取正确的版本

私人仓库：[Jacky-code535/pmt-raw-capture](https://github.com/Jacky-code535/pmt-raw-capture)。
先请仓库所有者授予访问权限，再用自己的 GitHub 账号登录；显示 404 时先检查账号和邀请。
无需在采集脚本中填写 GitHub 密码、令牌或 BMC 凭据。

在仓库 **Releases → v0.4.2 → Assets** 中下载以下两个附件，并通过获准渠道传到待测机器：

- `pmt-system-debug-0.4.2.tar.gz`：可直接运行的工具包。
- `pmt-system-debug-0.4.2.tar.gz.sha256`：下载完整性校验文件。

优先使用上述附件，不要把 GitHub 自动生成的 `Source code` 压缩包与它混用。
将两个附件放在同一目录，执行：

```bash
sha256sum -c pmt-system-debug-0.4.2.tar.gz.sha256
```

预期显示 `pmt-system-debug-0.4.2.tar.gz: OK`。失败时停止使用并重新下载；
SHA-256 用于检查文件是否一致，不是代码签名，也不能代替确认下载来源。

## 1. 运行环境

| 要求 | 说明 |
| --- | --- |
| 运行位置 | 待测机器的 Linux OS；开发机只负责连接和传包 |
| 软件 | Bash、Python 3.7+；解压需要 tar 和 gzip，无需安装 pip 包 |
| PMT 接口 | `/sys/class/intel_pmt/telem*`，区域中有 `guid`、`size`、`telem` |
| 权限和磁盘 | 能读取 PMT、写入本地结果目录，并有足够空间；以下采集示例使用 sudo |

工具自动发现 PMT 区域，不固定 CPU 型号。没有 PMT 接口时，需要先确认平台和驱动支持。
普通采集不需要安装服务，也不需要 systemd。换平台后先做三份试采。

`inventory` 只发现设备和元信息，不能代替真正读取数据的试采。采样不修改 PMT 配置，
但仍会产生硬件读取、CPU 和磁盘开销；不要未经验证就在生产机器使用很短的间隔。
采集主机不需要联网。发布包构建和 GitHub 下载所需的网络不属于采集运行依赖。

## 2. 解压并试采

把工具包放到待测机器，在该机器的终端依次运行：

```bash
tar -xzf pmt-system-debug-0.4.2.tar.gz
cd pmt-system-debug-0.4.2
python3 --version
./pmt-capture --version
sudo ./pmt-capture inventory
```

版本应显示 `0.4.2`。`inventory` 列出各区域的 AccessId、GUID、字节数和路径；
不同平台的数量可能不同，不要套用其他机器的固定数量。
下面将 `lab-host` 替换为团队认可的机器标签，然后每隔 10 秒采一份，共三份：

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

采完后打包，成功时打印结果包路径：

```bash
sudo ./pmt-capture pack --run-dir ./results/trial-001 --output ./output
```

将 `output/pmt-capture-trial-001.tar.gz` 交给分析同事。
**pack 已包含文件和份数检查，不需要先单独运行 verify。**

成功标准是 `pack` 退出码为 0，并生成不带 `-partial` 的包；包内 `result.txt`
应显示 `Collection: COMPLETE`。这只说明采集数据通过文件和份数检查，不说明硬件健康。
建议先让分析同事确认这三份能被目标 decoder 读取，再开始长实验。

## 3. 每条命令做什么

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

例如查看进度：`sudo ./pmt-capture status --run-dir ./results/trial-001`。
查看任一命令的全部选项：`./pmt-capture start --help`，将 `start` 换成相应命令即可。

### start 常用参数

| 参数 | 含义 |
| --- | --- |
| `--endpoint lab-host` | 必填，机器标签，不是 IP 地址，脚本不会用它远程连接 |
| `--samples 3` | 必填，计划采样份数，正整数 |
| `--interval 10` | 采样间隔，单位秒，可为正小数，默认 60；也可写 `--interval-seconds` |
| `--run-id trial-001` | 本次任务名；省略时自动生成。新实验换名字，续采不要改目录名 |
| `--output-root ./results` | 结果父目录，默认当前目录下的 `results` |
| `--background` | 后台运行，可断开终端；不会在重启后自动恢复 |
| `--experiment` / `--workload` / `--note` | 可选实验标签、负载标签和备注，仅记录文字，不启动负载 |

机器标签和任务名使用英文字母、数字、点、下划线或连字符。采样不是硬实时；
读写慢时实际间隔可能变长。多个 PMT 区域按顺序读取，不是同一瞬间的原子快照。

## 4. 长实验：后台、停止和续采

每分钟一份，共 600 份，约 10 小时：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id experiment-001 \
  --interval 60 --samples 600 --output-root ./results --background
sudo ./pmt-capture status --run-dir ./results/experiment-001
```

需要暂停时运行 `stop`，再用 `status` 确认 `busy: false`：

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

每个实验使用唯一的 `--run-id`。`--run-dir` 必须指向整次任务目录，不能只指向
`snapshots/`，也不要重命名任务目录。重启、断电或被强制结束后，后台 CLI 不会自动重启；
确认 PMT 接口恢复后手动 `resume`。如果 PMT 区域、GUID 或 Size 改变，应结束旧任务，
重新建立基线并开始新任务，不要修改旧任务的数据来绕过检查。

运行期间不要删除、编辑或移动结果文件，也不要用两个入口同时操作同一任务。
持续查看磁盘空间，例如 `df -h ./results`；启动前的空间估算不能预留磁盘，其他进程也可能写满磁盘。

## 5. 结果保存在哪里

| 路径 | 内容 |
| --- | --- |
| `results/<run-id>/snapshots/bulk-*.json.gz` | 每轮原始数据，含 GUID、长度、时间戳和 Base64 编码的原始字节 |
| `results/<run-id>/run.json` | 机器信息、采集参数和任务状态 |
| `results/<run-id>/manifest.ndjson` | 每份快照的文件名和采集摘要 |
| `results/<run-id>/collector.log` | 采集事件；后台启动输出另见 `console.log` |
| `output/pmt-capture-<run-id>.tar.gz` | 交付包，含快照、日志、检查报告和 `result.txt` 摘要 |

分析端需要匹配平台的元数据和兼容 decoder，数据字段见 [DATA-FORMAT.md](DATA-FORMAT.md)。
结果可能包含机器信息和敏感遥测，只分享给获准接收的人，不放进公开源码仓库。

同样不要把结果提交到这个**私人源码仓库**、Issues 或 Release 附件。结果包包含 hostname、
内核版本、BootId、任务标签、备注和原始遥测；不要在 `--note` 等参数中填写密码或令牌。
工具不会自动上传，也不会替你脱敏。

以 `sudo` 采集时，结果通常属于 root。若当前获准用户需要传输结果包，可仅转交该归档：

```bash
sudo chown "$(id -u):$(id -g)" ./output/pmt-capture-trial-001.tar.gz
```

不需要把整个结果目录改为所有人可读写，也不要使用 `chmod 777`。

交接时附上：工具版本、任务名、获准的机器标签、CPU/平台和内核信息、实验负载、实际采集
时间范围及是否暂停过；分析同事负责准备匹配 `GUID + Size` 的获准元数据和 decoder。
保留原始任务目录，收到结果包且确认可读取后，再按团队数据保留规则处理。

## 6. 其他脚本做什么

普通采集只使用 `pmt-capture`，下列脚本不需要依次执行。

| 脚本 | 用途 |
| --- | --- |
| `run.sh` | 可选的 systemd 服务菜单，管理安装的任务，不管理普通 CLI 任务 |
| `install.sh` | 将工具安装到 `/opt/pmt-system-debug` 并创建采集服务；默认立即启动 |
| `uninstall.sh` | 停止并卸载已安装的服务和工具，保留采集数据；不停止独立 CLI 任务 |
| `build-package.sh` | 维护者生成工具发布包到 `dist/`，不是打包实验结果 |
| `pmt_capture_cli.py` / `pmt_bulk_capture.py` | 命令行和采集核心实现，通常无需直接调用 |
| `field-kit/*.sh` | 菜单调用的辅助脚本，具体用途见可选服务说明 |

前三个脚本可用 `--help` 查看帮助。需要开机续采时再看 [可选服务说明](field-kit/USER-GUIDE.zh-CN.md)。

## 7. 常见问题

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

## 8. 验证范围和使用边界

- 自动化测试覆盖模拟 PMT 读取、原始字节保存、长度不匹配、文件校验、后台启动、
  停止续采、锁冲突、记录恢复、符号链接拒绝、打包以及命令帮助。
- CI 配置验证 Python 3.7、3.10、3.13，以及发布包解压后的测试；具体结果查看仓库 Actions。
- 自动化测试不能代替真实平台、驱动、长时间采集、systemd 安装或重启测试。
  本版本不承诺所有 Intel CPU 都支持 PMT，也不承诺任意 decoder 都兼容。
- `verify` 检查格式、原始数据长度、区域基线、序列和计划份数，不是防篡改签名。
  不要把来源不明或被外部修改的任务目录当成可信输入。

维护者执行：

```bash
python3 -m unittest discover -s tests -v
./build-package.sh
```

发布包和 SHA-256 文件生成在 `dist/`。只从白名单发布包构建仓库，
不要上传整个开发目录。详细发布步骤见 [PUBLISHING.md](PUBLISHING.md)。
当前仅用于获准的同事协作；未选择开源许可证，仓库访问权限不等于对外再分发授权。