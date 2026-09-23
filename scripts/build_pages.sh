#!/usr/bin/env bash
# 生成 GitHub Pages 的静态产物：导出静态内容 + 把绝对引用改写成子路径可用。
#
# Pages 把站点放在 /technical-knowledge/ 子路径下，没有服务端路由，所以：
#   - 静态资源走相对路径（site/ 就在 index.html 旁边）
#   - API 请求指向静态导出的 json
#   - 查询路由（?view= / ?path= / ?domain=）留在页内，改写成 ./ 相对形式
#   - 真服务器路由（/learn、/papers、/sources、/projects、/insights、
#     /apps/...）静态托管没有，统一指去 dev 完整站
#
# 用法： bash scripts/build_pages.sh <仓库根> <输出目录>
# 本脚本是 GitHub Actions（.github/workflows/pages.yml）与本地复现的唯一来源：
# 两边跑同一份，避免规则漂移。

set -euo pipefail

root="$1"
out="$2"
# export_static.py 用了 dict[str, int] 这类内置泛型注解，要 Python 3.9+。
# Actions 的 ubuntu-latest 自带 3.12；本地如果是老 python3，用 PYTHON= 指定。
python_bin="${PYTHON:-python3}"

# GNU sed 的 -i 可直接无后缀；macOS 的 BSD sed 必须给后缀（'' 表示不留备份）。
# 一边是 Actions（GNU），一边是本地复现（BSD），所以按能力选参数。
if sed --version >/dev/null 2>&1; then
  SED_INPLACE=(-i)
else
  SED_INPLACE=(-i '')
fi

mkdir -p "$out"
"$python_bin" "$root/scripts/export_static.py" "$root" "$out"
cp "$root/index.html" "$out/"
cp -r "$root/site" "$out/site"

# 1) 静态资源相对化
sed "${SED_INPLACE[@]}" \
  -e 's|href="/static/|href="site/|g' \
  -e 's|src="/static/|src="site/|g' \
  -e 's|href="/favicon.svg"|href="site/favicon.svg"|g' \
  "$out/index.html"

# 2) API 请求改相对。version 是独立文件名，必须先于通配条目。
sed "${SED_INPLACE[@]}" "s|'/api/notes/version'|'api/notes-version.json'|g" "$out/index.html"
sed "${SED_INPLACE[@]}" "s|'/api/notes?|'api/notes.json?|g" "$out/index.html"
sed "${SED_INPLACE[@]}" "s|'/api/|'api/|g" "$out/index.html"

# 3) 单篇取用：静态 JSON 按 vault 目录镜像，拼原始路径
sed "${SED_INPLACE[@]}" \
  -e "s|'api/note?path='+encodeURIComponent(path)|'notes/'+path+'.json'|g" \
  -e "s|'api/note?path='+encodeURIComponent(article.path)|'notes/'+article.path+'.json'|g" \
  "$out/index.html"

# 4) 查询类路由（/?path=、/?view=）是 SPA 自己的状态，留在页内
sed "${SED_INPLACE[@]}" 's|href="/?|href="?|g' "$out/index.html"

# 5) pushState 的三种书写形态：无空格、逗号后带空格、反引号模板串。
#    不改写会跳到域名根（hub138.github.io/?path=...），脱离项目页。
#
#    反引号那条曾写成 s|,`/\?|,`./?|g —— BRE 里 \? 是"前一个字符可选"，
#    匹配吃掉 "/" 后替换文本又补一个 "?"，/?domain= 被写成 ./??domain=，
#    参数名变成 "?domain"，领域页永远解析不到（2026-09-23 实测）。
#    现在直接匹配字面 `/?`。
sed "${SED_INPLACE[@]}" \
  -e "s|,'/|,'./|g" \
  -e "s|, '/|, './|g" \
  -e 's|,`/?|,`./?|g' \
  "$out/index.html"

# 6) 首页留在静态站自己（查询路由），不许跟着兜底指去 dev
sed "${SED_INPLACE[@]}" 's|href="/"|href="?view=home"|g' "$out/index.html"

# 7) 兜底：其余 href="/..." 是真服务器路由，统一指去 dev 完整站
sed "${SED_INPLACE[@]}" 's|href="/|href="https://21.6.137.121:28788/|g' "$out/index.html"

# 8) site/ 内部同样有绝对引用：base.css 的 @import、js 里的 fetch 与导航
sed "${SED_INPLACE[@]}" 's|url("/static/|url("|g' "$out/site/base.css"
sed "${SED_INPLACE[@]}" -e 's|"/api/|"api/|g' -e "s|'/api/|'api/|g" "$out"/site/*.js

# 9) 查询路由留在页内（SPA 自己接），先于兜底执行
sed "${SED_INPLACE[@]}" 's|"/?|"?|g' "$out"/site/*.js

# 10) JS 里拼的 HTML 字符串也要处理：shell.js 注入的品牌位写的是
#     `href="/"`（class="tk-brand"），站点首页就在当前目录，不该指去 dev。
sed "${SED_INPLACE[@]}" 's|href="/"|href="?view=home"|g' "$out"/site/*.js
#     导航项在 site/nav.js 里以 `href: "/..."` 声明、由 shell.js 动态注入
#     侧边栏，不走 HTML 里的 href="，所以必须单独改写。此前只改了
#     index.html，nav.js 生成的链接整份没动：知识库点开跳域名根、
#     论文/来源/项目/学习中心点开 404（2026-09-23 实测）。
sed "${SED_INPLACE[@]}" 's|href: "/"|href: "?view=home"|g' "$out"/site/*.js
sed "${SED_INPLACE[@]}" 's|href: "/|href: "https://21.6.137.121:28788/|g' "$out"/site/*.js

# 11) 其余服务器路由统一指 dev（含 js 动态注入的链接赋值，
#     如 projects-page 的 learn.href = "/learn"）
sed "${SED_INPLACE[@]}" 's|href="/|href="https://21.6.137.121:28788/|g' "$out"/site/*.js
sed "${SED_INPLACE[@]}" 's|\.href = "/|.href = "https://21.6.137.121:28788/|g' "$out"/site/*.js

touch "$out/.nojekyll"
