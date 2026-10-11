---
title: SSD的写放大来自介质要先擦后写
type: concept
status: active
updated: 2026-10-02
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
  - "https://zh.wikipedia.org/wiki/%E5%86%99%E5%85%A5%E6%94%BE%E5%A4%A7"
  - "https://semiconductor-nerds.com/write-amplification-where-2-writes-2-writes-is-not-equal-to-4-writes/"
---

# SSD的写放大来自介质要先擦后写

同一份数据在 SSD（固态硬盘）上实际写入量可能是逻辑写入的几倍，因为**闪存必须先擦除才能改写**。要解决的问题是：只按逻辑写入算，容量规划和寿命估算会双双失准。读完这篇你能按物理写入量做容量规划与寿命估算，两本账各归各位。

存储引擎的写放大是软件层的问题[[工程知识/数据系统：在并发与故障中保存事实/事务与存储/读写三放大是存储引擎的中央权衡|读写三放大是存储引擎的中央权衡]]，但 SSD 自己在介质层还叠了一层写放大，来源是闪存"必须先擦除才能改写"的物理约束。

## 它是怎么做到的：为什么必须先擦后写

NAND（一种闪存，用浮栅晶体管存储电荷）闪存单元的物理限制：写操作只能把位从 1 改成 0（向浮栅注入电荷），要改回 1 必须对整个擦除块（erase block，通常数 MB）执行高电压擦除。因为一次写入可能只改一个页而擦除以块为单位，FTL（Flash Translation Layer，闪存转换层）不能在原位置更新：一次 4KB 逻辑写要读出所在擦除块的其它页、写进新的擦除块位置、更新映射表。

写路径变成**"读-改-写"**，放大从这里开始。擦除次数本身有限：**SLC（Single-Level Cell，单比特单元）约 10 万次**，QLC（Quad-Level Cell，四比特单元，每单元存的比特越多寿命越短）约 1000 次，这个上限就是盘寿命估算的基准。

