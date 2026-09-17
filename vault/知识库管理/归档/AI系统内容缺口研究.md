---
title: AI 系统内容缺口研究
type: research
exclude_from_graph: true
status: verified
updated: 2026-09-03
review_after: 2026-10-03
change_rate: fast
confidence: high
tags:
  - research/gaps
  - ai/systems
  - ai/rag
  - ai/serving
  - ai/training
sources:
  - "https://arxiv.org/abs/1706.03762"
  - "https://arxiv.org/abs/2001.08361"
  - "https://arxiv.org/abs/2203.15556"
  - "https://github.com/NVIDIA/Megatron-LM"
  - "https://pytorch.org/docs/stable/fsdp.html"
  - "https://github.com/microsoft/DeepSpeed"
  - "https://arxiv.org/abs/2005.11401"
  - "https://arxiv.org/abs/2004.12832"
  - "https://arxiv.org/abs/2212.10496"
  - "https://arxiv.org/abs/2310.11511"
  - "https://arxiv.org/abs/2401.15884"
  - "https://arxiv.org/abs/2401.18059"
  - "https://github.com/microsoft/graphrag"
  - "https://arxiv.org/abs/2210.03629"
  - "https://modelcontextprotocol.io/specification/2026-07-28"
  - "https://a2a-protocol.org/v1.0.0/specification/"
  - "https://arxiv.org/abs/2205.14135"
  - "https://arxiv.org/abs/2309.06180"
  - "https://arxiv.org/abs/2211.17192"
  - "https://arxiv.org/abs/2210.17323"
  - "https://arxiv.org/abs/2306.00978"
  - "https://arxiv.org/abs/2211.10438"
  - "https://developers.openai.com/api/docs/guides/tools"
  - "https://github.com/EleutherAI/lm-evaluation-harness"
  - "https://crfm.stanford.edu/helm/"
  - "https://www.nist.gov/itl/ai-risk-management-framework"
  - "https://genai.owasp.org/llm-top-10/"
---

# AI 系统内容缺口研究

> 研究基准日：**2026-09-03**。本文只采用原始论文、官方规范、官方文档和官方仓库作为事实来源。它不是“再做一张 AI 热门名词表”，而是检查现有知识库是否能够让工程师从原理走到生产系统，并给出应补的知识单元、边界和验证方法。

## 结论

当前 `工程知识/AI系统` 已经覆盖了几条重要的工程判断：模型与系统的职责边界、上下文与记忆、Agent 编排、RAG 的证据观、推理服务中的 prefill/decode、KV cache、工具协议、轨迹评测和事实证据。这些页面适合作为上层骨架。

但它仍然**不能作为完整的 AI 系统知识库**，原因不是少几个框架名称，而是缺少以下四种连接：

1. **基础到实现**：从 token、embedding、Transformer、训练目标和解码，连接到模型为什么有当前能力与限制；
2. **数据到质量**：从数据获取、清洗、标注、训练和微调，连接到评测指标、污染、偏差和回归；
3. **算法到后端**：从注意力、KV cache、量化、并行和网络拓扑，连接到 TTFT/ITL、吞吐、显存和成本；
4. **组件到系统**：从检索、工具、状态、权限、观测和恢复，连接到一个可重放、可审计、可上线的 AI 服务。

现有内容更像“架构原则精选”，而不是“从入门到生产的多层知识图”。下面的缺口按 `P0`（没有它无法形成基本判断）、`P1`（生产工程必需）、`P2`（专业方向或前沿）排列。

## 覆盖模型

AI 系统应至少有八个互相连接的层次。每层都要同时回答：**机制是什么、边界在哪里、怎样证明它有效**。

