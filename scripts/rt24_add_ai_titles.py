# -*- coding: utf-8 -*-
"""rt24: 把 AI 系统工程域 94 篇文章标题的英文词条插入 i18n.js 词典。

背景：用户要求 EN 态文章标题翻译。标题词条量大（94 条），replace 工具
对超长文本易失配，改用脚本按锚点行插入。锚点是主题词条块尾（首页行后）。

用法：python3 scripts/rt24_add_ai_titles.py（幂等：已有标题词条则跳过）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes.json")

# 94 篇标题的手工精译。键为文章标题原文，值为英文。
TITLES = {
    "AI 系统工程：把模型能力变成生产能力": "AI systems engineering: turning model capability into production capacity",
    "AI 辅助研发必须形成证据闭环": "AI-assisted development must close the evidence loop",
    "知识库的学习闭环：从来源到迁移": "The knowledge base learning loop: from sources to transfer",
    "Agent状态机与任务恢复：进度是状态不是聊天记录": "Agent state machines and task recovery: progress is state, not chat history",
    "ReAct计划执行搜索：三种行动范式的适用边界": "ReAct, planning, and search: where each action paradigm fits",
    "代码智能体需要结构索引、任务探索与运行证据": "Coding agents need structural indexes, task exploration, and runtime evidence",
    "任务分解的质量决定 Agent 的上限": "Task decomposition quality caps the agent",
    "先用工作流，只有路径无法预先枚举时才使用 Agent": "Use workflows first; reach for agents only when paths cannot be enumerated",
    "反思要有外部锚点，否则只是自我说服": "Reflection needs external anchors, or it is self-persuasion",
    "多智能体只在能并行或需要独立上下文时才值得": "Multi-agent systems pay off only for parallelism or isolated contexts",
    "工具是受约束的能力，不是提示词里的函数名": "Tools are constrained capabilities, not function names in a prompt",
    "构建可靠 Agent 应用：从模型调用到可运营系统": "Building reliable agent apps: from model calls to operable systems",
    "模型负责判断，运行时负责执行语义": "Models judge; the runtime owns execution semantics",
    "浏览器与Computer Use Agent：高噪声观察下的受控操作": "Browsers and computer-use agents: controlled action under noisy observation",
    "结构化输出与约束解码：schema约束形状，事实另需验证": "Structured output and constrained decoding: schemas constrain shape; facts still need checking",
    "结构化输出的约束解码：让模型输出可解析": "Constrained decoding for structured output: making model output parseable",
    "AI 可以做语义决策，系统必须守住事实边界": "AI can make semantic decisions; the system must guard factual boundaries",
    "执行证据必须独立于 AI 结论": "Execution evidence must be independent of AI conclusions",
    "提示注入和工具越权是不同威胁": "Prompt injection and tool privilege escalation are different threats",
    "模型与数据供应链需要可验证来源": "Model and data supply chains need verifiable provenance",
    "模型权重文件是可执行输入：从 pickle 信任模型到格式即边界": "Model weight files are executable input: from pickled trust to format-as-boundary",
    "沙箱限制能力，策略限制行为": "Sandbox limits capability; policy limits behaviour",
    "红队测试与越狱防御：提示注入的攻防工程": "Red-teaming and jailbreak defence: the engineering of prompt injection",
    "AI 平台必须统一模型、数据、评测与发布版本": "An AI platform must unify models, data, evaluation, and releases",
    "FlashAttention是IO感知的精确算法，不是近似": "FlashAttention is IO-aware and exact, not an approximation",
    "GPU显存管理决定服务容量上限": "GPU memory management caps serving capacity",
    "Prefill 与 Decode 决定 LLM 服务如何调度": "Prefill and decode decide how LLM serving schedules",
    "批处理、KV 缓存、量化与并行如何改变服务容量": "How batching, KV cache, quantisation and parallelism change serving capacity",
    "推理批处理的两难：吞吐与延迟的调度天平": "The inference batching dilemma: throughput versus latency",
    "推理服务的单位请求成本从token定价推出来": "Unit request cost of inference serving follows from token pricing",
    "推理服务的核心矛盾是延迟、吞吐、显存与质量": "Inference serving's core tension: latency, throughput, memory, quality",
    "模型服务架构从单进程到分布式副本": "Model serving architecture: from single process to distributed replicas",
    "模型路由与级联：小模型过滤大模型兜底的省钱结构": "Model routing and cascades: small models filter, big models backstop",
    "模型量化的精度经济学：位宽精度与显存的三角": "The economics of quantisation: bits, precision, and memory",
    "数据集、特征与模型版本必须可追溯": "Datasets, features, and model versions must be traceable",
    "数据飞轮的工程闭环：日志回流清洗与标注": "The data flywheel loop: log reflux, cleaning, and labelling",
    "模型发布需要注册、灰度与回滚": "Model release needs a registry, canary rollout, and rollback",
    "训练数据治理：来源、许可与污染决定语料的长期价值": "Training data governance: provenance, licensing, and contamination decide long-term value",
    "KV缓存与上下文长度的显存账：为什么长上下文贵": "The KV-cache memory ledger: why long context is expensive",
    "上下文工程是在有限预算内构造决策现场": "Context engineering: building the decision scene within a budget",
    "上下文工程的分层设计：系统提示工具结果与记忆": "Layered context engineering: system prompts, tool results, and memory",
    "多轮对话要管理上下文而不是累积它": "Multi-turn dialogue must manage context, not accumulate it",
    "模型提出候选，系统定义正确性": "The model proposes; the system defines correctness",
    "记忆写入治理：来源、主体与过期决定记忆的可信度": "Memory-write governance: source, subject, and expiry decide trust",
    "记忆是受治理的状态，不是更长的聊天记录": "Memory is governed state, not a longer chat log",
    "跨会话状态的一致性先于记忆的长度": "Cross-session consistency comes before memory length",
    "预训练、后训练、RAG 与工具改变不同层次": "Pre-training, post-training, RAG, and tools change different layers",
    "GPU执行模型与显存层级：SIMT与合并访存": "The GPU execution model and memory hierarchy: SIMT and coalesced access",
    "LoRA与参数高效微调：改行为不改基座": "LoRA and parameter-efficient tuning: change behaviour, not the base",
    "MoE 用稀疏激活换取参数容量和通信复杂度": "MoE trades sparse activation for parameter capacity and communication cost",
    "MoE路由的工程问题：负载不均与显存碎片": "MoE routing in practice: load imbalance and memory fragmentation",
    "Scaling Law 把训练预算分配成可测量假设": "Scaling laws turn training budgets into measurable hypotheses",
    "Token、Embedding 与表示学习连接数据和模型": "Tokens, embeddings, and representation learning connect data and models",
    "Transformer 如何把序列建模成可扩展计算": "How Transformers turn sequence modelling into scalable computation",
    "位置编码和长上下文限制有效利用": "Positional encoding and long-context utilisation limits",
    "分布式训练与并行策略如何切分模型": "How distributed training and parallelism split a model",
    "后训练对齐与微调改变行为边界": "Post-training alignment and tuning shift behavioural boundaries",
    "多模态模型把不同输入映射到共同推理接口": "Multimodal models map different inputs to a shared reasoning interface",
    "投机采样与推测解码：小模型带路大模型确认": "Speculative sampling and decoding: small model leads, big model confirms",
    "混合精度与数值稳定：低位宽训练的溢出与下溢管理": "Mixed precision and numerical stability: managing overflow and underflow",
    "蒸馏与模型合并：用小模型承接已验证的能力": "Distillation and model merging: small models carrying proven capability",
    "解码与采样参数：概率分布到生成文本的控制面": "Decoding and sampling: the control plane from distribution to text",
    "解码采样决定生成行为而不是知识本身": "Decoding and sampling shape generation behaviour, not knowledge",
    "预训练数据决定模型能力上限": "Pre-training data caps model capability",
    "AI 技术动态": "AI tech radar",
    "Agent 技术栈选型不是框架排名": "Agent stack selection is not a framework ranking",
    "MCP与A2A的分工：工具协议与Agent协议不互相替代": "MCP versus A2A: tool protocol and agent protocol do not replace each other",
    "MCP 接入必须验证协议、身份与工具契约": "MCP integration must verify protocol, identity, and tool contracts",
    "MCP 连接能力，A2A 委托任务": "MCP connects capabilities; A2A delegates tasks",
    "模型、框架、运行时与协议解决不同问题": "Models, frameworks, runtimes, and protocols answer different questions",
    "精调与RAG的边界：什么时候微调更划算": "Fine-tuning versus RAG: when tuning pays off",
    "GraphRAG 适合关系与全局问题但成本更高": "GraphRAG fits relational and global questions, at higher cost",
    "RAG 数据管道从文档到可引用证据": "RAG data pipelines: from documents to citable evidence",
    "RAG的新鲜度与权限传播：撤回的数据不能再被检索到": "RAG freshness and permission propagation: revoked data must stay unretrievable",
    "RAG 的核心是选择可引用证据": "The heart of RAG is selecting citable evidence",
    "向量数据库不是 RAG 本身": "A vector database is not RAG itself",
    "多模态RAG：图表、PDF与音频的证据不能只靠文本化": "Multimodal RAG: charts, PDFs, and audio need more than text conversion",
    "检索从一次查询演进为有状态的证据获取": "Retrieval is evolving from one-shot queries to stateful evidence gathering",
    "混合检索、重排与查询改写各自解决什么问题": "Hybrid retrieval, reranking, and query rewriting: what each one solves",
    "Agent 的缓存与结果复用": "Agent caching and result reuse",
    "Agent评估系统的设计契约": "The design contract of an agent evaluation system",
    "Agent 评测必须覆盖轨迹，而不只看最终答案": "Agent evaluation must cover trajectories, not just final answers",
    "RAG 评测要分离检索质量与生成质量": "RAG evaluation must separate retrieval quality from generation quality",
    "人在环路要设在不可逆的决策点": "Put humans in the loop at irreversible decision points",
    "可观测性必须能重建一次决策": "Observability must be able to reconstruct a decision",
    "可靠生成需要结构、证据、拒答与回归": "Reliable generation needs structure, evidence, refusal, and regression",
    "失败要分类才能对症下药": "Failures must be classified before they can be treated",
    "学习活动需要结果、轨迹与迁移证据": "Learning activities need outcome, trajectory, and transfer evidence",
    "幻觉的工程边界——哪些场景模型不该被单独信任": "The engineering boundary of hallucination — where models must not be trusted alone",
    "成本控制要从上下文和重试两头下手": "Cost control works both ends: context and retries",
    "提示词是代码，要版本化和回归测试": "Prompts are code: version them and regression-test them",
    "离线评测与在线评测回答不同问题": "Offline and online evaluation answer different questions",
    "评测集的构建与维护决定所有评测的地基": "Building and maintaining eval sets is the foundation of all evaluation",
    "评测集的构建与维护：从场景采样到难度分层": "Building and maintaining eval sets: from scenario sampling to difficulty tiers",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    # 幂等检查：已插入过则跳过。
    marker = "rt24·标题批 1/7"
    if marker in src:
        print("already inserted; skip")
        return

    # 对照 notes.json 核对键集（防止标题抄错）。
    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    ai_titles = {n["title"] for n in notes if n["category"].startswith("AI 系统")}
    missing = ai_titles - set(TITLES)
    extra = set(TITLES) - ai_titles
    if missing or extra:
        print("MISMATCH vs /tmp/notes.json")
        for t in sorted(missing):
            print("  missing:", t)
        for t in sorted(extra):
            print("  extra:", t)
        sys.exit(1)

    # 生成词条块（JS 语法，与既有词典风格一致）。
    lines = [
        "    /* 【rt24·标题批 1/7】AI 系统工程域 94 篇文章标题。用户要求",
        "       EN 态标题翻译（点名篇目在此域）。标题多为机制陈述句，按",
        "       导航语气精译。Clippings 外部剪藏标题保留原文不译。 */",
    ]
    for zh, en in TITLES.items():
        # JSON dumps 保证引号/破折号正确转义。
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：主题词条块尾（首页行）之后插入。
    anchor = '    "首页": { en: "Home" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
