# -*- coding: utf-8 -*-
# skill 文档与站点代码的漂移检测。
#
# skill 是静态文档，站点代码改名、删文件、换路由时文档指针悬空不会报错，
# AI 拿着过期文档继续干活会静默产出错误结果。本脚本把「文档引用的代码事实」
# 全部变成可校验断言，接进 check_all.py 统一门禁：
#
#   1. 路径引用  文档里写的 site/... scripts/... tests/... 等文件必须存在
#      （按顺序在三处解析：技术仓根、所在 skill 根、同级 skill 目录）
#   2. 代码锚点  文档依赖的代码内标识符（词表、迁移链、归层表）必须还在
#   3. API 路由  文档里写的 /api/... 必须能对上 server.py 的路由表
#   4. 字段消费  contract.md 声明的 frontmatter 字段必须至少被一个校验脚本消费
#   5. 词表交叉  contract.md、check_knowledge.sh、matrix.js 三处词汇集合互相对照，
#      矩阵 tags/types 收录了门禁不认的 type、契约写了词表没有的取值都算漂移
#   6. 词表落位  文章 frontmatter 的 tags 必须命中 matrix.js 词表（近似词给建议），
#      ASSIGN 归层必须覆盖工程知识全部文章，迁移链键必须指向真实目录
#   7. 红线在位  每个 SKILL.md 必须带安全边界类章节（红线/安全边界/不可做）
#   8. 脚本冒烟  skill 自带与字段消费方脚本必须可运行（--help / bash -n / 可编译）
#   9. 敏感文件  internal_names.txt 这类黑名单必须被 gitignore 保护或不在库中，
#      裸露状态（未忽略也未跟踪）报 ERROR——一次 git add . 就是泄露
#  10. 副本同步  .knowledge-skills/ 内嵌副本与聚合层主副本的逐文件差异（WARN）
#
# 来源台账（sources.md）里对其他 skill 脚本的提及属于叙述上游，不作执行承诺，
# 表格引述行与「cd <skill 目录」指引行跳过检测。pitfalls 的事故案例叙事
# 引用已删文件是叙事本体，不查存在性。
#
# 用法：
#   python3 scripts/check_skill_drift.py                  # 内嵌+聚合层全量（check_all 接入）
#   python3 scripts/check_skill_drift.py --no-articles    # 跳过文章级词表落位（快速档）
#
# 退出码：0 通过；1 有 ERROR。副本差异只 WARN，不挡门禁——发布版与本地版
# 的分叉是有意设计，差异列出来供人确认即可。

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
args_skills_dir_hint = None

# skill 文档依赖的代码内标识符。代码重构涉及改名时，先更新这张表，
# 检测器会强制文档与代码一起动
CODE_ANCHORS = {
    "site/matrix.js": ["LAYERS", "KINDS"],
    "site/shell.js": ["PATH_MIGRATIONS"],
    "site/panorama-data.js": ["ASSIGN"],
}

# contract.md 字段的消费方（按文件名在 governor scripts 与技术仓 scripts 找）
FIELD_CONSUMERS = [
    "check_knowledge.sh",
    "review_after.py",
    "editorial_pass.py",
    "article_selfcheck.py",
]

# 每个 SKILL.md 必须出现硬约束边界语言，出现任一即算在位
BOUNDARY_WORDS = ["禁止", "不得", "红线", "不可", "安全边界", "绝不", "必须"]

# 词表落位检查跳过的管理区文件（与 check_knowledge.sh 的 is_meta 口径一致）
META_EXCLUDE = ("知识库管理/", "知识库首页.md")

PATH_REF = re.compile(
    r"(?<![\w./-])((?:site|scripts|tests|apps|packages|papers|sources|projects|vault)"
    r"/[A-Za-z0-9_./-]+\.(?:py|js|sh|md|json|html|css|toml|yml))"
)
API_REF = re.compile(r"(?<![\w/])(/api/[a-z0-9_/{}.-]+)")


