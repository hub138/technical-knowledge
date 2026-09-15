# 内容与代码贡献规则

## 知识页

一页只解决一个可复用的问题。正文至少说明它解决什么、机制为何成立、何时适用、何时失效、如何验证，以及和哪些页面有关系。涉及版本、API、协议、价格、许可证或安全的内容必须写 `updated`、`review_after`、`change_rate` 和一手来源。

## 来源与更新

新的论文、项目、发布说明或外部文章先放到 `vault/知识库管理/更新候选`，核对后再并入主题页。不要把搜索摘要当作证据，也不要把一个 benchmark 的结果写成通用效果。历史材料可以解释演进，但不能直接代表当前实现。

## 项目目录

`projects/` 是上游源码快照。更新其中的项目时，保留原许可证、第三方声明和测试；不要提交 `node_modules`、`.next`、`.venv`、本机用户数据、日志或任何密钥。整合修改要在项目说明中记录来源和原因。

## 提交前检查

```bash
python3 -m compileall site packages/agent-foundation
python3 -m pytest packages/agent-foundation/tests
python3 site/server.py --root vault --host 127.0.0.1 --port 8878 --no-browser
```

网站只应读取 `vault/`，并能通过 Markdown 内链、来源链接和图谱回到原始页面。
