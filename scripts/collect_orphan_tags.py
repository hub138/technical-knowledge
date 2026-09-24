# -*- coding: utf-8 -*-
# 游离 tag 收编：把文章 frontmatter 里不在 matrix.js 词表中的 tag，
# 按显式映射表归并到词表内的正式词条。
#
# 背景：check_skill_drift.py 扫出 183 处 tag 未命中词表（79 种写法）。
# 词表本身 303 个词条不扩——游离词绝大多数是同一概念的历史拼法
# （reliability → ai/reliability 或 backend/reliability 语义重复、
# performance → 按领域归 ai/performance 等已存在词条），收编不新增词。
#
# 每条映射必须显式写进 TAG_MAP；没有映射的词保持原样并打印出来，
# 不猜。dry 模式只报告，写模式同时更新文章 frontmatter。
#
# 用法：
#   python3 scripts/collect_orphan_tags.py --dry    # 只看会改什么
#   python3 scripts/collect_orphan_tags.py --write  # 实际写入

import argparse
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXCLUDE = ("知识库管理/", "知识库首页.md")

# 游离词 → 词表内正式词条。一行一个决定，按高频到低频排列。
TAG_MAP = {
    # 按文章领域拆分的宽泛词：performance 25 处分布在 ai/系统/软件构建，
    # 收编时按文章已归属的 tag 语境就近映射
    "performance": "__BY_DOMAIN__",
    "skill/mastery": "learning",
    "reliability": "__BY_DOMAIN__",
    "backend": "backend/architecture",
    "infrastructure": "backend/infrastructure",
    "configuration": "backend/config",
    "llm": "ai/models",
    "network": "systems/network",
    "net": "systems/network",
    "storage": "data/storage",
    "dist": "distributed-systems",
    "tradeoff": "architecture",
    "systems/programming": "software/engineering",
    "os": "systems/os",
    "stability": "software/resilience",
    "database/storage": "data/storage",
    "engineering/build": "software/engineering",
    "inference": "ai/inference",
    "ai/numerics": "ai/training",
    "systems/operations": "operations",
    "mlops": "ai/mlops",
    "agent/cost": "agent-engineering/operations",
    "fundamentals": "ai/fundamentals",
    "software-quality": "software/quality",
    "consensus": "distributed-systems/consensus",
    "performance/vectorization": "performance/cpu",
    "linux/vm": "systems/os",
    "systems/capacity": "resource-capacity",
    "performance/algorithm": "software/algorithms",
    "protocols": "web/http",
    "systems/performance": "performance/profiling",
    "performance/queueing-theory": "overload",
    "latency": "overload",
    "linux/network": "systems/network",
    "performance/io": "linux/io",
    "data-integrity": "data/reliability",
    "hw": "hardware",
    "resource-management": "resource-capacity",
    "ai/performance": "ai/serving",
    "gpu": "gpu/performance",
    "ai/memory": "systems/memory",
    "state-management": "backend/design-patterns/state-machine",
    "ai/radar": "research/freshness",
    "decision": "architecture",
    "quantization": "ai/training",
    "scheduling": "software/scheduling",
    "cost-model": "ai/serving",
    "ai/cost": "ai/serving",
    "distributed-systems/reliability": "distributed-systems",
    "agent/testing": "agent-engineering/testing",
    "dataset": "data",
    "hallucination": "ai/alignment",
    "safety": "ai/safety",
    "agent-engineering/reliability": "agent/reliability",
    "file-systems": "systems/filesystems",
    "modeling": "data/modeling",
    "data-quality": "data/quality",
    "ownership": "data/governance",
    "integration": "backend/integration",
    "event-time": "distributed-systems/time",
    "database/migration": "migrations",
    "open-source-governance": "supply-chain",
    "app": "web",
    "build/make": "software/dependencies",
    "tooling/git": "software/version-control",
    "backend/performance": "__BY_DOMAIN__",
    "continuous-integration": "software/ci-cd",
    "selection": "infrastructure/selection",
    "debugging": "software/debugging",
    "ai-assisted": "ai/coding-agents",
    "capacity-planning": "resource-capacity",
    "estimation": "resource-capacity",
    "backend/degradation": "resilience",
    "caching": "backend/cache",
    "api-design": "backend/api",
    "idempotency": "backend/transactions",
    "backend/reliability": "__BY_DOMAIN__",
    "devops/container": "infrastructure/containers",
    "service-mesh": "backend/service-mesh",
}


def vocab_of_matrix():
    src = (REPO / "site" / "matrix.js").read_text(encoding="utf-8")
    vocab = set()
    for m in re.finditer(r"\btags:\s*\[(.*?)\]", src, re.S):
        vocab.update(re.findall(r'"([^"]+)"', m.group(1)))
    return vocab


