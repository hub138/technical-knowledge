"""批量标记已完成的优化文章（2026-09-25）。

editorial_pass.py done 会先跑 article_selfcheck，未 PASS 自动拒绝。
已确认全部 PASS 后统一标记，避免逐条手写 frontmatter 出错。
"""
import subprocess
from pathlib import Path

REPO = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
V = REPO / "vault/工程知识/软件构建：让变化可以理解、验证与交付/开发工具"
SKILL = Path("/data/code/AIagent/.agent/skills/knowledge-governor")
SCRIPT = SKILL / "scripts" / "editorial_pass.py"

NOTES = {
    "Make描述依赖图，不自动保证可重复构建.md":
        "补背景本质与代价段、依赖图与时间戳失效的量化锚点",
    "Git操作先区分工作区、索引与历史.md":
        "补索引层的背景本质与三层数据流图，改文末断链为相关列表",
    "Linux调查先收集事实再改变状态.md":
        "补代价本质段与只读取证时序图，明确回退成本判据",
    "本地复现环境是修线上问题的第一现场.md":
        "补应用本质段与三层复现决策图，理顺段落顺序",
    "依赖供应链需要锁定来源与构建输入.md":
        "补信任链背景段与四环依赖图、修正文末断链写法",
}

for name, note in NOTES.items():
    f = V / name
    r = subprocess.run(
        ["python3", str(SCRIPT), "done", str(f), "--agent", "agent-kg1",
         "--round", "1", "--content-changed", "--dims", "text,image",
         "--note", note],
        capture_output=True, text=True,
    )
    tail = (r.stdout or r.stderr).strip().split("\n")[-1]
    print(f'{"OK " if r.returncode == 0 else "FAIL"} {name[:40]:<42} {tail[:60]}')
