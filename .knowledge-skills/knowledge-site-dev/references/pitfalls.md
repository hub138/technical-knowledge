# 踩坑记录（按症状索引）

全部为 2026-09-22/23 真实踩坑，每条含症状、根因、正解。

## 部署 / dev 服务器

### ssh 命令里嵌 python heredoc，断言失败静默
- **症状**：远端脚本"跑完了"但什么都没改，输出丢失，事后发现假报告。
- **根因**：`ssh '... <<EOF python ...'` 单引号嵌套 + 断言失败，后续命令因换行分隔照常执行。
- **正解**：远端多步操作分两条 ssh 跑；每步后加验证性 grep/输出；不要在一条 ssh 里塞「改 + 验证 + 继续改」。

### plutil -replace 是插入不是替换
- **症状**：改 LaunchAgent 数组元素后 ssh 参数翻倍，`Could not resolve hostname 旧值`。
- **根因**：`plutil -replace ProgramArguments.5` 在某些结构下插入新元素而非替换，旧值残留被 ssh 当成第二个主机名。
- **正解**：用 `python3 + plistlib` 重写数组；改完 `plutil -p` 全量核对；`launchctl bootout` → `bootstrap` 重载。

### LaunchAgent 服务名找不到
- **症状**：`launchctl kickstart -k gui/501/xxx` 报 Could not find service。
- **根因**：plist 存在但从未 bootstrap 过；或已 bootout。
- **正解**：`launchctl bootstrap gui/$(id -u) <plist>`；确认用 `launchctl print gui/$(id -u) | grep <label>`。

### nginx 裸跑时 systemctl reload nginx 报 inactive
- **症状**：dev 上 `systemctl reload nginx` → "nginx.service is not active"，但 28788 明明在服务。
- **根因**：dev 的 nginx 以 `daemon off` 裸跑（systemd 单元 disabled），systemd 不认。
- **正解**：直接 `nginx -s reload`（改完先 `nginx -t`）。

### dev 克隆本地分支叫 master
- **症状**：在 dev 上 commit 后 `git push` 推出/试图推出 master 分支，与 main 脱节。
- **正解**：已改名（`git branch -m master main` + `branch -u origin/main`）。在新克隆上遇到同样问题照做。

### SSH 隧道远端端口被占
- **症状**：`Warning: remote port forwarding failed for listen port 28787`，ExitOnForwardFailure 导致 ssh 反复重启。
- **根因**：远端同端口被旧会话或别的进程持有。
- **正解**：ssh 上去 `ss -tlnp | grep <port>` 找到持有者，处理后再起隧道；隧道 plist 加 `ExitOnForwardFailure=yes` 防静默假活。

### macOS 回环只有 127.0.0.1 一扇门
- **症状**：本地服务绑 `--host 127.0.0.1`，局域网 IP（192.168.x.x）访问被拒。
- **根因**：回环和网卡是两个接口；绑哪扇门只能从哪进。
- **正解**：要局域网可访问就绑 `0.0.0.0`；只想自己访问就绑 127.0.0.1。Linux 的 127.0.0.0/8 天然全通，macOS 不是。

## 前端 / 浏览器

### 「我看不到变化」四连
- 按序排查：① URL 对吗（18787=dev 旧版 ≠ 18788=本地测试）② dev 拉了吗（5 分钟窗口）③ 浏览器缓存（Cmd+Shift+R + curl 服务端 grep 新标记）④ 重启窗口内加载的旧 JS（重新 goto）。逐一都有真实翻车记录。

### playwright 截图截到骨架屏
- **症状**：截图里是「正在读取知识库...」。
- **根因**：notes 数据 1.5MB，加载 6-8 秒。
- **正解**：sleep 7+ 或等 `#reader-title` 有值再截；顺手 `console error` 查静默失败。

### 函数定义插进别的函数闭包
- **症状**：页面整体正常，但新函数 `typeof === 'undefined'`，顶层调用 ReferenceError。
- **根因**：python 字符串替换把定义插进了 `async function initialize()` 内部（缩进相同区域），作用域被闭包。
- **正解**：定义放顶层（如 renderHome 前）；编辑后 `node --check` + 页面 eval `typeof fn` 双验。

### 高亮撞车：推荐位冒充位置态
- **症状**：常驻推荐项抄了 aria-current 实底框样式，用户「完全不知道现在在哪个页面」。
- **正解**：两套语义两种视觉——实底框=当前位置；推荐位=暖橙底色文字（无框）。见 design-language.md。

### CSS 写死色值，深色主题刺眼
- **正解**：全部走 token（--color-warm-soft 等），深浅主题自适应；SVG 描边用 currentColor。

## 数据 / 后端

### view:* 合成路径被 vault 校验清空
- **症状**：视图进入打点落库后 path 为空串，中台看不出"有人看过全景"。
- **根因**：handle_visit 用 vault.note(rel) 校验，非笔记路径归一为空。
- **正解**：`view:` 前缀的合成路径保留原样入库。

### 测试数据污染真实数据
- **症状**：本地测试实例的截图迭代把测试打点写进真实 data/。
- **正解**：测试实例启动必带 `KNOWLEDGE_DATA_HOME=/tmp/knowledge-test-data`；夹具数据从 dev 拷贝。

### 运营者自己的浏览污染监控
- **正解**：handle_visit/handle_feedback 开头 `client_is_operator()` 豁免（返回 skipped:operator）。
- **注意**：豁免需要 OPERATOR_PASSWORD env 配置 + 运营者 cookie；本地测试实例要同配 env 才能复现。

### git grep / grep -c 零命中时退出码 1
- **症状**：`cmd1 && grep -c pattern file` 在零命中时整链"失败"。
- **正解**：验证型 grep 放在链尾，或用 `|| echo 0` 收尾；别让退出码误导判断。

