# 部署说明

## 本机入口（2026-09-22 起：转发隧道，唯一服务在 dev）

Mac 的 knowledge-site 进程已停用；8787 端口由
`com.leoqqian.knowledge-forward` LaunchAgent 接管——SSH 本地转发
`-L 0.0.0.0:8787:127.10.0.1:28787`，把 localhost:8787 与
macbook-pro-2.local:8787 的请求送到 dev 的站点。URL 不变，内容与
数据统一落在 dev（含中台，运营者密码登录一次管 14 天）。Mac 断网
或 dev 重启时隧道自动重连（KeepAlive）。

vault 仍在 Mac 上编辑并 push（dev 每 5 分钟自动拉取），创作流程不变。反向同样成立：在 dev 上开发并 push 后，Mac 侧 com.leoqqian.knowledge-pull（每 60 秒）自动拉取；有未提交改动时 Mac 侧跳过拉取，不搅局。
Mac 的历史访问数据已合并进 dev 的 data/visits.jsonl。
OpenMAIC/DeepTutor 两个学习工具仍跑在 Mac（各自独立 LaunchAgent），
从转发站点的"创建课堂"跳转 `localhost:3100/3782` 可直达；
经 dev 签发的启动 cookie 在 Mac 工具上的适配尚待打通。

需要临时起本机站时：先 bootout 转发隧道腾出 8787，再把 knowledge-site
的 plist 改回原名 bootstrap。手动启动使用：

```bash
./run-site.sh
```

服务绑定 `0.0.0.0:8787`。知识库、搜索、图谱、Markdown 和项目说明公开可读；只有启动 OpenMAIC/DeepTutor 这类会使用本机默认模型凭据的动作才需要授权。Mac 自己发起的工具启动免登录；其他设备启动工具时输入访问密码。服务根据 TCP 连接的真实来源地址判断是否为本机，不采信浏览器可伪造的 `Host`、`Origin` 或 `X-Forwarded-For`。密码保存在 macOS Keychain 的 `knowledge-site-access` 项中。

优先使用不随 Wi-Fi 地址变化的 Bonjour 主机名：

```text
http://MacBook-Pro-2.local:8787/
```

当前 LaunchAgent 已设置 `KNOWLEDGE_PUBLIC_HOST=MacBook-Pro-2.local`，所以工具跳转也使用这个名称。`health` 仍会显示当前数字地址，便于确认 Wi-Fi 状态。

`192.168.x.x`、`10.x.x.x` 是路由器分配给当前网络接口的地址，切换 Wi-Fi、租约刷新或网络重连后可能变化。Docker 的固定容器地址只在 Docker 私有网络内有意义，不能固定 Mac 在家庭或公司局域网中的地址。需要所有局域网设备都使用稳定数字地址时，在路由器里为这台 Mac 的 Wi-Fi MAC 地址设置 DHCP 保留；需要跨网络访问时，应使用带 TLS 和身份认证的反向代理或 VPN，而不是直接暴露 `8787`。

## 公网入口（dev 实例，21.6.137.121）

公网 `http://21.6.137.121:28788/` 由 **dev 服务器上的独立实例** 服务（不是 Mac）：
`/data/code/technical-knowledge` 克隆，`knowledge-site.service`（systemd）跑
`server.py --host 127.10.0.1 --port 28787`，nginx 28788 反代到它；
`knowledge-update.timer` 每 5 分钟从 GitHub main 拉取。推完代码 5 分钟内自动上线，
需要立刻生效就手动 `systemctl restart knowledge-site`。

**回环别名约定（2026-09-22 起）**：反代/隧道把外部流量接到 `127.10.0.1`，服务端
`origin_is_local(源, 目的)` 对落在这个别名上的连接一律判非本机——中台（/insights）、
工具启动密码门禁都依赖它。只看来源地址会把经代理进来的访客（源恒为 127.0.0.1）
误判成本机：实测公网可开中台、免密启动工具（白用模型凭据）。改动绑定或代理目标时
必须保持这个契约。打点对别名流量采信 nginx 覆写的 `X-Real-IP` 记录真实访客 IP
（仅用于记录，鉴权仍只看 socket 地址）。

**运营者密码（2026-09-22 起）**：中台（/insights）的显示与解锁条件从
"本机"扩展为"本机或运营者"。设置 `KNOWLEDGE_OPERATOR_PASSWORD`（env）
后，在任意域名的登录框输入这把密码即换发中台签名 cookie——反代架构下
代理流量无法从 TCP 层认出运营者，这把密码是补上的身份维度。两把钥匙
不同权：站点密码只解锁工具启动，读不了中台；运营者密码两者都解锁。
不配置时行为退回纯本机判定。

Mac 的 `com.leoqqian.knowledge-tunnel`（SSH 反向隧道）已下线：dev 实例接管公网入口
后，隧道抢不到 28787，留着只会崩溃循环。plist 保留（转发目标已改为
`127.10.0.1:8787`）备查；若要复活隧道，macOS 需先 `sudo ifconfig lo0 alias 127.10.0.1`
（Linux 的 127/8 天然可用，macOS 不是）。

## Docker

容器环境没有 macOS Keychain，必须显式提供密码文件：

```bash
mkdir -p .secrets
umask 077
printf '%s\n' '替换为长随机密码' > .secrets/knowledge_site_password
docker compose up -d --build
```

`.secrets/` 已被忽略，不得提交。容器默认只暴露知识站；OpenMAIC、DeepTutor 和评估入口应各自按上游项目的认证与部署说明运行，不要把它们的密钥写进本仓库。

## 网络边界

知识站不启用宽泛 CORS，也不信任 `X-Forwarded-For` 作为本机判定。若放到反向代理后，代理负责 TLS、域名和外部认证，应用仍保留密码和 API 认证；不要把服务直接暴露到公网而省略 TLS、限流和访问控制。
