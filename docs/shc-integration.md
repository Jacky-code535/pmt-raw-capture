# SHC 集成预留

0.6.0 不包含 SHC runtime、SHC log parser 或自动故障分析。当前工具与 SHC 之间只保留稳定的数据边界，确保以后接入时不修改 raw v1 格式。

现有 `analyze --events <csv>` 接受通用事件字段：

```text
start,end,phase,test_item,status,failure_time
```

未来 SHC adapter 的职责仅是把已确认的 SHC 数据转换为该通用事件格式，并记录 adapter 版本和输入哈希。PMT 核心流程继续负责：

```text
raw -> XML decode -> series -> summary -> event alignment
```

预留但当前不实现：

- SHC phase 和 test item 自动解析；
- SHC 状态与 failure time 提取；
- 时钟偏移校准；
- SHC-PMT 故障归因；
- SHC 安装、启动或服务依赖。

没有 SHC 输入时，采集、打包、解码和统计行为完全不变。