def is_attribution_line(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith("| `") or "cd <skill" in line:
        return True
    # 代码块里的续行：上一行以 cd <skill 开头时，紧跟的命令行同属叙上示例
    return stripped.startswith("python3 ") and "search.py" in line


def doc_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in (".md", ".py", ".sh"):
            if "__pycache__" in p.parts:
                continue
            yield p


def skill_roots(root: Path):
    """聚合层或内嵌目录下真正的 skill 目录：直接子目录且含 SKILL.md。
    technical-knowledge 是站点仓库本身，memory 等是笔记目录，都跳过。"""
    if (root / "SKILL.md").exists():
        yield root
        return
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name != "technical-knowledge" and (d / "SKILL.md").exists():
            yield d


def extract_frontmatter_fields(contract: Path):
    """contract.md 必填字段 yaml 代码块里的顶层字段名。"""
    text = contract.read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    if not m:
        print("ERROR  contract.md 没有 yaml 代码块，字段消费链断检")
        sys.exit(1)
    fields = []
    for line in m.group(1).split("\n"):
        fm = re.match(r"^([a-z_]+):", line.strip())
        if fm:
            fields.append(fm.group(1))
    return fields


def contract_type_vocab(contract: Path):
    """contract.md 里「type 已知集合：a、b、c」一行的取值集合。"""
    text = contract.read_text(encoding="utf-8")
    m = re.search(r"type 已知集合：([^\n]+)", text)
    if not m:
        return set()
    return {w.strip() for w in m.group(1).split("、") if w.strip()}


def find_contract():
    """字段约定文档按序探测：聚合层 governor 的 references/contract.md 是权威
    （技术仓的父目录即聚合层），vault 文章里的 yaml 块是正文示例不作约定源。"""
    candidates = [
        REPO.parent / "knowledge-governor" / "references" / "contract.md",
        REPO / ".knowledge-skills" / "contract.md",
    ]
    if args_skills_dir_hint:
        candidates.insert(
            0, Path(args_skills_dir_hint) / "knowledge-governor" / "references" / "contract.md")
    for c in candidates:
        if c.exists():
            return c
    return None


def server_routes():
    """server.py 源码里的全部 API 路由。"""
    src = (REPO / "site" / "server.py").read_text(encoding="utf-8")
    return set(re.findall(r"[\"'](/api/[a-z0-9_/{}.-]+)[\"']", src))


def resolve_ref(ref: str, skill_dir: Path, sibling_dirs):
    for base in (REPO, skill_dir, *sibling_dirs):
        if (base / ref).exists():
            return True
    return False


def check_skill_tree(skill_dir: Path, label: str, routes, errors, sibling_dirs):
    flag_ok = False
    for doc in doc_files(skill_dir):
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(skill_dir)
        in_incident = False
        lines = text.split("\n")
        for lineno, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("### "):
                in_incident = "503" in line or "症状" in line
            elif not stripped:
                in_incident = False
            # 事故案例叙事（症状/根因/正解）引用已删文件是叙事本体，不查存在性
            if in_incident:
                continue
            if is_attribution_line(line):
                continue
            for ref in PATH_REF.findall(line):
                if not resolve_ref(ref, skill_dir, sibling_dirs):
                    errors.append(f"{label}/{rel}:{lineno} 引用的文件不存在 {ref}")
            for route in API_REF.findall(line):
                if route in routes or (route + "/") in routes or route.rstrip("/") in routes:
                    continue
                errors.append(f"{label}/{rel}:{lineno} 引用的路由不存在 {route}")
        if doc.name == "SKILL.md":
            body = "\n".join(lines[3:])  # 跳过 frontmatter
            if any(any(k in line for k in BOUNDARY_WORDS) for line in body.split("\n")):
                flag_ok = True
    if not flag_ok:
        errors.append(
            f"{label}: SKILL.md 全文无边界语言（需出现 {'/'.join(BOUNDARY_WORDS[:5])} 等硬约束措辞）")


def check_anchors_and_fields(errors, contract_fields, consumer_text):
    for anchor_file, symbols in CODE_ANCHORS.items():
        path = REPO / anchor_file
        if not path.exists():
            errors.append(f"锚点文件不存在 {anchor_file}（代码改名后未更新 CODE_ANCHORS）")
            continue
        body = path.read_text(encoding="utf-8")
        for sym in symbols:
            if sym not in body:
                errors.append(f"{anchor_file} 缺少锚点 {sym}，依赖它的 skill 文档已过期")
    for field in contract_fields:
        if field not in consumer_text:
            errors.append(f"约定字段 {field} 没有任何校验脚本消费（字段改名后消费链断裂）")


def script_vocabs():
    """check_knowledge.sh 里的 KNOWN_* 词汇集合。"""
    src = (REPO.parent / "knowledge-governor" / "scripts" / "check_knowledge.sh").read_text(encoding="utf-8")
    vocabs = {}
    for key in ("TYPES", "STATUS", "RATE", "CONFIDENCE"):
        m = re.search(rf'^KNOWN_{key}="([^"]+)"', src, re.M)
        if m:
            vocabs[key] = set(m.group(1).split("|"))
    return vocabs


def matrix_vocab():
    """matrix.js 词表：LAYERS/KINDS 全部 tags 数组与 KINDS 的 types 数组。"""
    src = (REPO / "site" / "matrix.js").read_text(encoding="utf-8")
    tags, types = set(), set()
    for m in re.finditer(r"\btags:\s*\[(.*?)\]", src, re.S):
        tags.update(re.findall(r'"([^"]+)"', m.group(1)))
    for m in re.finditer(r"\btypes:\s*\[(.*?)\]", src, re.S):
        types.update(re.findall(r'"([^"]+)"', m.group(1)))
    return tags, types


def article_frontmatter_tags(path: Path):
    """单篇文章 frontmatter 的 tags 值列表。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return None
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    in_tags = False
    values = []
    for line in m.group(1).split("\n"):
        if re.match(r"^tags:\s*$", line):
            in_tags = True
            continue
        if re.match(r"^tags:\s*\[", line):
            return re.findall(r'"([^"]+)"|[\w/-]+', line.split("[", 1)[1].rstrip("]"))
        if in_tags:
            v = re.match(r"^\s+-\s*(.+)$", line)
            if v:
                values.append(v.group(1).strip().strip('"'))
            else:
                break
    return values


def check_vocab_cross(errors, warns, contract, gov_vocabs):
    """三源词汇交叉：契约 vs 门禁脚本 vs 矩阵词表。矩阵还收录站点页面级
    type（paper/note/index 等，不进工程知识文章），只对文章实际用到的
    type 要求矩阵收录；站点级 type 分歧降为 WARN 供确认。"""
    c_types = contract_type_vocab(contract)
    s_types = gov_vocabs.get("TYPES", set())
    for label, diff in (("契约有 门禁脚本没有", c_types - s_types), ("门禁脚本有 契约没有", s_types - c_types)):
        if diff:
            errors.append(f"type 词汇三源漂移：{label} {sorted(diff)}（改 contract.md 与 check_knowledge.sh 其中一处使一致）")
    m_tags, m_types = matrix_vocab()
    used = article_types_in_use()
    for t in sorted(used - m_types):
        errors.append(f"文章在用 type [{t}] 矩阵 Y 轴不认（matrix.js KINDS types 补录或文章改 type，"
                      f"否则矩阵 Y 轴落位靠猜）")
    site_level = m_types - s_types - used - {"case"}
    if site_level:
        warns.append(f"矩阵收录的站点级 type（不进工程知识文章，确认即可）：{sorted(site_level)}")
    return m_tags


def article_types_in_use():
    """工程知识文章 frontmatter 实际用到的 type 集合。"""
    vault = REPO / "vault" / "工程知识"
    used = set()
    if not vault.is_dir():
        return used
    for f in vault.rglob("*.md"):
        rel = f.relative_to(REPO).as_posix()
        if rel.startswith(META_EXCLUDE) or f.name == "知识库首页.md":
            continue
        m = re.search(r"^type:\s*(\S+)", f.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            used.add(m.group(1))
    return used


def check_vocab_landing(errors, warns, m_tags):
    """文章级词表落位：tags 命中词表给近似建议、ASSIGN 覆盖全量、迁移链指向真实目录。
    ASSIGN 键与迁移链都按站点视角写（工程知识/...，省略 vault/ 前缀），比对时补全。"""
    vault = REPO / "vault" / "工程知识"
    if not vault.is_dir():
        errors.append("vault/工程知识 不存在，词表落位检查失效")
        return
    vocab = sorted(m_tags)
    off_hits = 0
    for f in sorted(vault.rglob("*.md")):
        rel = f.relative_to(REPO).as_posix()
        if rel.startswith(META_EXCLUDE) or f.name == "知识库首页.md":
            continue
        tags = article_frontmatter_tags(f)
        if tags is None:
            continue
        for tag in tags:
            if tag in m_tags:
                continue
            off_hits += 1
            near = difflib.get_close_matches(tag, vocab, n=2, cutoff=0.6)
            hint = f"（近似：{' / '.join(near)}）" if near else ""
            if off_hits <= 8:
                warns.append(f"tags 未命中词表 {rel}: [{tag}]{hint}")
    if off_hits > 8:
        warns.append(f"tags 未命中词表共 {off_hits} 处，仅列前 8 条")

    pano_src = (REPO / "site" / "panorama-data.js").read_text(encoding="utf-8")
    # 键内可有 JS 转义引号（\" 是文件名的一部分），(?:[^"\\]|\\.)* 完整吃下再还原
    assign_keys = {f"vault/{k.replace(chr(92) + chr(34), chr(34))}"
                   for k in re.findall(r'"(工程知识/(?:[^"\\]|\\.)*\.md)":', pano_src)}
    current = {f.relative_to(REPO).as_posix() for f in vault.rglob("*.md")
               if not f.relative_to(REPO).as_posix().startswith(META_EXCLUDE)
               and f.name != "知识库首页.md"}
    missing = sorted(current - assign_keys)
    if missing:
        for rel in missing[:5]:
            errors.append(f"ASSIGN 未归层 {rel}（panorama-data.js 补一行 path → 层 id，不补不上八层栈）")
        if len(missing) > 5:
            errors.append(f"ASSIGN 未归层共 {len(missing)} 篇，仅列前 5 条")
    stale = sorted(k for k in assign_keys
                   if not (REPO / k).exists()
                   and not _migrated(k, shell_migrations()))
    if stale:
        for rel in stale[:5]:
            warns.append(f"ASSIGN 键指向不存在的文件 {rel}（确认 PATH_MIGRATIONS 迁移链是否覆盖该旧名）")
        if len(stale) > 5:
            warns.append(f"ASSIGN 失效键共 {len(stale)} 条，仅列前 5 条")

    shell_src = (REPO / "site" / "shell.js").read_text(encoding="utf-8")
    for old, new in re.findall(r'\[\s*"([^"]+)",\s*"([^"]+)"\s*\]', shell_src):
        if not old.endswith("/") or not new.endswith("/"):
            continue
        if not (REPO / "vault" / new).is_dir():
            errors.append(f"PATH_MIGRATIONS 目标目录不存在 vault/{new}（域名再改名后迁移链指向空处）")


def shell_migrations():
    """shell.js 的 PATH_MIGRATIONS 前缀对。"""
    shell_src = (REPO / "site" / "shell.js").read_text(encoding="utf-8")
    return [(old, new) for old, new in
            re.findall(r'\[\s*"([^"]+)",\s*"([^"]+)"\s*\]', shell_src)
            if old.endswith("/") and new.endswith("/")]


def _migrated(path: str, migrations):
    for old_prefix, new_prefix in migrations:
        if path.startswith("vault/" + old_prefix):
            return True
    return False


def check_scripts_smoke(errors, script_paths):
    """脚本冒烟：argparse 的 --help、shell 的 bash -n、全部 py 可编译。"""
    for p in script_paths:
        if p.suffix == ".sh":
            r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                errors.append(f"shell 语法错误 {p.name}: {r.stderr.strip()[:120]}")
        elif p.suffix == ".py":
            r = subprocess.run([sys.executable, "-m", "py_compile", str(p)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                errors.append(f"py 编译失败 {p.name}: {r.stderr.strip()[:120]}")
                continue
            src = p.read_text(encoding="utf-8")
            if "add_argument" in src or "add_parser" in src:
                r = subprocess.run([sys.executable, str(p), "--help"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    errors.append(f"脚本 --help 不可用 {p.name}（returncode={r.returncode}）: {r.stderr.strip()[:120]}")


def check_secret_files(skill_roots_list):
    """敏感文件守卫：黑名单类文件必须被 gitignore 保护或根本不存在，
    未忽略也未跟踪的裸露状态最危险——一次 git add . 就进库。返回违规列表。"""
    patterns = ("internal_names", "*黑名单*", "*blacklist*")
    candidates = []
    for root in skill_roots_list:
        candidates += [p for p in root.rglob("*") if p.is_file()
                       and any(p.name.startswith(pat.replace("*", "")) or p.name in pat.replace("*", "")
                               for pat in patterns)]
    violations = []
    for f in candidates:
        gitroot = f.parent
        while gitroot != gitroot.parent and not (gitroot / ".git").exists():
            gitroot = gitroot.parent
        if not (gitroot / ".git").exists():
            violations.append(f"敏感文件 {f.name} 所在目录不在 git 仓内，无法验证忽略状态")
            continue
        rel = f.relative_to(gitroot).as_posix()
        ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=gitroot).returncode == 0
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                                 cwd=gitroot, capture_output=True).returncode == 0
        if tracked:
            violations.append(f"敏感文件已进版本库 {rel}（黑名单不得入库，git rm --cached 后补 .gitignore）")
        elif not ignored:
            violations.append(f"敏感文件裸露 {rel}（未被 gitignore 保护，一次 git add . 就会入库；"
                              f"把 {f.parent.name}/{f.name} 加进该仓 .gitignore）")
    return violations


def sync_check(embed: Path, main: Path, warns):
    """内嵌副本与聚合层主副本逐文件比对。主副本侧的 skill 目录可能是
    指向内嵌的符号链接，此时二者天然一致，跳过。"""
    for skill_dir in sorted(embed.iterdir()):
        if not skill_dir.is_dir():
            continue
        counter = main / skill_dir.name
        if not counter.is_dir():
            warns.append(f"内嵌 {skill_dir.name} 在主副本目录 {main} 无对应")
            continue
        if counter.resolve() == skill_dir.resolve():
            continue
        for doc in doc_files(skill_dir):
            other = counter / doc.relative_to(skill_dir)
            if not other.exists():
                warns.append(f"{skill_dir.name}: 内嵌有 主副本无 {doc.relative_to(skill_dir)}")
                continue
            if doc.read_text(encoding="utf-8") != other.read_text(encoding="utf-8"):
                warns.append(f"{skill_dir.name}: 内嵌与主副本内容不同 {doc.relative_to(skill_dir)}")


def main() -> int:
    global args_skills_dir_hint, args_embed_dir_hint, args_no_articles
    parser = argparse.ArgumentParser(description="skill 文档与站点代码的漂移检测")
    parser.add_argument("--skills-dir", default=None,
                        help="聚合层主副本目录，缺省时自动探测（技术仓父目录含 governor 即视为聚合层）")
    parser.add_argument("--embed-dir", default=str(REPO / ".knowledge-skills"))
    parser.add_argument("--no-articles", action="store_true", help="跳过文章级词表落位（快速档）")
    args = parser.parse_args()
    args_skills_dir_hint = args.skills_dir
    args_embed_dir_hint = args.embed_dir
    args_no_articles = args.no_articles
    if args.skills_dir is None and (REPO.parent / "knowledge-governor" / "SKILL.md").exists():
        args.skills_dir = str(REPO.parent)

    contract = find_contract()
    if contract is None:
        print("ERROR  找不到字段约定文档（候选：governor references/contract.md、"
              ".knowledge-skills/contract.md），字段消费链断检")
        return 1
    contract_fields = extract_frontmatter_fields(contract)
    # 字段消费方按文件名在两处找：governor 的 scripts/（skill 自带）与技术仓 scripts/
    gov_scripts = contract.parents[1] / "scripts"
    search_dirs = [d for d in (gov_scripts, REPO / "scripts") if d.is_dir()]
    consumer_paths, missing = [], []
    for name in FIELD_CONSUMERS:
        found = next((d / name for d in search_dirs if (d / name).exists()), None)
        if found:
            consumer_paths.append(found)
        else:
            missing.append(name)
    for name in missing:
        print(f"WARN   字段消费方脚本缺失 {name}（消费链待人工确认）")
    if not consumer_paths:
        print("ERROR  找不到任何一个字段消费方脚本，消费链断检")
        return 1
    consumer_text = "\n".join(p.read_text(encoding="utf-8") for p in consumer_paths)

    routes = server_routes()
    if not routes:
        print("ERROR  server.py 路由提取为空，检测失效")
        return 1

    errors, warns = [], []
    embed = Path(args.embed_dir)
    if not embed.is_dir():
        print(f"ERROR  内嵌副本目录不存在 {embed}")
        return 1
    embed_roots = list(skill_roots(embed))
    if not embed_roots:
        print(f"ERROR  内嵌副本目录里没有 skill（{embed}）")
        return 1
    for root in embed_roots:
        siblings = [d for d in embed_roots if d != root]
        check_skill_tree(root, "embed/" + root.name, routes, errors, siblings)
    check_anchors_and_fields(errors, contract_fields, consumer_text)

    main_dir = Path(args.skills_dir) if args.skills_dir else None
    main_roots = []
    if main_dir and main_dir.is_dir():
        main_roots = list(skill_roots(main_dir))
        for root in main_roots:
            siblings = [d for d in main_roots if d != root]
            check_skill_tree(root, "skills/" + root.name, routes, errors, siblings)
        sync_check(embed, main_dir, warns)

    # 词表交叉与落位（文章级可 --no-articles 跳过）
    gov_vocabs = script_vocabs()
    m_tags = check_vocab_cross(errors, warns, contract, gov_vocabs)
    if not args.no_articles:
        check_vocab_landing(errors, warns, m_tags)

    # 脚本冒烟：字段消费方 + governor 自带脚本
    smoke = list(consumer_paths)
    if gov_scripts.is_dir():
        smoke += [p for p in sorted(gov_scripts.glob("*.py")) if p not in smoke]
    check_scripts_smoke(errors, smoke)

    # 敏感文件守卫：聚合层与内嵌两侧的 skill 目录都查，同一文件只报一次
    secret_seen = set()
    for e in check_secret_files([r for r in (*embed_roots, *main_roots)]):
        if e not in secret_seen:
            secret_seen.add(e)
            errors.append(e)

    if errors:
        for e in errors:
            print(f"ERROR  {e}")
        print(f"\n  {len(errors)} 处漂移：skill 文档与代码已不同步，先改代码侧或文档侧使其一致")
        return 1
    print(f"  skill-drift ok  约定字段 {len(contract_fields)} 个全部有消费方，"
          f"锚点 {sum(len(v) for v in CODE_ANCHORS.values())} 个全部命中，"
          f"路径与路由引用全部有效，词表三源一致，安全章节在位，"
          f"脚本 {len(smoke)} 个冒烟通过（skill {len(embed_roots)} 个）")
    for w in warns:
        print(f"WARN   {w}")
    if warns:
        print(f"\n  {len(warns)} 处 WARN（不挡门禁，逐条确认）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
