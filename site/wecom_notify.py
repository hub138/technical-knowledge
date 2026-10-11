# -*- coding: utf-8 -*-
"""企业微信群机器人通知：knowledge-site 全部脚本共用的一个小模块。

为什么是独立模块
----------------
server.py 里已经有一个 notify_wecom()，但它长在 3000 多行的服务端里，
脚本这边 import server 会把整台站点拉起来（绑端口、读数据目录、初始化
论文评分），定时任务用不了。这里抽成独立文件：webhook key 的读取、
限频、发送，谁 import 谁就能用，两端行为保持一致。

key 从哪来
----------
优先读环境变量 KNOWLEDGE_WECOM_WEBHOOK_KEY（Linux/容器部署，cron 里
source /etc/knowledge-site.env 后天然可用）；没有再走 macOS Keychain
（服务端 WECOM_SERVICE="knowledge-site-wecom" 同一条）。两处都没有
就静默跳过——通知是增益能力，没配 key 的环境不该到处报错。

限频
----
同一条摘要 10 分钟内只发一次（md5 去重）。定时任务因为 flock 串行、
站点反馈本来低频，这个额度足够防重复触发，不需要按来源分别计数。

用法
----
    from wecom_notify import notify_wecom, notify_wecom_md
    notify_wecom("【知识库】papernotes 索引刷新：10,432 篇")       # 纯文本
    notify_wecom_md("**✅ 索引已刷新**\n> 10,432 篇 · <font color=\"comment\">28.5MB</font>")

    # 站点服务端（替代原 notify_wecom）：
    from wecom_notify import notify_wecom
    threading.Thread(target=notify_wecom, args=(summary,), daemon=True).start()
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
ENV_KEY = "KNOWLEDGE_WECOM_WEBHOOK_KEY"
KEYCHAIN_SERVICE = "knowledge-site-wecom"
DEDUPE_WINDOW_SECONDS = 600
MAX_CONTENT_CHARS = 1900          # 企微 text 消息上限 2048 字节，中文留余量
REQUEST_TIMEOUT_SECONDS = 6

# 进程内去重表：摘要 md5 -> 上次发送时间。cron 任务每次都是新进程，
# 表随进程生灭；对常驻的站点服务，它挡住 10 分钟内的重复反馈。
_recent: dict[str, float] = {}


def _read_env_key() -> str:
    return (os.environ.get(ENV_KEY) or "").strip()


def _read_keychain_key() -> str:
    """读 macOS 钥匙串；Linux/容器没有 /usr/bin/security，返回空串。"""
    if platform.system() != "Darwin":
        return ""
    try:
        query = subprocess.run(
            ["/usr/bin/security", "find-generic-password",
             "-a", os.environ.get("USER", os.getlogin()), "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=4, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return query.stdout.strip() if query.returncode == 0 else ""


def webhook_key() -> str:
    """webhook key：环境变量优先，Keychain 兜底。都没有返回空。"""
    return _read_env_key() or _read_keychain_key()


def _state_file() -> Path:
    """去重状态落盘位置：data 目录跟着仓库走，cron 与站点实例共享。"""
    here = Path(__file__).resolve()          # .../technical-knowledge/site/wecom_notify.py
    repo = here.parent.parent                # .../technical-knowledge
    return repo / "data" / ".wecom-notify-state.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _state_file().write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _dedupe(summary: str) -> bool:
    """True = 10 分钟内发过同一条，本次跳过。"""
    digest = hashlib.md5(summary.encode("utf-8")).hexdigest()
    now = time.time()
    state = _load_state()
    last = state.get(digest, 0)
    if now - last < DEDUPE_WINDOW_SECONDS:
        return True
    # 顺手清过期项，状态文件不膨胀
    state = {k: v for k, v in state.items() if now - v < DEDUPE_WINDOW_SECONDS * 6}
    state[digest] = now
    _save_state(state)
    return False


def notify_wecom(summary: str, *, dedupe: bool = True) -> bool:
    """发一条企微群通知。返回是否真的发出（没配 key / 限频跳过 / 失败都是 False）。

    绝不抛异常：通知失败只打日志，调用方的主流程（反馈落盘、索引刷新）
    不该被一个群机器人拖垮。"""
    return _send({"msgtype": "text", "text": {"content": summary[:MAX_CONTENT_CHARS]}},
                 dedupe=dedupe)


def notify_wecom_md(content: str, *, dedupe: bool = True) -> bool:
    """发一条 markdown 类型通知：支持 **加粗**、<font color="info|comment|warning">色字</font>、
    > 引用、[链接](url)。长度上限 4096 字节，超限截断。

    与 notify_wecom 相同的失败语义：不抛异常，返回是否真的发出。
    """
    return _send({"msgtype": "markdown", "markdown": {"content": content[:4096]}},
                 dedupe=dedupe)


def _send(payload: dict, *, dedupe: bool) -> bool:
    try:
        key = webhook_key()
        if not key:
            return False
        digest_source = json.dumps(payload, ensure_ascii=False)
        if dedupe and _dedupe(digest_source):
            return False
        request = urllib.request.Request(
            WEBHOOK_URL + key, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.read()
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as error:
        print(f"[wecom] notify failed: {error}", flush=True)
        return False


if __name__ == "__main__":
    import sys
    message = sys.argv[1] if len(sys.argv) > 1 else "【知识库】wecom_notify 模块自测"
    sent = notify_wecom(message, dedupe=False)
    print("sent" if sent else "skipped (no key / send failed)")
