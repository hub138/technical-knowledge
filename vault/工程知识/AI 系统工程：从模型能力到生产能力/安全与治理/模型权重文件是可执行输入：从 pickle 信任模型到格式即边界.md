---
title: 模型权重文件是可执行输入：从 pickle 信任模型到格式即边界
type: playbook
status: active
updated: 2026-09-22
review_after: 2026-12-22
change_rate: medium
confidence: high
tags:
  - ai/platform
  - ai/security
  - ai/supply-chain
sources:
  - "https://github.com/huggingface/safetensors"
  - "https://docs.python.org/3/library/pickle.html"
  - "https://jfrog.com"
---

# 模型权重文件是可执行输入

## 核心要点

| 维度 | 回答 |
| --- | --- |
| 要解决的问题 | 模型文件被当作"被动数据"对待，但 pickle 基格式在加载时执行任意代码，依赖的信任模型与可执行文件相同。明确"格式即信任边界"才能把 AI 供应链治理贯穿到加载路径上。 |
| 本质 | `.pt/.pth/.bin/.ckpt` 文件本质是 pickle 字节流，内嵌可调用对象在 `torch.load()` 反序列化时执行；这属于文档化的设计行为，不算漏洞。 |
| 做法 | 加载侧：默认 safetensors，旧格式加载必须 `weights_only=True`，未验证文件在隔离环境加载；传播侧：发布仓库强制 safetensors，仓库扫描工具仅作辅助。 |
| 效果与代价 | 效果是攻击面按设计消除而非靠扫描缓解；代价是存量转换成本、多卡分片与自定义代码（`modeling_*.py`）仍需单独治理。 |
| 边界 | safetensors 只消除了"加载即执行"这条路径，不能证明权重未被投毒（行为篡改藏在数值里），自定义代码、adapter、数据集仍按可执行输入对待。 |
| 验证 | 拿一个旧格式文件用 `pickletools.dis` 看到可见的 GLOBAL/REDUCE 操作码；对比 safetensors 头部 JSON 与 raw bytes 结构；跑一次"恶意 pickle 反弹 shell"与"同名 safetensors 无代码路径"实验。 |

## 机制：pickle 虚拟机与 REDUCE 操作码

pickle 是一个基于栈的虚拟机（PVM），反序列化时按操作码流重建对象。核心风险操作码：

- **GLOBAL**：从任意模块导入可调用对象（如 `('subprocess', 'Popen')`）。
- **REDUCE**：从栈上弹出一个可调用对象和参数元组，**调用它**。`__reduce__` 方法返回 `(callable, args)`，unpickler 直接执行。
- **STACK_GLOBAL**：GLOBAL 的 2.x 高效变体，绕过部分只匹配 GLOBAL 的扫描器。

```python
# 生成一个加载即执行命令的 .bin 文件（仅演示，勿分发）
import pickle, subprocess

class Weaponized:
    def __reduce__(self):
        return (subprocess.Popen, ("touch /tmp/pwned", {"shell": True}))

with open("pytorch_model.bin", "wb") as f:
    pickle.dump(Weaponized(), f)
# 任何 torch.load("pytorch_model.bin") 都会在重建对象时执行该命令
```

这条路径不是漏洞：Python 官方文档明文写着 "The pickle module is not secure. Only unpickle data you trust."。PyTorch 的 `.pt/.pth/.bin/.ckpt` 底层就是 pickle，`torch.load()` 继承全部风险。JFrog 2024 年在 Hugging Face 扫出约 100 个含恶意代码执行模式的模型（goober2/baller13 嵌入反弹 shell 的 `__reduce__`，连回攻击者 C2）。

## 格式即边界：safetensors 的信任模型差异

safetensors 的安全主张不是"扫描掉恶意内容"，而是"让攻击无法表示"：

- 文件 = 8 字节头长度 + JSON 头（tensor 名、dtype、shape、字节区间）+ raw bytes。
- **格式里没有代码的概念**：没有操作码流、没有可调用对象、没有 import 路径。`__reduce__` 无法藏进一个"没有代码概念"的格式。
- 代价边界也要摆明：数值投毒（后门权重）照常可表示，格式安全不等于内容安全。

| 对比维度 | pickle 系（.pt/.pth/.bin/.ckpt） | safetensors |
| --- | --- | --- |
| 反序列化行为 | 执行任意 Python 代码 | 仅读取张量数据，无代码执行路径 |
| 信任模型 | 与可执行文件同级：只加载可信来源 | 与图像/文档同级：数据文件 |
| 调用链 | torch.load → pickle.load → PVM | load_file → mmap + JSON 解析 |
| 静态扫描可行性 | 本质不安全格式靠扫描缓解，扫描器可被绕过 | 无需扫描，攻击面按设计消除 |

与软件供应链的映射关系：pickle 系格式对应"安装脚本"（npm install 时的 preinstall hook，执行在你信任的进程里），GGUF 的 Jinja2 chat template 对应"软件包里带一个待渲染的模板"——llama.cpp 生态在模板引擎不沙箱时同样代码执行。这个映射的用途是举一反三：判断一个新格式安不安全，看它加载时有没有"调用任意可调用对象"的路径。

## 防线分层

| 层 | 动作 | 依据 |
| --- | --- | --- |
| 格式层 | 发布与加载默认 safetensors；存量分批转换 | 攻击面按设计消除 |
| 加载层 | 必须加载旧格式时 `torch.load(..., weights_only=True)`（PyTorch 2.6+ 默认）；未验证文件在隔离环境加载 | 缩小但非消除（CVE-2025-32434 曾绕过 weights_only） |
| 扫描层 | picklescan/fickling/ModelScan 做辅助筛子 | 扫描器本身有绕过漏洞（JFrog 2025 披露 3 个 zero-day），不能当主防线 |
| 运行层 | 加载环境网络隔离、行为监控（出站连接、进程派生、文件写） | 纵深防御，捕捉漏网载荷 |
| 溯源层 | 按仓库 commit hash 锁定 + SHA-256 校验 | 与 [[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/模型与数据供应链需要可验证来源]] 的发布者绑定互补 |

## 与既有文章的分工

[[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/依赖供应链需要锁定来源与构建输入]] 锁"物"的层面（版本/hash/签名/构建输入），[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/模型与数据供应链需要可验证来源]] 建立了模型供应链的输入清单，本篇下钻到**加载路径的格式层**：为什么 safetensors 之前的问题无法靠扫描修复，以及"格式即边界"的判断框架。

## 选读提示与验证

- **pickle 可视化**：`python -m pickletools.dis model.bin` 看 GLOBAL/REDUCE 操作码流。预期：能识别导入的可调用对象，包括 `subprocess`、`os.system` 等危险符号。
- **格式对比实验**：同一 state_dict 分别存为 `.bin` 与 `.safetensors`，hexdump 对比头部。预期：`.bin` 头部包含 pickle 操作码流；`.safetensors` 头部是纯 JSON + tensor 字节区间。
- **加载行为实验（隔离环境）**：生成武器化 `.bin` 在容器里 `torch.load`，观察预设的 touch 文件是否被创建。预期：文件被创建（证明加载即执行）；同一载荷无法用 safetensors 表示。

关系：[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/模型与数据供应链需要可验证来源]] · [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/依赖供应链需要锁定来源与构建输入]] · [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/维护者信任是供应链信任的地基：贡献者治理与维护者变更审计]] · [[工程知识/缺陷分析：从个案到体系/安全/案例四十四：投毒不是写错，是写给你看——依赖投毒的三个真实剧本]]