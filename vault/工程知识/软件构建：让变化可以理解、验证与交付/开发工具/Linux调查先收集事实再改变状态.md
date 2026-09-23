---
title: Linux 调查先收集事实再改变状态
type: reference
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: high
tags:
  - linux/operations
  - software/debugging
  - security/operations
sources:
  - "https://man7.org/linux/man-pages/index.html"
  - "[[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/系统指标与观测]]"
  - "https://www.brendangregg.com/linuxperf.html"
---

# Linux 调查先收集事实再改变状态

命令的价值来自调查问题，而不是数量。运行前确认主机/容器、用户、cwd、目标路径、时间窗口和权限；任何删除、杀进程、改配置和抓包都先做只读检查。

## 要解决的问题：为什么先收集事实再改变状态（机制）

| 问题 | 首选 | 关注 |
| --- | --- | --- |
| 文件/内容在哪 | `find`, `rg`, `stat`, `du` | 路径范围、权限、挂载点 |
| 哪个进程在运行 | `ps`, `pgrep`, `pstree`, `systemctl` | PID 复用、父子树、启动时间 |
| 谁占用文件/端口 | `lsof`, `fuser`, `ss` | namespace、权限、监听/连接状态 |
| 日志发生了什么 | `journalctl`, `less`, `tail`, `rg` | 时区、轮转、request/task ID |
| 资源为什么慢 | `vmstat`, `pidstat`, `mpstat`, `iostat` | 队列、尾延迟、采样间隔 |
| 网络在哪断 | `getent`, `curl`, `ss`, `ip`, `mtr`, `tcpdump` | DNS/TLS/代理/权限/隐私 |
| 文件何时变化 | `inotifywait`, audit/event source | watcher 丢事件、递归、轮转 |

## 文件与文本

```bash
rg -n 'pattern' /explicit/path
find /explicit/path -type f -mtime -1 -print
du -xhd1 /explicit/path | sort -h
stat /explicit/path/file
```

`rg` 适合内容搜索；`find` 适合按元数据筛选。处理包含空格/换行的文件名时使用 `-print0` 和支持 NUL 的消费者。不要用 `cat file | grep` 代替 `rg/grep file`，也不要让未校验变量展开为 `/`、home 或工作区根目录。

## 进程与服务

```bash
ps -eo pid,ppid,lstart,stat,%cpu,%mem,args --sort=-%cpu
pstree -ap <pid>
cat /proc/<pid>/status
ls -l /proc/<pid>/fd
systemctl status <unit>
journalctl -u <unit> --since '2026-08-31 10:00:00'
```

停止前验证 PID 的命令、启动时间、cwd 和 owner；优先让服务管理器执行 stop。单杀父 PID 可能留下子孙进程，详见 [[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理]]。

## 网络

```bash
getent hosts example.com
curl -v --connect-timeout 3 --max-time 10 https://example.com/health
ss -lntp
ip -s link
```

`ping` 失败不能证明 TCP/HTTP 不可达，很多网络会过滤 ICMP；`curl` 成功也只证明该 URL、身份和时间点。抓包可能包含凭据和业务数据，限制接口、host、时间和文件权限。

## 性能快照

```bash
uptime
vmstat 1 5
pidstat -dur 1 5
mpstat -P ALL 1 5
iostat -xz 1 5
```

这些命令提供入口，不给出根因。把采样和用户请求、trace、应用队列对齐，再进入 [[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/系统指标与观测]] 和具体 CPU/内存/I/O/网络页面。

## 破坏性操作门禁

执行删除、权限变更、kill、iptables/nft、mount、sysctl 前：

1. 用只读命令解析精确目标并打印；
2. 确认当前 namespace、host、用户和 cwd；
3. 备份配置/创建恢复点，写明回滚；
4. 对单个目标试运行，观察指标；
5. 记录命令、退出码、stdout/stderr 和变更后验证。

不要在未展开的变量、宽泛 glob 或符号链接边界不清时运行递归操作。优先使用可恢复的移动/隔离，而不是直接删除。

## Shell 管道正确性

- 引号保护变量：`"$value"`；参数用数组而不是拼接命令字符串。
- 管道失败可能被最后一个命令掩盖；脚本按环境使用 `set -euo pipefail`，同时理解其边界并显式处理预期失败。
- 使用 `--` 分隔选项和文件名，避免以 `-` 开头的路径被解释为参数。
- 命令输出不是稳定 API；自动化优先 JSON/结构化格式或 `/proc`/正式接口，并做 schema 校验。

关联：[[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/后台任务不能依赖终端会话维持生命周期]]、[[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能问题定位]]、[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论]]、[[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/本地复现环境是修线上问题的第一现场]]、[[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/静态分析在门禁里定位为证据生成器]]。

文件何时变化这一项的下钻：[[工程知识/缺陷分析：从个案到体系/资源与容量/文件监视器数量失控：递归监听与上限裁剪]] —— 监听类工具本身的开销也要收进观测清单。

## 效果与代价

先看事实的收益是动作命中率高（一次调查定位问题，反复试错的命令与时间省下来），代价是多花几分钟读状态（ps、ss、lsof 的输出）；改变状态后再查事实的代价不对称——回退困难的环境（改了挂载、杀了进程、清了缓存）里，几分钟的前置观察省掉的是小时级的恢复。

