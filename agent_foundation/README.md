# Agent Foundation

这是与任何 Agent 框架、模型、CLI 实现、任务格式和应用系统无关的会话基础设施。
它不定义领域对象、应用规则或特定工具/模型的协议。

可直接给本地 CLI、远程代理桥接程序、浏览器自动化代理、MCP host 或长连接会话使用。

## 已提取能力

- `cli_session`：任意 CLI 的发起、stdout/stderr 读取、硬超时、空闲超时、心跳、进程组回收和 JSONL/SSE 流清理。
- `Event`：通用 append-only 会话事件；不假定工具名、模型名或输出字段。
- `recovery`：不透明 continuation checkpoint 的原子保存，以及调用者定义可重试边界的指数退避。
- `TranscriptWriter`：JSONL transcript、常见密钥/私钥块脱敏、容忍中断尾行的读取。
- `content`：JSON Pointer 取值、文本渲染、从裸文本或代码块中恢复 JSON；不校验指定 schema。
- `probe`：可执行文件发现和短时探测；认证是否有效由各 Agent 的适配器自行判断。

## 不包含的东西

- 任意特定 CLI 的参数、认证方式、会话字段名或输出 schema。
- 领域对象、数据库模型、检索策略、评估规则、编排策略或应用状态机。
- 对恢复后“应该继续做什么”的判断；包只保存调用者提供的 continuation。

## 使用示例

```python
from agent_foundation import ProcessSpec, ProcessSupervisor

result = ProcessSupervisor().run(
    ProcessSpec(
        ["your-agent-command", "..."],
        hard_timeout_seconds=1800,
        idle_timeout_seconds=300,
    )
)
```

各 Agent 仅需在自己的适配器中：构造命令、把自己的事件解码成 `Event`、保存自己的
continuation token。其余存活、恢复基础、记录和脱敏都复用本包。