| 层次 | 当前覆盖 | 主要缺口 |
| --- | --- | --- |
| 模型基础 | 有训练/后训练/RAG 的分层概览 | tokenization、Transformer 细节、位置编码、注意力、MoE、解码、扩散和多模态 |
| 数据与训练 | 几乎没有独立专题 | 数据生命周期、目标函数、分布式训练、混合精度、checkpoint、复现和数据治理 |
| 后训练与适配 | 只有概念分层 | SFT、LoRA/QLoRA、RLHF/DPO、蒸馏、持续训练、灾难性遗忘和模型合并 |
| 知识与检索 | 有两篇原则性 RAG 页 | 解析、切块、索引、embedding、混合检索、重排、图/层次检索、多模态 RAG、权限和新鲜度实现 |
| Agent 应用 | 工具、状态、协议和边界较好 | 计划/反思、结构化输出、人工接管、浏览器/代码 Agent、多 Agent 通信和任务恢复实作 |
| 推理后端 | 有调度、KV 和服务容量 | GPU/互联基础、算子与内核、量化算法、推测解码、并行策略、批处理公平性和容量模型 |
| 质量与运营 | 有轨迹评测与可观测性 | 数据集设计、judge 校准、污染、红队、线上实验、漂移、成本质量曲线和发布门禁实作 |
| 安全与治理 | 有沙箱和事实边界 | 威胁模型、提示注入、工具投毒、数据外泄、供应链、隐私、内容溯源和责任分级 |

## 模型基础与架构（P0）

### 应补的知识单元

