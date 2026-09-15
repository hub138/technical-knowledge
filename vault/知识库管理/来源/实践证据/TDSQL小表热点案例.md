---
title: TDSQL 小表热点问题的分析与优化实践
type: case-study
status: source-only
updated: 2026-08-31
review_after: 2027-08-31
change_rate: stable
confidence: medium
tags:
  - source/case-study
  - performance/profiling
  - database/contention
derived:
  - "[[工程知识/计算机系统与性能/观测与诊断/性能问题定位]]"
---

# TDSQL 小表热点问题的分析与优化实践

> [!warning] 证据边界
> 本页是 2025 年特定 TDSQL/MySQL 版本、表结构和负载下的内部案例。可复用的是 `profile -> 源码假设 -> uprobe -> page 元数据 -> 反证实验 -> 基准对照` 的定位方法；具体热点函数、并发拐点、字段/索引方案和性能数字不能直接推广。提炼后的方法见 [[工程知识/计算机系统与性能/观测与诊断/性能问题定位]]。

原始文章：[TDSQL 小表热点问题的分析与优化实践](https://km.woa.com/group/cloudlei/articles/show/601432)

丨 导语 结合 profiling & tracing 技术，分析与优化 TDSQL 小表热点问题的实践，供读者参考。

## 问题背景

TDSQL 某金融客户有一张账号表，在高并发查询业务场景中性能不及预期，初步判断是小表热点问题，即表数据量很小，但因多个线程竞争同一个 page（如高频读写某一行或某几行数据）导致性能瓶颈。

## 定位热点 page

我们首先使用雨滴平台的 CPU Profiling 功能，分析压测时 TDSQL 热点函数及火焰图，结果链接为：[Drop - 一站式性能优化平台](https://drop.qcloud.com/task/result?taskID=9037f5cc-bfca-4957-a5b7-af92625a43a2&taskExpiredTime=2064473763&sharedTaskToken=%3CREDACTED%3E&isSharedURL=true)

查看分析结果中的热点函数，如下图所示，Top3 热点函数分别为 native_queued_spin_lock_slowpath、finish_task_switch、__schedule，系统可能存在严重的调度开销/锁竞争问题。

![img](https://km.woa.com/asset/000100022506004b64d438c8e14e1d02?height=914&width=2532&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

进一步查看火焰图，可以看出调度开销/锁竞争主要是由 TDSQL 内核函数 buf_page_optimistic_get 触发，该函数的作用是尝试以乐观的方式获取 buffer pool 中的某个页面（page），其采样占比达到 72.94%，说明在高并发访问同一个 page，形成小表热点现象，导致性能不及预期。

![img](https://km.woa.com/asset/0001000225060021e21169a5fa4a9202?height=1276&width=2470&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

热点函数 buf_page_optimistic_get 占比显著，判断已经出现了性能拐点。接下来，我们通过 调整 threadpool 相关参数（size、oversubscribe），粗略计算该小表的性能拐点。

### 活跃线程数对比

针对该银行的业务小表，当活跃线程数为 32 时压测 QPS 可以达到 1.1w，超过之后便开始出现性能拐点。热点函数 buf_page_optimistic_get 占比非常显著，高并发下容易命中相同的页面（page），活跃线程数越多拿 page 锁的竞争也就越激烈，尤其是 threadpool 参数 size 取值超过 32 的情况。

![img](https://km.woa.com/asset/000100022506004e812874dbcb4d7b02?height=268&width=1226&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

## 热点 page 优化

既然增大并发时查询该小表容易命中同一个 page，那是否可以通过添加字段将访问打散在更多 page 呢？容易想到的办法是增加一些 dummy 字段（无业务含义）。

### 添加字段无效？

接下来尝试修改表结构，添加 32 个 dummy 字段，每个字段默认 255 个字符 'a'，确保单个 page 放不下所有业务账号记录。经压测对比，QPS、热点函数均无变化。说明竞争的还是同一个 page？为什么新增 dummy 字段无效？具体原因放在后面解释。



前面我们推断性能瓶颈在于高并发访问同一个 page，但只是推断，缺少具体数据支撑，比如具体是哪一个 page？page 的类别和数据量是什么情况？接下来我们尝试通过 tracing 手段（uprobes） 做进一步的细粒度分析。

### uprobe 统计热点 page

TDSQL 函数 buf_page_optimistic_get 的声明如下，位于头文件 storage/innobase/include/buf0buf.h：

![img](https://km.woa.com/asset/000100022506006704511a85fe478b02?height=152&width=1496&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

其中，第 2 个参数 block 类型为 struct buf_block_t，首字段 page 表示一个 buffer page，class page_id_t 的前 2 个字段 m_space、m_page_no 唯一标识一个 buffer page，即二元组（space， page_number），且这 2 个字段均为 4 个字节（uint32_t），具体定义摘录如下：

```cpp
struct buf_block_t {
  buf_page_t page;
  ...
};

class buf_page_t {
  page_id_t id;
  ...
};

class page_id_t {
  space_id_t m_space;
  page_no_t m_page_no;
  ...
};

typedef uint32_t space_id_t;
using page_no_t = uint32_t;
```



执行 [uprobe 工具](https://github.com/brendangregg/perf-tools/blob/master/user/uprobe)，记录每次调用 buf_page_optimistic_get 所访问 page 对应的唯一标识 (space、 page_number)：



```basic
./uprobe 'p:<MYSQLD_BINARY>:_Z23buf_page_optimistic_getmP11buf_block_tm10Page_fetchPKcmP5mtr_t space=+0(%si):s32 page_number=+4(%si):s32'
```

`<MYSQLD_BINARY>` 代指当时带可解析符号的目标二进制；符号名、参数寄存器和结构偏移都依赖具体构建与 ABI，重新使用前必须用当前二进制的调试信息验证，不能直接复制本命令。

%si：表示 buf_page_optimistic_get 第二个参数 block

+0(%si):s32：获取 Space 编号

+4(%si):s32：获取 Page 编号

经统计，压测过程中（3276, 320) 这个 page 最热，超过 99% 访问的都是该 page，另一个 page（3268, 34) 访问比较零星可忽略，如下图所示：

![img](https://km.woa.com/asset/00010002250600d3dbd52fc65648c402?height=1812&width=2970&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

uprobes 参考链接：[Uprobe-tracer: Uprobe-based Event Tracing](https://docs.kernel.org/trace/uprobetracer.html)

我们通过 uprobe 工具可以精准定位出热点 page 的唯一标识，有没有办法基于这个标识进一步获取 page 的详细信息呢？自然是有的。

### 查询指定 page 具体信息

执行以下 SQL 语句，使用唯一标识（3276, 320），从 TDSQL 系统表 information_schema.INNODB_BUFFER_PAGE 查询该热点 page 的具体信息：



```sql
SELECT * FROM information_schema.INNODB_BUFFER_PAGE where SPACE=3276 and PAGE_NUMBER=320;
```

 结果如下图所示：

![img](https://km.woa.com/asset/00010002250600aa578a71a439494602?height=1334&width=3446&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

对于该热点 page：

● PAGE_TYPE 为 INDEX， 参照下面的表格，该 page 存放的是 B-tree node；

● number_records、data_size 分别为 229、8015，存放 229 条记录，总大小 8015 字节，只需一个 page 即可放下；

● 表名是 hotspot_super_acct_prebal，即仿真环境中的业务小表。



PAGE_TYPE 枚举值表格：

![img](https://km.woa.com/asset/000100022506002efc67e6c059424702?height=1936&width=1338&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

系统表 information_schema.INNODB_BUFFER_PAGE 参考链接：[ https://dev.mysql.com/doc/refman/8.4/en/information-schema-innodb-buffer-page-table.html](https://dev.mysql.com/doc/refman/8.4/en/information-schema-innodb-buffer-page-table.html)

### 添加字段无效原因

修改表结构，添加字段前后基本上访问的还是同一个 page，不过这个 page 的类型是 INDEX，总大小不到 10K（单个 page 16 K），包括记录数均为 229，里面存的是 B+ 树索引的非叶子节点。因此，添加字段不起作用，最热的 page 还是索引页。

### 添加索引提升性能

由上述分析可知最热的 page 是索引页，添加字段无效，那么在这些新增字段上加索引呢？经测试，新增16 个字段（1w 条数据）、索引新增 2*255*4 字节(限制总长度为 3072 个字节)，QPS 提升至 1.2w（+26%），热点函数 buf_page_optimistic_get 在火焰图上消失。

![img](https://km.woa.com/asset/0001000225060074820c6b619d4d7902?height=990&width=2458&imageMogr2/thumbnail/1540x%3E/ignore-error/1)

## 原文总结

针对 TDSQL 小表热点问题，我们先使用雨滴 CPU Profiling 快速定位热点 page 问题（热点函数 buf_page_optimistic_get），然后通过 tracing 手段（uprobes），统计出热点 page 的类别是 INDEX，解释了添加 dummy 字段无效的原因，进一步指导添加索引达到性能提升的效果。因此，对于业务表，不是表越小越好，当存在性能瓶颈时可考虑添加 dummy 字段及索引来缓解。

更新于：2025-06-10 14:44

标签： [profiling ](https://km.woa.com/group/38034/articles?tag_id=23015)[Tracing ](https://km.woa.com/group/38034/articles?tag_id=23177)[tdsql ](https://km.woa.com/group/38034/articles?tag_id=90274)[性能问题定位与分析 ](https://km.woa.com/group/38034/articles?tag_id=93343)[ftrace](https://km.woa.com/group/38034/articles?tag_id=127227)

相关阅读(1)

[TDSQL 性能抖动探因：基于 tracing & profiling 工具快速定位与修复](https://km.woa.com/articles/show/612329)





## 如何定位是非叶子节点

在文章中，作者通过 **间接推断** 的方式判断热点Page（3276, 320）是B+树的**非叶子节点**，而非叶子节点。以下是具体的逻辑链条和判断依据：

---

### **1. 关键线索：`PAGE_TYPE = 'INDEX'`**
- 通过查询 `information_schema.INNODB_BUFFER_PAGE`，确认热点Page的类型是`INDEX`，即属于B+树索引的一部分。
- 但`INDEX`类型无法直接区分叶子/非叶子节点，需结合其他信息。

---

### **2. 核心推断逻辑**
#### **(1) 数据量和Page大小的矛盾**
- **字段值**：
  - `NUMBER_RECORDS=229`（**存储229条记录**）
  - **DATA_SIZE=8015字节（约7.8KB）**
  - 单个InnoDB Page大小为16KB。
- **矛盾点**：
  - 如果是**叶子节点**：  
    叶子节点存储的是实际数据（或主键+二级索引指针）。对于金融账号表，单条记录通常较大（例如包含多个字段），229条记录很难全部压缩到7.8KB内（除非字段极少或数据极短）。
  - 如果是**非叶子节点**：  
    非叶子节点仅存储键值（如主键）和子节点指针，每条记录很小（例如4字节主键 + 6字节指针），229条记录仅需约 `229 * (4+6) ≈ 2.3KB`，与`DATA_SIZE=8015`字节更吻合（剩余空间可能用于其他元数据或填充）。

#### **(2) 添加字段无效的实验**
- **操作**：添加32个255字符的**dummy字段**（约8KB/条），**试图分散数据到多个Page。**  
- **结果**：热点Page的访问未变化（仍是同一个Page）。  
- **推论**：  
  如果热点Page是叶子节点，添加字段后数据量激增，应触发Page分裂（新数据分散到其他Page）。但实际未分裂，说明该Page存储的是**索引结构**（非叶子节点），而非表数据。

#### **(3) 添加索引有效的实验**
- **操作**：在新字段上添加索引。  
- **结果**：QPS提升26%，热点消失。  
- **推论**：  
  新索引生成独立的B+树，将查询压力分散到新索引的非叶子节点，缓解了原索引根节点的竞争。这进一步验证原热点Page是**原索引的非叶子节点**。

---

### **3. 为什么不是叶子节点？**
- **叶子节点的特征**：  
  - 存储实际数据，记录数通常远少于非叶子节点（因为单条数据更大）。  
  - 若热点Page是叶子节点，添加字段后数据膨胀会强制Page分裂，导致访问分散到新Page（但实际未发生）。

- **非叶子节点的特征**：  
  - 存储键值和指针，记录数多但体积小，对表结构变化不敏感。  
  - 根节点或高层非叶子节点会被所有查询路径访问，天然容易成为热点。

---

### **4. 总结：文章的判断依据**
1. **`PAGE_TYPE='INDEX'`**：确认是B+树的一部分。
2. **`NUMBER_RECORDS`和`DATA_SIZE`**：229条记录仅占7.8KB，符合非叶子节点的存储特征（键值+指针）。
3. **添加字段无效**：说明Page内容与表数据无关，而是索引结构。
4. **添加索引有效**：新索引分散了原索引非叶子节点的压力。

通过这些证据链，作者**排除叶子节点的可能性**，确定热点Page是B+树的**非叶子节点**（如根节点或中间节点）。
