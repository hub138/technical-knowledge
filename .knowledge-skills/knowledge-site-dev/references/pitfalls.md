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
