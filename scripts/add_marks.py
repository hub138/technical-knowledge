"""给本轮改写但未带 editorial 标记的文章补标记（2026-09-25）。

改写时直接写 frontmatter 的部分篇章已带标记，这里只补漏的，
并统一刷新 updated。字段顺序按 optimize.md 的约定。
"""
from pathlib import Path

V = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge"
         "/vault/工程知识/软件构建：让变化可以理解、验证与交付/开发工具")

NOTES = {
    "依赖升级按风险分层：验证阶梯、节奏策略与 CVE 响应.md":
        "补验证阶梯的按类型分流图，保留三条机制与断言",
    "依赖升级的半衰期策略：跟随与锁定的平衡.md":
        "补升级债复利曲线图，保留三档节奏与边界",
    "cli的参数设计：限速这类可调旋钮要暴露成参数，不能藏在配置文件里.md":
        "补三级覆盖链图，清理要点块与叙述重复",
    "维护者信任是供应链信任的地基：贡献者治理与维护者变更审计.md":
        "补四根柱子的递进关系图，去重重复 tag",
    "Linux常用命令的词源地图.md":
        "补四类构词逻辑图，修正参数表一处笔误",
    "cherry-pick摘取的是补丁：摘取分支决定冲突面.md":
        "补身份分裂的 gitGraph 图，清理加粗堆砌",
}

for name, note in NOTES.items():
    f = V / name
    text = f.read_text(encoding="utf-8")
    if "editorial_by: agent-kg1" in text:
        print(f"已有标记  {name[:44]}")
        continue
    block = (f'editorial_pass: 1\n'
             f'editorial_at: 2026-09-25\n'
             f'editorial_by: agent-kg1\n'
             f'editorial_note: "{note}"\n'
             f'editorial_dims: [text, image]\n')
    idx = text.find("\n---", 3)
    text = text[:idx] + "\n" + block + text[idx:]
    f.write_text(text, encoding="utf-8")
    print(f"已补标记  {name[:44]}")
