"""GitHub Pages 静态导出：把动态 API 落成同形状的静态文件。

用法: python3 scripts/export_static.py <仓库根> <输出目录>

使用仓库内容与 requirements.txt 中的渲染依赖。产物（相对输出目录）：
- api/notes.json        首页文章列表全量（单文件应答所有分页请求）
- api/notes-version.json 与上面同一个 signature（10 秒轮询不再拉全量）
- api/digest          优雅降级（静态托管没有 BestBlogs 数据源）
- api/papers          论文索引（paper/ 目录在仓库里，构建时可用）
- notes/<原路径>.json   单篇载荷（镜像 vault 目录结构），形状与
  /api/note?path= 一致；前端拼原始路径取用
"""
import importlib.util
import json
import re
import sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("kserver", repo / "site" / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

vault = server.Vault(repo / "vault")


def write(rel: str, obj) -> None:
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


listed = [n for n in vault.notes.values() if n["listed"]]

# 1) 文章列表：全量进一个文件。前端分页循环看的是
#    offset(已收条数) < total —— 首页响应直接给全量，循环体不跑。
cap = 600
notes = []
for n in listed:
    public = {k: v for k, v in n.items() if k not in {"body", "mtime", "listed"}}
    body = str(n["body"])
    public["excerpt"] = server.excerpt(body, str(n["title"]))
    public["search_text"] = body[:cap]
    notes.append(public)
graph_paths = {str(n["path"]) for n in notes if not n.get("exclude_from_graph")}
edges = [e for e in vault.edges() if e["source"] in graph_paths and e["target"] in graph_paths]
signature = vault.signature()
write("api/notes.json", {
    "notes": notes,
    "total": len(notes),
    "offset": 0,
    "signature": signature,
    "edges": edges,
})
write("api/notes-version.json", {"signature": signature})

# 2) 单篇载荷：文件名 = encodeURIComponent(路径)，与前端改写后的
#    fetch('notes/'+encodeURIComponent(path)+'.json') 一一对应。
for n in listed:
    rel = str(n["path"])
    public = {k: v for k, v in n.items() if k not in {"body", "mtime", "listed"}}
    rendered = server.render_markdown(str(n["body"]), vault, rel)
    rendered = re.sub(r"^<h1\b[^>]*>.*?</h1>\s*", "", rendered, count=1, flags=re.DOTALL)
    # 站内笔记链接改相对：项目子路径下指向本页自身，SPA 从 location.search
    # 取 path 再取 notes/*.json（绝对 /?path= 会跳出项目页）。
    rendered = rendered.replace('href="/?path=', 'href="?path=')
    public["html"] = rendered
    public["raw"] = str(n["body"])
    write(f"notes/{rel}.json", public)

# 3) 早报：静态托管没有 BestBlogs 数据源，返回与后端同形的空态，
#    页面显示自己的"暂无内容"而不是报错。
write("api/digest", {
    "items": [],
    "error": "GitHub Pages 是静态镜像，早报请访问完整站点（内网 21.6.137.121:28788）",
})

# 4) 论文索引：paper/ 目录在仓库里，直接可用。
write("api/papers", {"papers": vault.paper_index(), "method": server.PAPER_METHOD_NOTE})

# 5) 领域树：侧栏知识树的数据源（跳过总览/Clippings/归档，与后端同口径）。
counts: dict[str, int] = {}
for n in vault.notes.values():
    category = n.get("category") or ""
    topic = n.get("topic") or ""
    if not category or category in {"总览", "Clippings"}:
        continue
    if topic == "归档":
        continue
    counts[category] = counts.get(category, 0) + 1
write("api/domains", {
    "domains": [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
})

# 6) 收藏夹：favorites.json 在仓库里（唯一入库的运行数据）。
favorites_path = repo / "data" / "favorites.json"
entries = json.loads(favorites_path.read_text(encoding="utf-8")) if favorites_path.exists() else []
entries.sort(key=lambda e: float(e.get("favorited_at") or 0), reverse=True)
write("api/favorites", {"items": entries, "cap": server.FAVORITES_CAP})

# 7) 访客身份：Pages 上人人都是访客。
write("api/access", {
    "local_client": False,
    "knowledge_public": True,
    "tool_launch_requires_auth": True,
})

per_note = len(list((out / "notes").rglob("*.json")))
hostile = [str(n["path"]) for n in listed if any(c in str(n["path"]) for c in "?#%")]
for h in hostile:
    print(f"警告：路径含 URL 敌对字符，Pages 上取不到：{h}")
print(f"listed notes: {len(listed)}, per-note files: {per_note}, edges: {len(edges)}")