![写入以 4KiB 页为单位、擦除以 256KiB 块为单位的不对称（Wikimedia Commons《NAND Flash Pages and Blocks》，作者 Dmitry Nosachev，CC BY-SA 4.0，https://commons.wikimedia.org/wiki/File:NAND_Flash_Pages_and_Blocks.svg）](/static/figures/1280px-nand-flash-pages-and-blocks-svg.png)

*图示：NAND 闪存的页与块结构，擦除以块为单位。图源：Wikimedia Commons《NAND Flash Pages and Blocks.svg》，作者 Dmitry Nosachev，CC BY-SA 4.0，https://commons.wikimedia.org/wiki/File:NAND_Flash_Pages_and_Blocks.svg。*
图里两种粒度相差两个数量级：**改一页的数据必须牵扯整块**。上面那张图是「一次写入被摊成多次物理写」，这张图说清了它为什么必然发生——粒度不对称是擦除块的物理属性，FTL只能在这个约束里调度。

粒度不对称的完整层级，Semiconductor Nerds 的工程博客图更直观——NAND Die → Plane → Block → Page 四级嵌套，写与擦各自锁定在哪一级一目了然：

![NAND 闪存层级结构图：Die → Plane → Block → Page 四级嵌套，写以页为单位、擦以块为单位](/static/figures/semiconductor-nerds-blocks.png)

图源：[Semiconductor Nerds《Write Amplification Explained》](https://semiconductor-nerds.com/write-amplification-where-2-writes-2-writes-is-not-equal-to-4-writes/)。写落在最细的 Page 级、擦锁死在 Block 级——正是上一张「页比块小三个数量级」的结构化呈现。

| 来源 | 机制 | 典型量级 |
| --- | --- | --- |
| 擦除块对齐 | 页比擦除块小三个数量级，改一页牵动整块 | 随碎片化上升 |
| 垃圾回收 | 烘焙块里的有效页搬进新块才能腾出可擦块 | 写放大（Write Amplification，下文称 WA）1.5-3x |
| 磨损均衡（把擦写均匀分散到全盘各块以拉平寿命消耗） | 全盘均匀消耗擦写次数，冷数据也要搬 | 小负载下显著 |
| metadata/RAISE（Redundant Array of Independent Silicon Elements，用冗余硅片抵消坏块） | FTL 映射表与纠删开销 | 恒定小幅 |
| OP 空间不足 | OP（Over-provisioning，预留空间）越小 GC（Garbage Collection，垃圾回收：把闪存中已失效页占用的空间整理出来以便整块擦除）越频繁 | OP 28% → WA≈2 |
| SMR（Shingled Magnetic Recording，叠瓦式磁记录：磁道像瓦片一样重叠，改写须整条重写）叠瓦 | 磁记录的类似约束：磁道叠写必须整带重写 | 量级更大 |

表里的放大来源可以叠乘，使物理写入量成倍、寿命消耗成倍、性能抖动（GC 停顿）。闪存介质本身顺序写吞吐高、随机读延迟低，这是使用闪存的理由；写放大是同一介质带来的代价，两者并存。

表里「垃圾回收」那一行的搬运过程，Semiconductor Nerds 另一张图给了逐步演示——挑一个含大量无效页的块做牺牲块，把仍然有效的页抄进新块，再把牺牲块整体擦除：

![垃圾回收示意：牺牲块中的有效页被搬运进新块，整块擦除后归还为空闲块](/static/figures/semiconductor-nerds-gc.png)

图源：[Semiconductor Nerds《Write Amplification Explained》](https://semiconductor-nerds.com/write-amplification-where-2-writes-2-writes-is-not-equal-to-4-writes/)。「搬运有效页」就是下文鱼鳞册比喻里「照抄仍然有效的地块」的工程实物——**搬运本身就是额外写入，写放大在 GC 里结构必然，而不是缺陷**。

![一次 4KiB 主机写入在盘上被摊成多次物理写（Wikimedia Commons《Write Amplification on SSD》，作者 Music Sorter，CC BY-SA 3.0，https://commons.wikimedia.org/wiki/File:Write_Amplification_on_SSD.svg）](/static/figures/1280px-write-amplification-on-ssd-svg.png)

*图示：SSD 写放大：一次逻辑写引发的多次物理写。图源：Wikimedia Commons《Write Amplification on SSD.svg》，作者 Music Sorter at English Wikipedia，CC BY-SA 3.0，https://commons.wikimedia.org/wiki/File:Write_Amplification_on_SSD.svg。*
图上左边蓝色是主机发出的一次逻辑写，右边红色的每一块都是它在介质上真实消耗的物理写——倍数就是**写放大**。容量规划按左栏算、寿命估算按右栏算，两侧对不上账是 SSD 场景最常见的估算失准来源。

「改动一格要重绘（外观变化但布局不变、重新描画像素）一册」的实物原型是明代的鱼鳞册：鱼鳞册按地块逐块绘图造册，一块田的业主变了，不在旧图上涂改（介质不许原地改），等攒够一批变更后整册重绘、旧册封存——重绘时还要把旧册里仍然有效的地块全部照抄进新册（垃圾回收搬运有效页），抄写的功夫就是写放大：

![明代的鱼鳞册：地块变更攒批后整册重绘，有效地块照抄进新册](/static/figures/fishscale-register.jpg)

*图源：Wikimedia Commons，作者猫猫的日记本，CC BY-SA 3.0，https://commons.wikimedia.org/wiki/File:Fish-Scale_Inventory_of_the_Ming_Dynasty_2012-06.JPG。*

FTL 的 GC 与鱼鳞册重绘同构：擦除块是"一册"，有效页是"仍有效的地块"，搬运写是新册的照抄，**OP 预留空间是留白页——留白越少，重绘越频繁**；每册重绘次数有限（擦写寿命），攒批（把多个小操作攒成一批一次处理）的节奏（写入模式）直接决定这套账本能用多少年。

## 怎么自己动手验证

**写放大倍数要与盘上计数对账**——预写逻辑写入量乘放大系数应接近物理写入量，实测偏差超出预期就说明该盘的映射层行为与假设不同。

下面两条命令用公开工具实测自己手上的盘，一条看物理写入累计，一条看逻辑写入对比：
```bash
# 看物理写入累计与寿命消耗（SMART属性 233/249 视厂商而异；SMART 是固态盘与机械盘自带的运行状态及寿命计数标准）
smartctl -a /dev/nvme0n1 | grep -E "Data Units|Percentage Used"
# 看逻辑写入并对比：WA = 物理写入量 / 逻辑写入量
用 nvme-cli 的 admin-passthru 子命令或厂商提供的管理工具读取 FTL 内部统计计数器
```
跨来源对账：存储工程博客 flashdba.com 的作者提出的 SELFISH（Selfish Page Modes：按页模式分类测量写放大的分析方法，出自 FAST'08 论文）实测了各页模式与配置下的 WA 分布，可以拿它当对照基线（正常状态下的指标水平、用来对比异常）——不同写入模式（随机小写 vs 顺序大写）的 WA 相差数倍，任何"SSD 写放大一般是 X"的单点断言，都该被你自己的 SMART（硬盘自检数据：盘自己上报的健康指标）数据检验一遍。

## 这套说法在哪儿会失效

本篇讲介质层的放大机制与容量寿命估算方法。闪存介质层与存储引擎层的写放大如何叠乘、以及 LSM（Log-Structured Merge，先把写入追加成日志再后台合并成有序文件的存储结构）的 compaction 与 FTL 的 GC 谁吸收谁，见 [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/LSM树用写放大换取顺序写和可扩展性|LSM树用写放大换取顺序写和可扩展性]]（软件层用顺序写摊薄介质层放大）。

介质选型（TLC/QLC 的寿命与延迟权衡）见 [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/非关系数据库按访问模式选择数据模型|非关系数据库按访问模式选择数据模型]] 的选型视角。SMART 数据只能看物理写入累计，读不到 FTL 内部策略，厂商私有。

GC 停顿造成的延迟毛刺（延迟曲线上偶发的短时尖峰）观测方法见 [[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能剖析与火焰图|性能剖析与火焰图]]。HDD（机械硬盘）侧的劣化信号与更换决策（SMART 属性的另一套读法）见 [[工程知识/缺陷分析：从个案到体系/硬件故障/磁盘坏道与静默损坏的检测修复路径|磁盘坏道与静默损坏的检测修复路径]]。

## 接着读哪几篇：软件层写放大总纲

- [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/读写三放大是存储引擎的中央权衡]]——软件层写放大总纲
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/InnoDB用日志连接事务、恢复与复制|InnoDB用日志连接事务、恢复与复制]]——日志先行的写路径在闪存上的表现
