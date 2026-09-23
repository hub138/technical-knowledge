# 部署拓扑全图

## 服务拓扑

```
Mac 浏览器 ──→ localhost:18787（SSH 隧道，com.leoqqian.knowledge-forward）
                │
                ▼
        dev 21.6.137.121（内网开发机，唯一线上服务）
        nginx :28788 ──→ 127.10.0.1:28787（site/server.py，systemd knowledge-site）
                ▲
Mac vault 编辑 ──→ git push ──→ GitHub main ──→ dev 每 5 分钟自动拉取
```

- **dev 是唯一线上服务**。Mac 的 knowledge-site 已停用（plist .retired）；Mac 的 18787 是转发隧道不是站点。
- 回环别名 `127.10.0.1` 是安全约定：经代理/隧道进来的流量目的地址落在别名上 → 判非本机。Mac 本机测试绑 `0.0.0.0` 时不触发此判定（回环直连仍算本机）。
- dev 克隆路径随机器而定（用 `KNOWLEDGE_REPO` 或技能目录同级的 `technical-knowledge` 定位），本地分支 main。改 systemd/nginx 后要 `daemon-reload` / `nginx -s reload`（nginx 是 daemon off 裸跑，systemd 里 disabled）。

## 端口约定（五位数是后来的约定，别混）

| 端口 | 是什么 |
|---|---|
| 18787 | Mac 转发隧道入口（dev 内容） |
| 18788 | 本地测试实例（数据隔离在 /tmp/knowledge-test-data） |
| 28788 | 内网公开站（dev nginx） |
| 28787 | dev 站点进程（回环别名上） |
| 3100 / 3782 | Mac 上的 OpenMAIC / DeepTutor（独立 LaunchAgent） |

## 数据与监控

- 访问/反馈数据：dev `data/visits.jsonl`、`feedback.jsonl`（gitignore，不上 GitHub；Mac 历史数据已合并，备份 .bak-clean）。
- 打点覆盖：文章（记具体篇目）+ 首页/目录/图谱/全景（`view:*` 合成路径，每次页面加载一次，同 load 去重）。
- **运营者豁免**：持运营者 cookie 的会话，访问与反馈均不入库（`skipped: operator`）——中台数据只反映真实访客。
- view:* 合成路径在 handle_visit 里保留原样（不以 vault 校验清空）。
- 测试实例用 `KNOWLEDGE_DATA_HOME=/tmp/...` 隔离，截图迭代不会污染真实数据。

## GitHub Pages 静态镜像

- `https://hub138.github.io/technical-knowledge/`，Actions workflow（.github/workflows/pages.yml）。
- 构建时 `scripts/export_static.py` 导出静态 JSON，工作流 sed 改写 index.html 与 site/*.js 的请求模板到静态文件；`/api/*` 多数降级。
- push 会触发 workflow；若 legacy 残留构建后到覆盖，重新 dispatch 工作流即可。

## 仓库同步（双向编辑）

- GitHub main 是唯一枢纽。dev/Mac 各自 commit+push，各自自动拉取（dev 5 分钟 / Mac 60 秒）。
- Mac 拉取脚本 `scripts/pull-upstream.sh`：工作区脏 → 跳过；本地领先 → 跳过；分叉 → 报警不硬合并。
- dev 克隆本地分支曾叫 master，2026-09-23 已改名 main。
