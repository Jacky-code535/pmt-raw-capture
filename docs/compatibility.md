# GNR 兼容性

## 0.6.1 支持声明

0.6.1 的 collector 可发现 Linux Intel PMT sysfs 暴露的区域，但“可发现”不等于“已验证解码”。正式资格范围是 AVC01 GNR 主机上观察并通过真实采集、精确 XML 匹配和内置解码的以下七组 schema。

平台数据版本：`df82b1741dec619300707881114f6b17b5204f60`

| GUID | Size（bytes） | GNR schema | 状态 |
| --- | ---: | --- | --- |
| `0x22473996` | 14496 | OOBMSM CORE rev3 | Qualified |
| `0x22491753` | 6272 | PUNIT IODIE | Qualified |
| `0x22806802` | 6784 | PUNIT CDIE | Qualified |
| `0x3d4bb40a` | 48 | OOBMSM TOPO-ROOT | Qualified |
| `0x3d4bb41a` | 24 | OOBMSM TOPO-LEAF | Qualified |
| `0x477e9373` | 6160 | OOBMSM RMID rev0 | Qualified |
| `0x6e94ffa0` | 176 | OOBMSM QAT | Qualified |

资格结果：30/30 complete snapshots、每份 36/36 PMT regions、1,080 raw records、962,940 decoded rows，所有 series rows 在该次策略下有效。完整记录见[硬件资格](qualification.md)。

## 在其他 GNR 主机上使用

先运行：

```bash
sudo ./pmt-capture inventory
```

完成三次短采集后运行：

```bash
./pmt-capture validate-platform --run-dir results/<run-id>
```

结果解释：

- `mapping_valid: true`：本次所有 GUID + Size 均精确匹配文件；
- `valid: true`：匹配 schema 也能由内置 decoder 加载；
- 任一为 false：当前主机不在已验证路径中，先保存报告，不要替换为相近 GUID 的 XML；
- 两者均为 true 只证明 schema 可用，新增 inventory 仍应通过真实 payload 分析后才能加入 Qualified 列表。

## 当前边界

- 只对表中 GNR schema 作正式硬件资格声明；
- bundled registry 中其他 mapping 是可选输入，不自动获得支持状态；
- 物理 topology 不从 `telemN` 推断，需要显式 CSV；
- counter、invalid marker 和空间聚合规则需要平台确认后显式配置；
- SRF、OOB 和 SHC 不属于 0.6.1 运行范围。