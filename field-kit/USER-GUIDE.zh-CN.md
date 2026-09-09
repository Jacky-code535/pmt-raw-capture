# 可选 systemd 菜单

版本 0.4.2。普通采集使用 [README 中的命令](../README.md)。只有希望在专用实验机安装
后台服务并开机续采时，才使用这个菜单。

开机续采要求启动时 PMT sysfs 已可用；服务使用 `Restart=no`，不保证异常后自动恢复。
普通 CLI 和服务任务不要同时操作同一个结果目录。首次使用先完成三份试采，
再在获准的实验机验证停止、启动和重启行为。

```bash
sudo ./run.sh
```

需要 Linux、Python 3.7+、正在运行的 systemd、PMT sysfs 和 root 权限。
菜单预检查要求 `/var/lib` 至少 500 MB；采集程序另按计划估算空间。

1. 选择开始任务，填写机器标识，选择三份试跑或明确的自定义计划。
2. 查看状态。首次整分钟对齐可能等待最多一分钟；刚启动还没有 run.json 时稍后再查看。
3. 暂停使用菜单的暂停项；继续使用继续项，保留已保存的份数和原计划。
4. 任务完成或暂停后打包。未完成/校验失败时需明确同意导出 partial 诊断包。
5. 卸载需要确认，停止已安装服务，保留数据。

菜单控制 `/etc/pmt-system-debug/active-instance` 所指的当前安装实例。
多实例操作请用明确的 systemctl 单元名和 CLI `--run-dir`，不要依赖菜单猜测。
开始新任务不会继承旧任务的 interval/samples；正在运行的服务必须先暂停才能安装新任务。

也可以提供本次计划的环境变量，菜单仍会要求确认：

```bash
sudo env PMT_ENDPOINT=lab-host PMT_INTERVAL_SECONDS=10 PMT_SAMPLES=3 ./run.sh
```

`PMT_TOTAL_HOURS` 可代替份数，按间隔向上取整；不要同时设置冲突的计划。
默认 60 秒、600 份约 10 小时，第一份后首尾跨度实际约 599 分钟。

结果在 `/var/lib/pmt-system-debug/results/<run-id>`。包内菜单导出到包目录的 `output/`；
从 `/opt/pmt-system-debug` 运行菜单时导出到 `/var/lib/pmt-system-debug/exports`。
同名归档不会覆盖，需要重复导出时使用 CLI 指定另一个输出目录。

`COLLECTION STATUS` 是次数/程序状态，`VERIFICATION STATUS` 是独立文件校验状态。
两者均不是硬件健康结论。

## 脚本用途

以下脚本由 `run.sh` 菜单调用，均操作当前安装的服务任务，不操作 README 中的独立 CLI 任务。

| 脚本 | 用途 |
| --- | --- |
| `start-capture.sh` | 检查环境、选择采集计划并安装启动服务，或选择继续未完成任务 |
| `show-progress.sh` | 显示当前安装任务的进度、服务状态和检查状态 |
| `pause-capture.sh` | 停止当前采集服务，保留数据 |
| `resume-capture.sh` | 启动当前服务，按已保存的计划续采 |
| `pack-results.sh` | 检查并打包当前任务，可确认导出不完整诊断包 |
| `lib/` | 上述脚本使用的配置、计划和状态处理实现，不需要手动运行 |

需要直接安装服务时：

```bash
sudo ./install.sh --endpoint lab-host --instance lab-host \
	--run-id service-trial-001 --interval 10 --samples 3
sudo systemctl status pmt-bulk-capture@lab-host.service
```

直接管理该服务使用 `systemctl stop` / `systemctl start`，单元名均为
`pmt-bulk-capture@lab-host.service`。`install.sh --no-start` 只安装，不启动或启用开机启动。
卸载用 `sudo ./uninstall.sh`，确认后停止所有已安装的 PMT 服务并保留数据。