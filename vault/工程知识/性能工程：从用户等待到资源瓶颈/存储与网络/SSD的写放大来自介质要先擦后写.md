---
title: SSD的写放大来自介质要先擦后写
type: concept
status: active
updated: 2026-09-25
confidence: high
change_rate: low
review_after: 2029-03-21
tags:
  - "hardware"
  - "performance/storage"
  - "systems/memory"
  - "data/storage"
sources:
  - "https://flashdba.com/2014/04/16/understanding-selfish-page-modes/"
  - "https://www.usenix.org/legacy/event/fast08/tech/full_papers/lee/lee.pdf"
  - "https://en.wikipedia.org/wiki/Write_amplification"
editorial_pass: 1
editorial_at: 2026-09-25
editorial_by: agent-A
editorial_note: "1处命中为擦除块对齐硬件术语误报保留；图0.80达标不动"
---

# SSD的写放大来自介质要先擦后写

存储引擎的写放大是软件层的问题（见 [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/读写三放大是存储引擎的中央权衡|读写三放大是存储引擎的中央权衡]]），但 SSD 自己在介质层还叠了一层写放大，来源是闪存"必须先擦除才能改写"的物理约束。要解决的问题：同一份用户数据在 SSD 上实际产生的物理写入量可能是逻辑写入的几倍，容量规划和寿命估算都必须按物理写入算，只按逻辑写入算会双双失准。

## 机制：为什么必须先擦后写

NAND 闪存单元的物理限制：写操作只能把位从 1 改成 0（充电），要改回 1 必须对整个擦除块（erase block，通常数 MB）执行高电压擦除。擦除有次数限制（SLC 约 10 万次、QLC 约 1000 次），且擦除块必须整体操作。FTL（Flash Translation Layer，闪存转换层）因此不能原地更新：一次 4KB 逻辑写要读出所在擦除块的其它页、写进新的擦除块位置、更新映射表。写路径变成"读-改-写"，放大从这里开始。

![写入以 4KiB 页为单位、擦除以 256KiB 块为单位的不对称（Wikimedia Commons《NAND Flash Pages and Blocks》，作者 Dmitry Nosachev，CC BY-SA 4.0，https://commons.wikimedia.org/wiki/File:NAND_Flash_Pages_and_Blocks.svg）](https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/NAND_Flash_Pages_and_Blocks.svg/1280px-NAND_Flash_Pages_and_Blocks.svg.png)

图里两种粒度相差两个数量级：改一页的数据必须牵扯整块。上面那张图是「一次写入被摊成多次物理写」，这张图说清了它为什么必然发生——粒度不对称是擦除块的物理属性，FTL 只能在这个约束里调度。

| 来源 | 机制 | 典型量级 |
| --- | --- | --- |
| 擦除块对齐 | 页比擦除块小三个数量级，改一页牵动整块 | 随碎片化上升 |
| 垃圾回收 | 烘焙块里的有效页搬进新块才能腾出可擦块 | WA 1.5-3x |
| 磨损均衡 | 全盘均匀消耗擦写次数，冷数据也要搬 | 小负载下显著 |
| metadata/RAISE | FTL 映射表与纠删开销 | 恒定小幅 |
| OP 空间不足 | OP（Over-provisioning，预留空间）越小 GC 越频繁 | OP 28% → WA≈2 |
| SMR 叠瓦 | 磁记录的类似约束：磁道叠写必须整带重写 | 量级更大 |

表里的放大来源可以叠乘。收益是闪存的顺序写吞吐与随机读延迟；代价是物理写入量成倍、寿命消耗成倍、性能抖动（GC 停顿）。

![一次 4KiB 主机写入在盘上被摊成多次物理写（Wikimedia Commons《Write Amplification on SSD》，作者 Music Sorter，CC BY-SA 3.0，https://commons.wikimedia.org/wiki/File:Write_Amplification_on_SSD.svg）](https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Write_Amplification_on_SSD.svg/1280px-Write_Amplification_on_SSD.svg.png)

图上左边蓝色是主机发出的一次逻辑写，右边红色的每一块都是它在介质上真实消耗的物理写——倍数就是写放大。容量规划按左栏算、寿命估算按右栏算，两侧对不上账是 SSD 场景最常见的估算失准来源。

## 验证

验证的锚点：写放大倍数要与盘上计数对账——预写逻辑写入量乘放大系数应接近物理写入量，实测偏差超出预期就说明该盘的映射层行为与假设不同。

用公开工具实测自己手上的盘：
```bash
# 看物理写入累计与寿命消耗（SMART 属性 233/249 视厂商而异）
smartctl -a /dev/nvme0n1 | grep -E "Data Units|Percentage Used"
# 看逻辑写入并对比：WA = 物理写入量 / 逻辑写入量
nvme admin-passthru 系工具或厂商工具读 FTL 统计
```
跨来源对账：flashdba 的 SELFISH 研究论文（FAST'08）实测了各页模式与配置下的 WA 分布，可以拿它当对照基线——不同写入模式（随机小写 vs 顺序大写）的 WA 相差数倍，任何"SSD 写放大一般是 X"的单点断言都该被你自己的 SMART 数据推翻或证实。

## 边界

本篇讲介质层的放大机制与容量寿命估算方法。闪存介质层与存储引擎层的写放大如何叠乘、以及 LSM 的 compaction 与 FTL 的 GC 谁吸收谁，见 [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/LSM树用写放大换取顺序写和可扩展性|LSM树用写放大换取顺序写和可扩展性]]（软件层用顺序写摊薄介质层放大）。介质选型（TLC/QLC 的寿命与延迟权衡）见 [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/非关系数据库按访问模式选择数据模型|非关系数据库按访问模式选择数据模型]] 的选型视角。SMART 数据只能看物理写入累计，读不到 FTL 内部策略，厂商私有。GC 停顿造成的延迟毛刺观测方法见 [[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能剖析与火焰图|性能剖析与火焰图]]。HDD 侧的劣化信号与更换决策（SMART 属性的另一套读法）见 [[工程知识/缺陷分析：从个案到体系/硬件故障/磁盘坏道与静默损坏的检测修复路径|磁盘坏道与静默损坏的检测修复路径]]。

## 相关

- [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/读写三放大是存储引擎的中央权衡]]——软件层写放大总纲
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/InnoDB用日志连接事务、恢复与复制|InnoDB用日志连接事务、恢复与复制]]——日志先行的写路径在闪存上的表现

