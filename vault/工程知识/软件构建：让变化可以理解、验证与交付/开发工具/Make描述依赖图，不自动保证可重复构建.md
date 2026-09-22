---
title: Make 描述依赖图，不自动保证可重复构建
type: reference
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: stable
confidence: high
tags:
  - build/make
  - software/automation
sources:
  - "https://www.gnu.org/software/make/manual/make.html"
---

# Make 描述依赖图，不自动保证可重复构建

Make 的本质是根据目标、依赖与时间戳构建有向无环图，只重建过期目标。它适合把本地常用命令变成稳定入口，但不能自动提供 hermetic build、依赖锁定或跨平台一致性。

## 基本模型

```make
target: prerequisites
	recipe
```

recipe 行默认必须以 Tab 开头。目标文件不存在，或任一 prerequisite 比目标新时，recipe 执行。

```make
.PHONY: test clean

PYTHON ?= python3

test:
	$(PYTHON) -m pytest

clean:
	$(RM) -r build .pytest_cache
```

`.PHONY` 防止同名文件让命令目标意外跳过；`?=` 允许调用方覆盖，`:=` 立即展开，`=` 递归展开。变量引用使用 `$(NAME)`。

## 正确使用边界

- 目标应可重复执行，尽量从声明的输入生成声明的输出。
- recipe 每行默认由独立 shell 执行；需要共享 shell 状态时写在同一行或显式使用 `.ONESHELL` 并理解错误语义。
- shell 变量用 `$$name`，因为 `$` 先被 Make 解释。
- 并行 `make -j` 要求依赖图真实完整；缺失依赖会产生偶发竞态。
- 删除目标只写明确的构建产物路径；不使用未验证变量、宽泛 glob 或工作区根目录。
- 语言自己的构建工具（Cargo/Gradle/npm 等）仍是事实来源，Make 作为统一入口而非重写其依赖模型。

## 常用模式

```make
BUILD_DIR := build
SOURCES := $(wildcard src/*.c)
OBJECTS := $(patsubst src/%.c,$(BUILD_DIR)/%.o,$(SOURCES))

app: $(OBJECTS)
	$(CC) $(LDFLAGS) $^ -o $@

$(BUILD_DIR)/%.o: src/%.c
	@mkdir -p $(@D)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@
```

自动变量：`$@` 当前目标，`$<` 第一个 prerequisite，`$^` 所有去重 prerequisites，`$(@D)` 目标目录。

## 可重复构建还需要什么

Make 只决定执行顺序。要获得可信构建，还需：

- 锁定编译器、运行时、依赖和镜像；
- 明确环境变量、网络和缓存输入；
- 生成物携带源码 revision 和构建元数据；
- CI 与本地使用同一入口；
- 缓存键包含全部影响输出的输入；
- 测试真实执行而不是只打印命令。

## 调试与验收

```bash
make -n target       # 预览，不执行
make --warn-undefined-variables target
make -j4 target
```

- [ ] clean checkout 可构建，增量构建与全量结果一致。
- [ ] `-j` 并行没有偶发失败。
- [ ] `clean` 只删除可重建产物。
- [ ] recipe 失败能返回非零状态，不被管道或多命令掩盖。
- [ ] 构建输出可绑定 revision、工具链和依赖锁。

关联：[[工程知识/软件构建：让变化可以理解、验证与交付/软件构建：让变化可以理解、验证与交付]]、[[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/测试策略从风险选择证据]]、[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论]]。
