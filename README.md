# Agent Knowledge & Evidence Review

一个面向 AI Agent 开发与解析的知识工作台。它将通用 Agent 知识、当前协议与安全边界、公开评估项目和研究证据放在同一套可追溯的页面中。

不是罗列框架名，也不把某个基准分数写成通用结论。重点是理解一个 Agent 为什么有价值、在哪里失效，以及什么改动值得做。

## 能力

- **Agent 知识闭环**：任务契约、决策与工具、状态与检索、协作、安全、观测、评估和恢复。
- **项目差异化识别**：从 README、文档、代码与配置、演进记录、测试和运行轨迹提取目标 Agent 的任务侧重点、差异化机制和关键约束。
- **任务特定评估**：功能交付、缺陷修复、业务操作、检索和多 Agent 协作使用不同的判断维度，不套用统一评分表。
- **可视化交付**：将任务、证据、判断和改进建议连接成可阅读的路径，而非只给一个总分。
- **有边界的改进建议**：每项建议包含问题、可改动作、作用机制、外部证据、反例、成本和置信度。

## 解析一个 Agent 时，页面要回答什么

1. 它服务的高价值任务是什么，什么结果才算完成？
2. 它的差异化价值来自机制、数据、工具集成、工作流还是交互体验？
3. 当前设计已经保护了哪些关键风险，又留下了哪些可观察缺口？
4. 哪些改动真正保护或放大其核心价值，为什么可能有效，代价是什么？
5. 结论来自 README、代码、历史、测试、轨迹还是外部研究，它们之间是否一致？

README 与变更记录只提供声明和演进线索；代码、任务夹具、运行轨迹和重复结果才逐步提高结论的可信度。没有目标 Agent 的材料时，页面只给静态候选，不伪装成具体项目结论。

## 页面

`index.html` 提供两个公开页面：

- **知识体系**：按稳定能力对象组织 Agent 知识，避免把短期 SDK 或固定参数当成原理。
- **评估框架**：先建立被评测 Agent 画像，再交付优势、问题、定向方案、证据/置信度和可视化路径。

## 启动

```bash
git clone https://github.com/hub138/technical-knowledge.git
cd technical-knowledge
python3 app.py
```

打开终端输出的地址，或访问 `http://127.0.0.1:8080/index.html`。远程机器需要确保 `8080/tcp` 可访问。

## 参考依据

- [MCP 2025-11 Specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [A2A 1.0 Specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [AgentRx: trajectory-based failure diagnosis](https://github.com/microsoft/AgentRx)
- [AdaRubric: task-adaptive trajectory evaluation](https://github.com/alphadl/AdaRubrics)
- [Agent-as-a-Judge](https://github.com/metauto-ai/agent-as-a-judge)
- [Claw-Eval](https://github.com/claw-eval/claw-eval)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)

这些来源各自只支持其公开验证范围。项目提取可复用的判断机制，并保留适用边界、反例与待验证项。
