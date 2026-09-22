---
title: Linux常用命令的词源地图
type: reference
status: core
status_note: 词源系列核心参考
updated: 2026-09-29
confidence: high
change_rate: low
review_after: 2028-09-22
tags:
  - vocabulary
  - terms/etymology
  - linux/shell
sources:
  - "https://www.gnu.org/software/coreutils/manual/"
  - "https://en.wikipedia.org/wiki/List_of_Unix_commands"
  - "https://man7.org/linux/man-pages/man1/chmod.1.html"
  - "https://en.wikipedia.org/wiki/Unix"
  - "https://en.wikipedia.org/wiki/Pdp-7"
---

# Linux常用命令的词源地图

`ls` 是 list，`mv` 是 move，`awk` 是三个作者姓氏首字母——Linux 命令名是有来历的。要解决的问题：把常用命令的缩写来历、参数短名的原始英文单词讲清楚，新人不需要背"咒语"，靠词源就能把命令行连成体系。

## 机制：按构词逻辑分四类

命令名与参数短名的缩写策略可以分成四类，分清类别后大部分"神秘短名"都能自己猜出来：

| 类别 | 代表命令 | 构词逻辑 | 说明 |
| --- | --- | --- | --- |
| 动词缩写 | cp、mv、rm、ln、mkdir | 取动词首部：copy、move、remove、link、make directory | 最直觉的一类 |
| 名词短语缩写 | ls、ps、df、du、id | list、process status、disk free、disk usage、identity | 信息展示类命令 |
| 跨工具家族共享词 | grep、sed、awk | 全称或姓氏缩写：globally search a regular expression and print、stream editor、Aho Weinberger Kernighan | 文本三剑客各有来历 |
| 参数血统差异 | ps aux vs ps -ef | BSD 无横线无横线血统 vs System V 横线血统 | 同功能两套参数的根源 |

参数短名的词源表（只列难词，all/force 这类自解释词不列）：

| 参数 | 原始单词 | 为什么是这个短名 | 常见命令 |
| --- | --- | --- | --- |
| -v | verbose | 啰嗦模式：输出更多细节 | grep/tar/mv/cp |
| -v | version | 打印版本号 | gcc/python/node |
| -h | human-readable | 数字带 K/M/G 单位 | ls/df/du |
| -h | help | 打印帮助 | 大部分 GNU 工具 |
| -n | numeric | 不做名字解析（显示数字） | netstat/ss/top |
| -n | no-clobber | 不覆盖已有文件 | cp/mv |
| -r / -R | recursive | 递归处理目录 | cp/rm/chmod |
| -f | follow / force | 跟随符号链接 / 强制执行 | ls -f vs rm -f 语义不同 |
| -i | interactive | 逐个确认 | rm -i/cp -i |
| -p | preserve / parents | 保留属性 / 连父目录一起建 | cp -p/mkdir -p |
| -u | user / update | 按用户过滤 / 只复制更新的 | ps -u/cp -u |
| -t | tag / target | 打标签 / 指定目标 | git tag -t/rsync -t |
| -x | extract / exclude | 解包 / 排除 | tar -x/rsync -x |
| -a | all / append | 全部 / 追加 | ls -a/tee -a |
| -b | block-size / buffer | 块大小 / 缓冲区 | dd/du -b |
| -c | command / count | 执行命令 / 计数 | sh -c/head -c |
| -l | long / list / login | 长格式 / 列表 / 登录 shell | ls -l/crontab -l/bash -l |
| -s | silent / size / summary | 静默 / 大小 / 拜讨 | curl -s/du -s |
| -w | wait / width | 等待 / 宽度 | fsck -w/column -t |

## 年代与血统：哪些是遗留、哪些是演进