def article_domain(block: str):
    """文章 tags 里已有的语境词：按前缀族优先级取第一个命中词表语义的，
    用于宽泛词的就近映射。"""
    vals = frontmatter_tags(block)
    for pref in ("ai/", "performance/", "backend/", "data/", "systems/",
                 "distributed", "agent", "software/", "database/",
                 "networking", "tcp", "web/", "hardware", "gpu/",
                 "linux/", "operating-systems/", "memory", "storage"):
        for v in vals:
            if v.startswith(pref):
                return v
    return None


def frontmatter_tags(block: str):
    """frontmatter 块的 tags 列表（列表式与行内式都支持）。"""
    values = []
    intags = False
    for line in block.split("\n"):
        if re.match(r"^tags:\s*$", line):
            intags = True
            continue
        if re.match(r"^tags:\s*\[", line):
            values += re.findall(r'"([^"]+)"', line)
            intags = False
            continue
        if intags:
            v = re.match(r"^\s+-\s*(.+)$", line)
            if v:
                values.append(v.group(1).strip().strip('"'))
            else:
                intags = False
    return values


def resolve(tag: str, block: str, vocab):
    target = TAG_MAP.get(tag)
    if target is None:
        return None
    if target != "__BY_DOMAIN__":
        return target
    domain = article_domain(block)
    if domain is None:
        return None
    # 宽泛词的就近收编：ai/* 文章 → ai/…正式词条；其余 → 词表内的领域层
    if tag == "performance":
        return domain if domain in vocab else "performance/profiling"
    if tag == "reliability":
        if domain and domain.startswith("ai/"):
            return "ai/reliability"
        if domain and domain.startswith(("backend", "distributed")):
            return "distributed-systems"
        if domain and domain.startswith("data"):
            return "data/reliability"
        if domain and domain.startswith("agent"):
            return "agent/reliability"
        return "software/resilience"
    if tag == "backend/reliability":
        return "distributed-systems"
    if tag == "backend/performance":
        return "overload"
    return target


def rewrite_tags(text: str, mapping):
    """frontmatter tags 区重写：命中映射的替换，保持列表形态。"""
    m = re.match(r"(---\n)(.*?)(\n---)", text, re.S)
    block = m.group(2)
    intags = False
    out_lines = []
    for line in block.split("\n"):
        if re.match(r"^tags:\s*$", line):
            intags = True
            out_lines.append(line)
            continue
        if re.match(r"^tags:\s*\[", line):
            vals = re.findall(r'"([^"]+)"', line)
            new = [mapping.get(v, v) for v in vals]
            out_lines.append("tags: [" + ", ".join(f'"{v}"' for v in new) + "]")
            continue
        if intags:
            v = re.match(r"^(\s+)-\s*(.+)$", line)
            if v:
                val = v.group(2).strip().strip('"')
                out_lines.append(f"{v.group(1)}- \"{mapping.get(val, val)}\"")
                continue
            intags = False
        out_lines.append(line)
    return text[:m.start(2)] + "\n".join(out_lines) + text[m.end(2):]


def main() -> int:
    parser = argparse.ArgumentParser(description="游离 tag 收编（映射表驱动）")
    parser.add_argument("--dry", action="store_true", help="只报告")
    parser.add_argument("--write", action="store_true", help="实际写入")
    args = parser.parse_args()
    if not (args.dry or args.write):
        parser.error("需要 --dry 或 --write")

    vocab = vocab_of_matrix()
    changed = 0
    unresolved = {}
    for f in sorted((REPO / "vault" / "工程知识").rglob("*.md")):
        rel = f.relative_to(REPO).as_posix()
        if rel.startswith(EXCLUDE):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        block = m.group(1)
        vals = frontmatter_tags(block)
        mapping = {}
        for v in vals:
            if v in vocab:
                continue
            target = resolve(v, block, vocab)
            if target:
                mapping[v] = target
            else:
                unresolved.setdefault(v, []).append(rel)
        if not mapping:
            continue
        print(f"{rel}")
        for old, new in sorted(mapping.items()):
            print(f"    {old}  ->  {new}")
        if args.write:
            f.write_text(rewrite_tags(text, mapping), encoding="utf-8")
        changed += 1

    print(f"\n{changed} file(s) {'written' if args.write else 'to change (dry)'}")
    if unresolved:
        print(f"{len(unresolved)} tag(s) without mapping (left as-is):")
        for v, rels in sorted(unresolved.items()):
            print(f"  {v}  x{len(rels)}  e.g. {rels[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
