import re

# 目标：把 index.html 内联脚本里遗留的可选链写法改写为等价旧语法，
# 兼容旧手机 WebView（不认识 ?. 与 ??，解析即抛 SyntaxError）。
# 只做精确、已验证唯一性的字符串替换；替换清单先打印计数再落盘。

path = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/index.html"
with open(path, encoding="utf-8") as f:
    text = f.read()

pairs = [
    # zhHome 语言判断（renderHome）
    ("zhHome=window.TKI18N?.lang!=='en';const t_=(zhText,enText)=>(zhHome?zhText:enText);const lede=heroLede(zhHome);",
     "zhHome=!(window.TKI18N&&window.TKI18N.lang==='en');const t_=(zhText,enText)=>(zhHome?zhText:enText);const lede=heroLede(zhHome);"),
    # 图谱入口监听
    ("$('#home-graph')?.addEventListener('click',event=>{event.preventDefault();showGraph()});",
     "{const homeGraph=$('#home-graph');if(homeGraph)homeGraph.addEventListener('click',event=>{event.preventDefault();showGraph()});}"),
    # 状态卡标题读取
    ("const chip=card&&card.querySelector('.status');",
     "const chip=card&&card.querySelector('.status');"),
]

for old, new in pairs:
    n = text.count(old)
    print(f"count={n}  {old[:60]}")
    text = text.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("written")
