"""复核本轮 12 篇优化结果（2026-09-25）。

四件事是否做到，看三个可量指标：自检是否 PASS、图密度是否达标、
篇幅是否补足。三项一起看，避免只过门禁但内容没长进。
"""
import re
import subprocess
from pathlib import Path

REPO = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
V = REPO / "vault/工程知识/软件构建：让变化可以理解、验证与交付/开发工具"
SKILL = Path("/data/code/AIagent/.agent/skills/knowledge-governor")

NAMES = [
    "Make描述依赖图，不自动保证可重复构建.md",
    "Git操作先区分工作区、索引与历史.md",
    "Linux调查先收集事实再改变状态.md",
    "本地复现环境是修线上问题的第一现场.md",
    "依赖供应链需要锁定来源与构建输入.md",
    "cherry-pick摘取的是补丁：摘取分支决定冲突面.md",
    "Docker与K8s词汇的设计逻辑.md",
    "依赖升级按风险分层：验证阶梯、节奏策略与 CVE 响应.md",
    "依赖升级的半衰期策略：跟随与锁定的平衡.md",
    "cli的参数设计：限速这类可调旋钮要暴露成参数，不能藏在配置文件里.md",
    "维护者信任是供应链信任的地基：贡献者治理与维护者变更审计.md",
    "Linux常用命令的词源地图.md",
]

ok = fail = 0
for name in NAMES:
    f = V / name
    if not f.exists():
        print(f"缺文件 {name}")
        fail += 1
        continue
    r1 = subprocess.run(["python3", str(SKILL / "scripts" / "article_selfcheck.py"),
                         str(f)], capture_output=True, text=True)
    passed = "PASS" in r1.stdout
    r2 = subprocess.run(["python3", str(SKILL / "scripts" / "illustration_audit.py"),
                         str(f)], capture_output=True, text=True)
    dens = re.search(r"密度 ([\d.]+)", r2.stdout)
    verdict = re.search(r"判定 (\S+)", r2.stdout)
    chars = re.search(r"有效字符 (\d+)", r2.stdout)
    if passed:
        ok += 1
    else:
        fail += 1
    print(f'{"PASS" if passed else "FAIL"} '
          f'{chars.group(1) if chars else "?":>5}字 '
          f'密{dens.group(1) if dens else "?":<5} '
          f'{verdict.group(1) if verdict else "?":<4} {name[:40]}')

print(f"\n自检通过 {ok} / {ok + fail}")
