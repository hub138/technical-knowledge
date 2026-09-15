# 部署说明

## 本机守护进程

macOS LaunchAgent 已指向仓库中的 `vault/` 和 `site/`。手动启动使用：

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