| 命令/参数 | 出生年代 | 状态 | 门道 |
| --- | --- | --- | --- |
| ls/cp/mv 等核心缩写 | 1969-1971（PDP-7/PDP-11 时代） | 标准 | 打字机时代省按键的缩写传统，POSIX 定为标准 |
| ps aux vs ps -ef | BSD（1978+）与 System V（1983+）双血统 | 遗留 | 两套参数同功能并存，是 Unix 分裂史的活化石 |
| -v verbose / -v version 双义 | 1970s 起 | 遗留 | 短名空间耗尽后各自认领，无标准可协调 |
| --verbose 长参数 | GNU（1983+） | 标准 | 长名自解释，是 GNU 对打字机时代的纠偏 |
| tar -x 磁带词源 | v7 Unix（1979）磁带时代 | 遗留 | 名字停在磁带时代，功能早已是通用归档 |
| ss vs netstat | ss（2001，iproute2） | 演进 | netstat 的继任者，更快更现代的 socket 视图 |
| lsof | 1994 | 标准 | 排查"谁开着这个文件"的事实收集标准件 |
| GNU coreutils 家族 | 2002 整合 | 标准 | --force/--verbose 全家族一致的长参数纪律 |

收益与代价：词源讲清后，新工具的参数可以"按家族猜"（GNU 家族的 --verbose/--force 全家族一致）；年代与状态分档把"哪些要背（遗留）哪些能推（标准）"划开，学习成本从死记降到分类记忆。代价：血统差异（BSD vs System V）造成的同义参数分裂是永久记忆负担，没有逻辑只有历史，接受它。这份地图的取舍：只收高频与难词，all/force/list 这类自解释词不收，完整覆盖交给 man 手册。

## 思想背景与看完能判断什么

短名经济的来路：1970 年代终端是电传打字机，80 列 24 行，每敲一个字符都是真成本，两三字母缩写是那个约束下的最优解。GNU 长名是对这份遗产的反思：脚本要被人读，可读性比敲键数重要——这个判断在今天依然成立，它是"给机器省成本"与"给人省成本"两种价值观的分界。看到这里，看任何一个工具的参数设计，都能判断它站在哪边、为什么。

- 手上的活是排查线上问题：这表里的难词（-n、-h、-i）大多是观测与安全词，知道词源就能跨工具迁移（ss -n 与 netstat -n 同义）。
- 手上的活是写脚本：优先长参数，血统短名（-v 双义类）在脚本里是隐患，宁可敲长。
- 手上的活是给团队定规范：GNU 家族的长参数纪律（全家族一致）是可以直接抄的范本，血统遗留参数写成对照表放进团队 wiki。
- 想借鉴设计：tar 的"名字停在磁带时代"是警示——词汇一旦定型就很难改，命名时把当下技术当永久词源是包袱（今天用 yaml 命名的工具十年后会面临同样尴尬）。

## 验证

```bash
# 验证血统差异：同一台 Linux 上两套 ps 参数都活
ps aux | head -3
ps -ewf | head -3
# 验证 -h 双义：同一家族内也分裂
ls -h / df -h / du -h | head -3
```
预期：ps aux 与 ps -ef 输出同内容不同格式（血统共存证据）；-h 在 ls/df/du 全族都是 human-readable（家族内一致性证据）。数字对不上（某命令 -h 打印帮助）时查它的 --help，确认它属于哪个家族血统。

## 边界

本篇是 Linux 侧词源明细。方法论总纲（三层词汇结构、长短双轨的来历）见 [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/词汇即接口：Linux与容器命令的词源与设计.md|词汇即接口：Linux与容器命令的词源与设计]]。容器侧词汇（docker/kubectl 的动词集）见 [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/Docker与K8s词汇的设计逻辑.md|Docker与K8s词汇的设计逻辑]]。这些命令穿过的 shell 机制（管道、重定向）见 [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/Linux调查先收集事实再改变状态.md|Linux调查先收集事实再改变状态]]。

## 相关

- [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/词汇即接口：Linux与容器命令的词源与设计.md|词汇即接口：Linux与容器命令的词源与设计]]——方法论总纲
- [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/Docker与K8s词汇的设计逻辑.md|Docker与K8s词汇的设计逻辑]]——容器侧对照
