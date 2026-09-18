#!/usr/bin/env python3
"""Give every paper a Chinese title, keeping the original for the English view.

Why this is a file and not a translation call at build time: these are 44
well-known papers, and a title translated wrong is worse than one left in
English — a reader cannot tell "注意力就是你所需要的一切" from a bad rendering of
some other paper. The translations live here, are reviewed once, and are
versioned; the build script only copies them in.

Terms that name a method, model or library stay in the original script, per the
writing rules (中文叙述 + 英文术语、模型名保留原文). So it is
"RAG：面向知识密集型任务的检索增强生成", not "检索增强生成：面向知识密集型的
检索增强生成" — repeating the expansion of the acronym adds nothing.

Used by scripts/build-paper-notes.py via scripts/paper-titles.json.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(__file__).resolve().parent / "paper-titles.json"

# arxiv id -> Chinese title
TITLES = {
    # ── 2024 ──
    "2410.20878": "AutoRAG：自动优化 RAG 管道",
    "2404.16130": "从局部到全局：面向查询聚焦摘要的 Graph RAG 方法",
    "2403.14403": "Adaptive-RAG：按问题复杂度自适应选择检索策略",
    "2401.18059": "RAPTOR：面向树状组织的递归摘要式检索",
    "2401.15884": "Corrective RAG：让检索结果先过一遍自查",
    "2401.08281": "Faiss 向量检索库",
    "2401.04088": "Mixtral 混合专家模型",
    # ── 2023 ──
    "2310.11511": "Self-RAG：通过自我反思决定何时检索、如何评判",
    "2309.15217": "Ragas：RAG 管道的自动化评测",
    "2309.06180": "PagedAttention：大模型服务的高效显存管理",
    "2308.12966": "Qwen-VL：可理解、定位与读文字的多模态模型",
    "2308.08155": "AutoGen：用多智能体对话搭建 LLM 应用",
    "2306.07179": "神经网络训练算法的基准测试方法",
    "2306.05685": "用 MT-Bench 与 Chatbot Arena 检验 LLM 作为裁判的可靠性",
    "2306.00978": "AWQ：激活感知的权重量化",
    "2305.18290": "DPO：语言模型本身就是一个奖励模型",
    "2305.18654": "语言模型的组合能力边界",
    "2305.06983": "主动检索增强生成",
    "2304.08485": "视觉指令微调",
    "2303.11366": "Reflexion：用语言反馈做强化学习的智能体",
    "2302.12173": "间接提示注入如何攻破集成 LLM 的真实应用",
    # ── 2022 ──
    "2212.10496": "无需相关性标注的零样本稠密检索",
    "2211.17192": "投机解码：加速 Transformer 推理",
    "2211.10438": "SmoothQuant：大模型训练后量化的精度与效率平衡",
    "2210.17323": "GPTQ：生成式模型的训练后量化",
    "2210.03629": "ReAct：让推理与行动交替进行",
    "2205.14135": "FlashAttention：考虑 IO 的精确注意力计算",
    "2204.07196": "学习算法的分布假设检验",
    "2203.15556": "按计算量最优训练大模型",
    "2203.10050": "SURF：用数据增强的半监督奖励学习",
    "2203.02155": "用人类反馈训练语言模型遵循指令",
    # ── 2021 ──
    "2104.09864": "RoFormer：用旋转位置编码增强 Transformer",
    "2104.08646": "语言数据中的伪特征：如何发现与移除",
    "2104.04473": "用 Megatron-LM 在 GPU 集群上高效训练大模型",
    "2101.03961": "Switch Transformer：用稀疏激活扩展到万亿参数",
    # ── 2020 ──
    "2005.11401": "RAG：面向知识密集型任务的检索增强生成",
    "2004.12832": "ColBERT：基于上下文化延迟交互的高效段落检索",
    "2001.08361": "神经语言模型的缩放定律",
    # ── 2019 ──
    "1910.02054": "ZeRO：万亿参数模型训练的内存优化",
    "1908.10084": "Sentence-BERT：用孪生网络得到句子向量",
    "1904.09751": "神经文本退化的奇怪现象",
    # ── 2017 ──
    "1706.03762": "Attention Is All You Need：只靠注意力机制的 Transformer",
    "1701.06538": "稀疏门控混合专家层",
    # ── 2015 ──
    "1508.07909": "用子词单元翻译稀有词",
}


def main() -> None:
    registry = json.loads(
        (ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
         / "arxiv-registry.json").read_text(encoding="utf-8")
    )
    ids = set(registry["papers"])
    titled = set(TITLES)

    missing = sorted(ids - titled)
    extra = sorted(titled - ids)
    if missing:
        raise SystemExit(f"{len(missing)} paper(s) have no Chinese title: {missing}")
    if extra:
        raise SystemExit(f"{len(extra)} title(s) belong to no known paper: {extra}")

    OUT.write_text(json.dumps(TITLES, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.name} — {len(TITLES)} title(s), every paper covered")


if __name__ == "__main__":
    main()
