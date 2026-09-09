# PMT Raw Capture

Linux Intel PMT 原始数据采集工具，支持定时采样、后台运行、停止续采和结果打包。运行依赖 Python 3.7+，无需安装 pip 包。

## 下载

**[下载工具包 v0.4.3](https://github.com/Jacky-code535/pmt-raw-capture/releases/download/v0.4.3/pmt-raw-capture-0.4.3.tar.gz)**

下载后将压缩包放到被测主机。历史版本见 [Releases](https://github.com/Jacky-code535/pmt-raw-capture/releases)。私人仓库的下载链接需要登录有访问权限的 GitHub 账号。

## 开始采集

被测主机需运行 Linux，并提供 `/sys/class/intel_pmt/telem*` 设备节点。

解压并查看 PMT 设备：

```bash
tar -xzf pmt-raw-capture-0.4.3.tar.gz
cd pmt-raw-capture-0.4.3
sudo ./pmt-capture inventory
```

每隔 10 秒采集一份，共三份。将 `lab-host` 替换为机器标签：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id trial-001 \
  --interval 10 --samples 3
```

第一份立即采集，约 20 秒完成。数据保存在 `results/trial-001/`。

检查并打包结果：

```bash
sudo ./pmt-capture pack --run-dir ./results/trial-001 --output ./output
```

生成的 **`output/pmt-capture-trial-001.tar.gz`** 即为本次实验的结果包。

## 后台采集

每分钟一份，共 600 份，约 10 小时：

```bash
sudo ./pmt-capture start --endpoint lab-host --run-id experiment-001 \
  --interval 60 --samples 600 --background
sudo ./pmt-capture status --run-dir ./results/experiment-001
```

停止与续采：

```bash
sudo ./pmt-capture stop --run-dir ./results/experiment-001
sudo ./pmt-capture resume --run-dir ./results/experiment-001 --background
```

`stop` 后用 `status` 确认 `busy: False` 再续采或打包。续采沿用原计划，保留已采数据；主机重启后需手动续采。

## 文档

| 文档 | 内容 |
| --- | --- |
| [使用指南](docs/usage.md) | 参数、任务状态、结果文件与排障 |
| [数据格式](docs/data-format.md) | 快照字段与解码接口 |
| [服务部署](docs/service.md) | systemd 安装、开机启动和菜单操作 |
| [开发说明](docs/development.md) | 测试、构建与发布 |
| [更新记录](docs/changelog.md) | 各版本变更 |

## 仓库结构

```text
pmt-capture     命令行入口
src/            Python 采集与任务管理实现
docs/           使用与开发文档
service/        可选的 systemd 部署及菜单
scripts/        工具包构建脚本
tests/          自动化测试
```

命令帮助：`./pmt-capture --help`。采集结果在本地保存，分析端使用对应平台的 XML 和解码器处理。