| 知识单元 | 核心机制 | 边界与常见误判 | 最小验证 |
| --- | --- | --- | --- |
| Tokenizer 与词表 | 文本先被编码为 token；词表、合并规则和特殊 token 决定序列长度、未知词处理和训练/推理成本 | token 数不是字符数；换 tokenizer 会改变上下文预算、embedding 和微调数据分布 | 对中英文、代码、数字、emoji 和长 URL 比较 token 数、可逆性和截断 |
| Embedding 与表示空间 | 将离散 token 或输入映射到向量，后续层通过相似性和变换形成上下文表示 | 向量近不等于事实相同；embedding 模型、归一化和领域分布决定检索表现 | 固定数据集测近邻、聚类、跨语言和 OOD 稳定性 |
| Transformer | 自注意力在 token 间建立内容相关的加权连接，前馈层、残差、归一化和位置机制共同构成层 | 注意力权重不能直接当作因果解释；二次复杂度、内存带宽和上下文长度仍是硬边界 | 用小模型逐层检查 shape、mask、梯度和长序列复杂度；原始架构见 [Attention Is All You Need](https://arxiv.org/abs/1706.03762) |
| 位置表示 | 绝对位置、相对位置、RoPE 等把顺序注入无递归架构 | 扩大 max context 不等于模型学会远距离关系；外推常产生质量退化 | 在不同长度、位置和插值方案上测困惑度、检索位置偏差和任务准确率 |
| 训练目标 | 自回归 next-token、掩码建模、对比学习等把不同数据目标转成损失 | 训练 loss 下降不等于事实性、指令遵循或工具可靠性提高 | 保存训练/验证曲线，并用独立任务集和污染检查验证迁移 |
| 解码与采样 | greedy、temperature、top-k、top-p、beam 和约束解码改变输出分布 | temperature 不是“智能度”；随机采样会放大长链路 Agent 的方差 | 固定 seed 与多 seed 比较 pass@k、重复率、格式错误率和尾延迟 |
| Scaling law 与数据/算力配比 | 模型、token 和计算量对损失存在可拟合的幂律关系；Chinchilla 说明模型规模与训练 token 应共同扩展 | 预训练 loss 的最优分配不直接等于下游任务、推理成本或数据质量最优 | 在自身数据与硬件上做小规模 scaling sweep；参考 [Scaling Laws](https://arxiv.org/abs/2001.08361) 与 [Chinchilla](https://arxiv.org/abs/2203.15556) |
| MoE 与稀疏激活 | 路由 token 到少量专家，增加总参数但只激活部分参数 | 激活参数少不等于通信少；负载不均、路由抖动和专家容量会成为瓶颈 | 记录 expert load、drop/token overflow、通信量、质量和尾延迟 |

### 需要形成的关系页

- `Token、上下文窗口与成本如何共同决定输入设计`；
- `Transformer 的注意力、位置编码与长上下文限制`；
- `自回归解码、采样参数与结构化输出`；
- `Dense、MoE 与多模态模型的容量/通信权衡`；
- `Scaling law 只告诉你怎么分配预算，不告诉你任务是否成功`。

## 数据、预训练与分布式训练（P0/P1）

这一层是当前目录最明显的空白。没有它，工程师只能“调用模型”，无法解释模型质量、训练失败、成本或 checkpoint 是否可信。

### 必须补齐

| 主题 | 要讲清楚的机制 | 必须守住的边界 | 验证点 |
| --- | --- | --- | --- |
| 数据生命周期 | 来源、许可证、采集、解析、去重、质量过滤、混合采样、切分、版本和删除 | 数据集不能把版权、个人信息和内部数据当作无条件训练材料 | lineage、许可证、去重率、PII 命中、数据版本可重建 |
| 数据质量与配比 | 领域覆盖、难度、重复、污染和 curriculum 影响梯度与下游能力 | 更多 token 不必然更好；合成数据会复制教师偏差 | source mix、dedup、污染和 held-out 任务回归 |
| 预训练循环 | forward/loss/backward/optimizer/scheduler、梯度累积和 checkpoint | 单步 loss 成功不代表全局收敛或可恢复 | loss、吞吐、梯度范数、NaN、恢复后 bitwise/统计一致性 |
| 数据并行与模型并行 | DP 复制数据，TP/PP 切分计算，CP/EP 处理长上下文或专家；通信与计算重叠 | 并行度不是越大越快；batch、网络拓扑和 micro-batch 改变效率 | scaling efficiency、通信占比、bubble、显存和收敛变化 |
| FSDP/ZeRO | 分片参数、梯度和优化器状态，按需 all-gather/reduce-scatter | sharding 改变 checkpoint 形态、恢复顺序和通信峰值 | OOM 边界、step time、通信、保存/加载、跨 world size 恢复；参考 [PyTorch FSDP](https://pytorch.org/docs/stable/fsdp.html) 与 [ZeRO](https://github.com/microsoft/DeepSpeed) |
| 混合精度与数值稳定 | FP32/BF16/FP16/FP8、loss scaling、累积精度和算子 fallback | 低精度可能改变收敛、溢出和质量；硬件支持不一致 | overflow、梯度统计、收敛曲线、最终任务质量和 kernel fallback |
| Checkpoint 与实验追踪 | 保存权重、优化器、scheduler、随机状态、数据位置和代码/配置 revision | 只有权重不能保证可继续训练或可审计 | 中断恢复、跨并行配置加载、校验和、元数据完整性 |
| 训练可复现性 | 固定随机源、容器/依赖、数据快照、硬件和非确定性算子 | seed 相同不等于跨硬件 bitwise 相同 | 记录差异预算，比较统计等价而非虚假的绝对一致 |

官方 [Megatron-LM/Core](https://github.com/NVIDIA/Megatron-LM) 目前同时展示 TP、PP、DP、EP、CP、混合精度和分布式 checkpoint；它应被用来理解并行组合的工程形态，而不是照抄成某个项目的固定模板。

## 后训练、适配与模型生命周期（P0/P1）

现有“预训练、后训练、RAG 与工具改变不同层次”是正确的总览，但还缺少可执行的选择和失败分析。

### 需要补的专题

1. **SFT 与数据格式**：监督目标、packing、mask、样本权重、长度分布和训练/验证切分；验证格式遵循率、任务质量和通用能力回归。
2. **PEFT**：LoRA 冻结基座并注入低秩矩阵，可大幅降低可训练参数和显存；但 rank、target modules、alpha、合并方式和量化底座决定效果。原始论文见 [LoRA](https://arxiv.org/abs/2106.09685)。
3. **QLoRA 与量化微调**：4-bit 基座与低秩适配降低显存；必须区分训练存储精度、激活精度、保存格式和部署 kernel。
4. **RLHF 与偏好优化**：SFT、奖励模型、PPO 是 InstructGPT 的经典链路；DPO 直接在偏好对上优化，省去显式在线 RL，但依赖偏好数据分布和参考策略。见 [InstructGPT](https://arxiv.org/abs/2203.02155) 与 [DPO](https://arxiv.org/abs/2305.18290)。
5. **蒸馏、剪枝与模型合并**：教师-学生目标、结构裁剪、权重合并和路由合并各自改变容量与能力；不能把压缩后的 benchmark 提升外推为生产收益。
6. **持续训练与灾难性遗忘**：增量数据、回放、混合比例、版本回滚和能力边界；验证新域提升是否伴随旧域退化。
7. **模型注册与供应链**：权重、tokenizer、配置、许可证、训练数据声明、评测、漏洞和来源必须绑定；只保存一个 `model.bin` 无法复现部署。

每个适配专题都应包含“何时用 RAG、何时 SFT、何时 PEFT、何时重新预训练”的决策表，并用相同任务集比较质量、数据准备成本、训练成本、推理成本和回滚难度。

## RAG 全链路（P0）

当前已有 RAG 两篇上层页，但缺少把“证据系统”落到数据和检索实现的专题。这是用户明确指出的缺口，应作为第一批补写方向。

### 需要覆盖的完整链路

```text
来源与许可
  -> 解析/OCR/表格/代码抽取
  -> 文档版本、ACL、时间和父子结构
  -> 切块/标题/重叠/摘要/实体与关系
  -> 稀疏、稠密、向量、SQL、图和 API 索引
  -> 查询改写/分类/分解/过滤
  -> 多路召回与融合
  -> reranker / late interaction
  -> context packing、去重、压缩
  -> 生成、引用、拒答与事实核验
  -> 更新、删除、权限传播和回归
```

### 缺口清单

| 专题 | 核心机制 | 边界 | 验证 |
| --- | --- | --- | --- |
| 文档解析与知识单元 | 保留标题、表格、代码、页码、父子关系和来源 hash | 纯文本抽取会丢列关系、版面和权限 | 解析覆盖率、表格单元格准确率、代码符号完整性 |
| Chunking 与层次索引 | 以语义边界和问题粒度切块；父文档/摘要/子块并存 | 固定字符窗口可能拆开条件与结论；过大块污染 context | gold evidence 的边界召回、token 成本和引用精度 |
| Embedding 与向量索引 | 向量距离生成语义候选；索引控制召回/延迟/更新 | embedding 相似度不能代替权限、版本或事实判断 | Recall@k、索引构建/更新、跨域和 OOD |
| 稀疏、稠密与混合检索 | BM25/倒排擅长专名、数字、代码；dense 擅长改写；融合取互补 | 只看向量会漏掉版本号、否定和精确标识 | 分桶测 lexical/dense/hybrid 的 Recall、MRR/nDCG |
| 重排与 late interaction | cross-encoder 或 ColBERT 在较小候选集上做细粒度交互；见 [ColBERT](https://arxiv.org/abs/2004.12832) | 更准通常更慢；领域迁移和候选截断会反转收益 | nDCG、rerank 延迟、候选数敏感性 |
| 查询改写/分解 | 把用户语言变成检索表达；多跳问题拆成可验证子问题 | 改写可能改变意图、增加查询爆炸和成本 | 意图保持率、子问题覆盖、每步增益/成本 |
| 反思与纠错检索 | Self-RAG 按需检索并反思；CRAG 先评估检索质量再补源或过滤 | 反思 token/循环不是事实证明；错误评估会放大污染 | retrieval evaluator calibration、证据支持率和循环上限 |
| RAPTOR/GraphRAG | 层次摘要适合跨段全局问题；图结构适合实体关系和全局主题；见 [RAPTOR](https://arxiv.org/abs/2401.18059) 与 [GraphRAG 官方仓库](https://github.com/microsoft/graphrag) | 建图、实体消歧、更新和存储成本高，不能替代普通检索 | 按问题类型分桶比较简单 RAG、层次/图方案的收益 |
| Context packing 与压缩 | 在 token 预算内保留高支持度、互补、最新和可引用内容 | 长上下文仍有位置偏差和干扰；压缩可能丢条件 | evidence coverage、lost-in-middle、引用支持和 token/延迟 |
| Freshness、ACL 与删除 | revision、valid time、租户和权限在召回前过滤；撤权需传播到缓存和索引 | “索引已更新”不等于缓存、摘要、向量和图已更新 | 删除传播时间、越权零容忍、旧版本命中率 |
| 多模态 RAG | 图片、PDF、音频、视频需要 OCR、布局、视觉 embedding 和时间轴 | 单一文本化会丢图表/空间信息；模态错配导致假支持 | 按模态测召回、证据定位、解析失败和端到端任务 |

应新增一张“RAG 组件与问题类型”关系图：精确查值优先 SQL/倒排，语义开放问答用 dense/hybrid，多跳关系考虑图，实时状态调用 API；不要把所有问题都归入向量数据库。

## Agent、工具与运行时（P0/P1）

现有 Agent 页面原则比较完整，但缺少从模型输出到运行时状态的实作级专题。

### 应补的主题

- `ReAct、计划-执行、反思和搜索的差异`：ReAct 把推理与行动交错，优点是可根据观察调整路径；边界是循环、成本、私有推理泄露和不可重放，原始论文见 [ReAct](https://arxiv.org/abs/2210.03629)。
- `结构化输出、函数调用与约束解码`：schema 只保证形状，不保证业务事实、权限或副作用；验证 JSON schema、语义约束、版本兼容、拒答和重试。
- `Agent 状态机与任务恢复`：状态、事件、checkpoint、取消、超时、重试、补偿和人工审批必须分别建模；验证重复副作用、旧版本恢复和部分成功。
- `工具契约与动态工具发现`：输入/输出 schema、幂等键、scope、速率和错误分类；工具搜索减少上下文噪声，但不能扩大授权。
- `浏览器/Computer Use Agent`：截图、点击、键盘和页面变化是高噪声观察；必须使用沙箱、域名/动作白名单、人工确认和结果验证。
- `代码 Agent`：仓库索引、构建画像、测试、补丁、worktree、进程和产物证据；模型可以判断语义，运行时必须验证命令和退出码。
- `多 Agent 通信`：何时用普通函数、工作流、MCP 或 A2A；MCP 连接工具/资源，A2A 管理远程 Agent 的任务和状态，不能互相替代。规范见 [MCP](https://modelcontextprotocol.io/specification/2026-07-28) 与 [A2A](https://a2a-protocol.org/v1.0.0/specification/)。
- `记忆写入治理`：事实、偏好、摘要、任务状态分开；写入需要来源、主体、置信度、过期、纠错和删除；验证污染、串租户和撤回。

## 推理后端与 AI 性能（P0/P1）

已有 prefill/decode、KV cache 和容量页，但仍缺少“为什么这些优化有效”的硬件和算法基础。AI 后端不应只写成 vLLM/LLM 框架清单。

### 必须补的机制链

1. **GPU 执行模型**：SM、CUDA core/Tensor Core、HBM、L2、PCIe/NVLink、kernel launch 和 occupancy；验证 roofline、带宽、算力、同步和 host/device 拷贝。
2. **Attention 与 IO**：标准 attention 的中间矩阵和 HBM 访问；FlashAttention 通过 tiling 减少 HBM 读写，是 IO-aware 的精确算法，见 [FlashAttention](https://arxiv.org/abs/2205.14135)。验证算子时间、显存峰值、序列长度和数值误差。
3. **KV cache 管理**：每个请求的 KV 随生成增长；PagedAttention 用分页减少碎片并支持共享，见 [PagedAttention/vLLM](https://arxiv.org/abs/2309.06180)。验证碎片、命中率、抢占、租户隔离和长尾延迟。
4. **调度与批处理**：continuous batching、chunked prefill、队列公平、优先级、截止时间和 token budget；验证 TTFT、ITL、E2E p50/p95/p99、goodput 和饥饿。
5. **Prefill/Decode 分离**：prefill 偏计算，decode 偏内存带宽；分离可降低干扰，但增加 KV 网络传输和两个池的调度复杂度。验证短请求/低并发/慢互联等反例，而不是默认拆分。
6. **量化**：GPTQ、AWQ、SmoothQuant 分别处理权重、激活和校准分布；低 bit 不是一个布尔开关。见 [GPTQ](https://arxiv.org/abs/2210.17323)、[AWQ](https://arxiv.org/abs/2306.00978)、[SmoothQuant](https://arxiv.org/abs/2211.10438)。验证 perplexity、核心任务、异常 token、kernel 支持、显存和端到端吞吐。
7. **推测解码**：小模型先提出多个 token，大模型并行验证；在分布不变的条件下加速自回归解码，见 [Speculative Decoding](https://arxiv.org/abs/2211.17192)。验证接受率、序列长度、额外显存和不同任务收益。
8. **并行与通信**：DP、TP、PP、专家并行、上下文并行和多节点拓扑共同决定容量；通信不能只看带宽峰值。验证 scaling efficiency、collective 时间、pipeline bubble、故障恢复和跨节点成本。
9. **服务控制面**：模型注册、权重缓存、LoRA adapter、灰度、路由、限流、扩缩、健康检查、热升级和回滚；验证版本绑定、冷启动、缓存抖动、实例驱逐和请求重放。
10. **容量模型与成本**：将请求长度分布、输出 token、并发、显存、GPU 小时、网络和失败重试转成 token/s、goodput、$/成功任务；GPU utilization 单指标不足。

应增加“性能实验模板”页，强制记录模型/量化/硬件/引擎版本、输入输出长度分布、并发到达过程、warm-up、采样参数、质量集、SLO 和置信区间。

## 质量、评测与可观测性（P0/P1）

当前有轨迹评测和决策追踪，但缺少可落地的评测科学。AI 系统必须把“回答好不好”拆成可归因的证据。

### 应补齐的评测层

| 层 | 应测什么 | 常见错误 |
| --- | --- | --- |
| 数据集 | 任务切片、难例、负例、时间切分、权限切分、污染和版本 | 只挑容易样本；测试集被 prompt/训练数据泄漏 |
| 模型能力 | 事实、推理、代码、工具、长上下文、结构化输出 | 用一个总分替代任务分布；忽略成本和延迟 |
| RAG | 解析、召回、排序、证据覆盖、引用支持、新鲜度和 ACL | 最终答案正确就认为检索正确 |
| Agent 轨迹 | 动作选择、参数、工具结果、重试、停止、状态和副作用 | 只看最终文本；把模型解释当执行事实 |
| 端到端任务 | 成功率、人工接管、恢复、用户等待、成本和风险 | 忽略失败后恢复和人工成本 |
| 安全 | 注入、越权、数据外泄、工具投毒、恶意文件和供应链 | 只做静态 prompt 黑名单 |
| 线上运营 | p50/p95/p99、goodput、漂移、回归、灰度、回滚和预算 | 只看平均延迟或 GPU 利用率 |

### 缺失的评测方法页

- **LLM-as-judge 校准**：固定 rubric、位置交换、盲测、人评抽样、分歧分析和 judge 版本锁定；judge 不是事实来源。
- **成对比较与置信区间**：同一输入比较版本，报告 bootstrap 区间和切片差异，避免把小波动写成提升。
- **数据污染与时间切分**：模型/检索库/评测集的来源和时间要可追踪；新鲜知识任务应使用冻结时间点。
- **线上灰度与回归**：模型、prompt、工具 schema、索引和后端版本必须作为同一变更单元；失败不能覆盖已确认成功的事实。
- **可观测性语义**：trace 记录模型、prompt、检索候选、引用、工具调用、token、延迟、错误和成本；敏感内容采用脱敏 hash/引用句柄。

可用 [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) 理解可复现实验的任务适配和输出聚合，用 [HELM](https://crfm.stanford.edu/helm/) 理解多维、可扩展的模型评测框架；两者都不能替代业务任务集。

## 安全、隐私与治理（P0/P1）

当前已有沙箱、权限和事实边界，但没有系统的威胁模型。需要按攻击路径，而不是按“安全最佳实践”罗列。

### 应补的攻击与防护链

| 攻击面 | 机制 | 防护与验证 |
| --- | --- | --- |
| 直接/间接提示注入 | 不可信文本改变模型指令，检索文档、网页和工具结果都可能携带指令 | 指令与数据分区、来源标记、工具 scope、沙箱；使用可执行攻击集和越权断言 |
| 工具投毒与能力漂移 | 工具描述/返回结果诱导模型扩大权限或改变参数 | schema 签名、版本锁定、服务端授权和输出验证；审计实际调用 |
| 数据外泄 | prompt、检索、日志、trace 和错误返回拼接出敏感信息 | 数据分级、最小出站、脱敏、租户隔离、保留期限和撤回测试 |
| 越权与混淆代理 | 模型生成的身份、租户或 scope 被系统误认为真实身份 | 授权决策在模型外执行，凭据绑定主体；构造跨租户回归 |
| 供应链 | 模型权重、LoRA、容器、依赖、数据集和 tokenizer 带来恶意代码/许可证风险 | 来源、hash、SBOM、签名、扫描、沙箱加载和回滚 |
| 不安全输出到执行器 | 生成 SQL、shell、HTML、代码或工作流参数造成副作用 | 解析器、allowlist、参数化、dry-run、人工审批和执行后验证 |
| 可用性攻击 | 超长上下文、循环工具调用、昂贵检索或恶意并发消耗资源 | token/步骤/时间/预算上限、队列隔离、熔断和成本告警 |
| 内容与社会风险 | 偏见、毒性、错误建议、合成内容和责任不清 | 场景化红队、人工升级、内容策略、溯源和事故响应 |

[NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) 与其生成式 AI Profile 提供生命周期化的治理框架；[OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/) 可作为攻击面索引，但每条风险都必须转成自身系统可执行的测试断言。

## 多模态与专业模型（P1/P2）

当前 AI 系统目录几乎默认“文本 LLM”，这会遗漏实际工程中的视觉、音频、视频、OCR、文档版面和代码模型。

应补的主题包括：

- 视觉-语言模型的 encoder、projector、cross-attention/early fusion 以及图像分辨率对 token、显存和延迟的影响；
- OCR、版面、表格和图表理解，及其在文档 RAG 中的证据定位；
- 语音识别、说话人分离、TTS、实时流式和端点检测；
- 视频抽帧、时间索引、长视频检索和多模态上下文压缩；
- 图像/音频生成的扩散、采样步数、条件控制和安全过滤；
- 代码模型的 fill-in-the-middle、编译反馈、仓库级检索和许可证检查；
- 多模态 embedding、跨模态检索和模态缺失时的降级策略。

每个专题都要把模态转换损失、输入预算、实时 SLO、隐私、版权和可验证证据写清楚，不能只介绍模型名字。

## 建议新增的专题页集合

以下是按当前目录直接可落地的第一批页面。标题用知识点和工程问题表达，不按课程或年份命名。

### `模型与上下文`

- `Token、词表与上下文预算`
- `Transformer：注意力、位置与残差如何工作`
- `解码、采样与结构化输出`
- `MoE：稀疏激活换来的容量与通信成本`
- `模型能力来自预训练、后训练还是推理时增强`
- `Scaling law、数据质量与训练预算`

### `知识与检索`

- `文档解析、切块与知识单元建模`
- `Embedding、倒排与混合召回`
- `Reranker、ColBERT 与候选集设计`
- `查询改写、分解与多跳检索`
- `RAPTOR、GraphRAG 与全局问题`
- `多模态 RAG：版面、表格与视觉证据`
- `RAG 的新鲜度、删除传播与权限隔离`

### `推理服务与平台`

- `GPU 执行、显存层次与 LLM 性能账本`
- `FlashAttention：性能来自减少数据搬运`
- `连续批处理、公平调度与 goodput`
- `量化的算法、数值风险与 kernel 约束`
- `推测解码与低延迟生成`
- `张量、流水线、数据、专家与上下文并行`
- `多模型、LoRA adapter 与权重缓存`
- `模型服务的容量模型、灰度与回滚`

### `Agent与工作流`

- `ReAct、计划-执行与反思的适用边界`
- `结构化输出不等于业务正确`
- `任务状态、checkpoint 与副作用恢复`
- `浏览器 Agent 的观察、动作与安全边界`
- `代码 Agent 的仓库探索、补丁和构建证据`
- `多 Agent 何时值得增加通信复杂度`

### `质量与运营`

- `从 benchmark 到真实任务集`
- `LLM-as-judge 的校准和人评抽样`
- `RAG/Agent 质量的分层归因`
- `数据污染、时间切分与可复现实验`
- `线上灰度、漂移、回归与回滚`
- `AI 系统的成本-质量-SLO 曲线`

### `安全与治理`

- `AI 系统威胁建模与攻击路径`
- `提示注入、工具投毒与间接指令`
- `模型/数据/依赖供应链与许可证`
- `隐私、租户隔离与数据出站控制`
- `生成内容溯源、人工接管与事故响应`

## 补写顺序

1. 先补模型基础、数据/训练、RAG 全链路和 GPU/推理基础，解决“看不懂现有页面”的问题；
2. 再补后训练、量化/并行、Agent 状态恢复和评测方法，解决“能实现但无法解释、验证和回滚”的问题；
3. 最后补多模态、模型供应链、前沿检索和专业模型，解决扩展方向和快速变化实现；
4. 每新增一页必须连到至少一个上层概念、一个后端或数据机制、一个质量/安全验证页；只有名词解释而没有边界和实验的页面不进入主知识区。

## 研究限制与复查

- 论文证明的是特定数据、模型和硬件下的实验结果，不是生产保证；所有性能数字必须在本地负载上重测。
- 框架、协议、模型版本、硬件支持和弃用状态属于快速变化事实，放在动态页和来源注册表，不写进稳定原理的标题。
- 本文只做缺口审计，未把每个缺口直接写成专题页；后续迁移时应保持一页一个核心问题，避免再次生成并列名词和课程流水账。
- 复查时优先检查：模型/API/协议下线，推理引擎调度与量化变化，评测标准变化，重大安全公告，以及当前任务集出现的新失败模式。