## 工具链

### macOS sed -i 语法
- macOS 要 `sed -i '' -e '...'`；Linux 是 `sed -i -e '...'`。跨机器脚本注意。

### sed 双重替换
- **症状**：链接被改写成 `https://x/https://x/...`。
- **根因**：多条 sed 规则的匹配串在后一条的替换结果里再次出现。
- **正解**：每条 sed 后立即 grep 检查"双写标记"（如 28788/https）；规则按"具体→兜底"排序。

### bash heredoc 里的反引号与引号层级
- **症状**：嵌套 heredoc 的字符串匹配莫名失败。
- **正解**：含反引号/单引号的内容用独立 python 脚本处理，别硬塞 sed。

## 内容展示

| 症状 | 根因 | 正解 |
|---|---|---|
| 页面上出现调研过程/方法论解释/内部思考 | 把「给站长看的分析」当成了页面内容 | 页面只放受众要的；过程收进按钮或删除 |
| 列表里混着几年前的旧内容还标「最新」 | 无时效过滤 | 时效预算：论文 2024 后、好文近两月、早报本周 |
| 删掉区块后旁边空一大块 | 只删不补位 | 删除后重新设计布局 |
| 图片列表里无图的条目显示怪异 | 同一样式套有图/无图 | 无图条目换样式或归类 |
| 外部 API 每次刷新都实时拉取 | 无缓存策略 | 抓取固定化落盘 + 定时更新（API 有配额） |
| JS heap OOM（4GB/8GB） | 超长会话内存累积 | 压缩上下文/重启会话/重活拆会话 |
| 长英文标题在窄容器换行 | 容器宽度未利用/未截断 | 利用右侧空间或 ellipsis |
| 小字看不清（标签/按钮/徽标） | 字号字重过小 | 加粗加大，截图核对可发现性 |

## 2026-09-24 新增（二级页 / 导航 / 验证）

### 改完代码没重启，一切验证都在证伪旧行为
- **症状**：curl 返 200、playwright 却是旧页面；同一份代码三个实例表现不一致。
- **根因**：28787（systemd）、18788、8787 是三个独立进程，改文件不触发重载。
- **正解**：改完立刻重启 28787（`systemctl restart knowledge-site.service`）与
  18788/8787（`bash /data/code/AIagent/scripts/restart_knowledge_sites.sh`），再验证。

### 迁移页面后旧路由先被通配分支截获，返 503
- **症状**：`/learn/path` 迁到 `/panorama/reading` 后，旧地址返 503
  `{"error":"learning page unavailable"}` 而不是 308。
- **根因**：`/learn/path` 仍留在 `LEARNING_PAGES` 里，前面的精确匹配分支先命中，
  去读已删除的 `apps/learning/path.html`，OSError → 503。
- **正解**：迁移页面时**从旧路由表里删掉条目**，只留重定向表；路由表与重定向表
  必须分开维护，别指望「加了重定向就自动不走旧表」。

### `n.tags` 是数组，不是对象
- **症状**：迁移后的页面列表全空，段勾选正常、无报错。
- **根因**：`kindOf` 写成 `n.tags && n.tags.kind`，而 `/api/notes` 的 tags 是
  字符串数组，取对象属性永远 undefined。
- **正解**：段归属一律走 `TKMatrix.classify(note).kind`，不要自己解析 tags。

### 两个导航项指向同一 URL，高亮只会落在一个上
- **症状**：点「学习路线」子项，侧栏高亮却是「我的阅读」。
- **根因**：`aria-current` 按 page key 判定，两个子项 href 相同时无法区分。
- **正解**：给其中一个加锚点（`#rd-path`），page key 由 `location.hash` 判定；
  页面内 `history.replaceState` 必须把 `location.hash` 拼回去，否则锚点被抹掉；
  侧栏在 DOMContentLoaded 已渲染完，锚点变化要自己回灌 `aria-current`。

### playwright 在本站的两个固定写法
- `wait_until="networkidle"` 在本站必超时（有轮询请求），一律用 `domcontentloaded` + 显式 sleep。
- 18788 实例无需登录；`/insights` 那条登录流程只对带密码的实例用。

### 折叠控件只认小箭头
- **症状**：用户点父项行文字区没反应，以为「点了会刷一下、页面不动」。
- **根因**：toggle 按钮宽高 22px 绝对定位在行尾，其余区域是链接；链接又带
  `preventDefault` 只折叠不跳转。
- **正解**：toggle 铺满整行（`top/right/bottom/left: 0`）负责折叠，跳转改由折叠组
  内的「总览」项承担，两个动作不再抢同一个点击区。

## 配图验收的站点服务坑

- **服务启动即报 KeyError**：Linux 下启动站点服务必须设 `KNOWLEDGE_SITE_PASSWORD` 环境变量（任意非空值），缺变量直接崩溃。服务命令 `python3 site/server.py --root <仓库>/vault --host 0.0.0.0 --port 28787`，监听 `127.10.0.1:28787`。服务已在运行时重复启动报地址占用，先 `curl -s -o /dev/null -w "%{http_code}" http://127.10.0.1:28787/` 确认 200 再直接用。
- **探测用根路径**：文章路径里有空格与中文，拼进 URL 探测会失败，造成服务在跑的假象。
- **页面参数要带 `工程知识/` 前缀**：页面参数是 vault 相对路径，漏前缀接口返回 not found、页面停在骨架屏。
- **SPA 未加载完数图必得 0**：正文显示「正在读取知识库…」时数图块必得 0，先确认骨架屏消失再截图。
- **竖排链超 6 节点留意容器限高**：截图发现裁切先分归属——图确实过长的压缩图，渲染端限高过紧的调站点样式，改完重截。
