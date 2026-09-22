# -*- coding: utf-8 -*-
"""rt30: 知识库管理域 34 篇文章标题的英文词条插入 i18n.js（标题批 7/7，收尾批）。

背景：EN 态全站标题翻译。批 1-6（AI 系统工程 94、缺陷分析 60、后端系统 59、
软件构建 56、数据系统 40、性能工程 39）已完成。本批覆盖知识库管理域全部
34 篇，其中域总览「知识库管理」已在前批译出（查重核实），故插其余 33 条。
特殊条目：
- 「每日外部更新 {{date:YYYY-MM-DD}}」含日期模板占位符，EN 译法保留
  {{date:YYYY-MM-DD}} 原样（渲染层会替换占位符，不能译坏）。
- 「Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks」
  本身是英文论文标题，EN 词条同值（保证审计键集完整）。
幂等：已有 rt30 标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt30.json")

TITLES = {
    "AI 系统内容缺口研究": "AI systems content gap research",
    "全库新鲜度审计": "Whole-library freshness audit",
    "全量编辑进度": "Full editing progress",
    "知识库变更日志": "Knowledge base changelog",
    "外部输入区": "External input area",
    "学习与迭代方法": "Learning and iteration methods",
    "学习工具使用与调用成本": "Learning tool usage and invocation costs",
    "待核验内容": "Content pending verification",
    "每日外部更新 {{date:YYYY-MM-DD}}": "Daily external updates {{date:YYYY-MM-DD}}",
    "AI 研发迭代框架案例证据": "Evidence from AI R&D iteration framework cases",
    "Agent 应用工程技术核验": "Engineering verification of agent applications",
    "Archify：可验证技术图谱生成器": "Archify: a verifiable technical knowledge graph generator",
    "DeepTutor：带检索、记忆与研究闭环的学习伴侣": "DeepTutor: a learning companion with retrieval, memory and a research loop",
    "Matt Skills：让 AI 先理解再修改": "Matt Skills: let AI understand before it edits",
    "OpenMAIC：多智能体互动课堂与可复用技能": "OpenMAIC: multi-agent interactive classrooms and reusable skills",
    "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    "论文标题": "Paper titles",
    "项目或仓库名称": "Project or repository names",
    "来源与证据说明": "Sources and evidence notes",
    "外部来源注册表": "External source registry",
    "知识体系缺口审计": "Knowledge system gap audit",
    "知识库范围与结构": "Knowledge base scope and structure",
    "知识更新方法论": "Knowledge update methodology",
    "知识演化机制": "Knowledge evolution mechanisms",
    "知识点写作与教学输出契约": "The writing and teaching contract for knowledge points",
    "知识质量标准": "Knowledge quality standards",
    "面向发布的知识写作文风契约": "The publication-facing style contract for knowledge writing",
    "项目方法反哺机制": "The project-to-method feedback loop",
    "一篇知识怎么写": "How to write one piece of knowledge",
    "知识从哪来，怎么更新": "Where knowledge comes from, and how it updates",
    "知识完善度怎么判断——四象限与九个信号": "How to judge knowledge completeness: four quadrants and nine signals",
    "知识缺口怎么补——图谱关系槽与补强工作流": "How to fill knowledge gaps: graph relation slots and reinforcement workflows",
    "论文怎么追踪、怎么解析": "How to track and parse papers",
    "知识库管理": "Knowledge base management",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt30·标题批 7/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    kb_titles = {n["title"] for n in notes if n["category"].startswith("知识库管理")}
    missing = kb_titles - set(TITLES)
    extra = set(TITLES) - kb_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in extra:
            print("  extra:", t)
        sys.exit(1)

    # 「知识库管理」域总览已在前批译出，不重复插入，只断言存在。
    overview = "知识库管理"
    existing = set()
    for line in src.splitlines():
        if '"%s": { en:' % overview in line:
            existing.add(overview)
    if overview not in existing:
        print("overview entry missing; abort")
        sys.exit(1)

    entries = [(zh, en) for zh, en in TITLES.items() if zh != overview]
    lines = [
        "    /* 【rt30·标题批 7/7】知识库管理域 34 篇（域总览「知识库管理」",
        "       已在前批译出，本批插其余 33 条）。占位符 {{date:YYYY-MM-DD}}",
        "       原样保留；英文论文标题 EN 同值保键集完整。标题批至此收齐。 */",
    ]
    for zh, en in entries:
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 6（性能工程）尾部最后一行。
    anchor = '    "排队论给容量一个可推导的模型": { en: "Queueing theory gives capacity a derivable model" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(entries), "title entries (7/7 complete)")

if __name__ == "__main__":
    main()
