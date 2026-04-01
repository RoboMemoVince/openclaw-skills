# Workflow Agent

OpenClaw 新版工作流代理架构打包。

这个目录对应的是当前实现中的四角色主路径：

```text
Gateway -> Controller -> Scheduler -> Worker
```

而不是旧的 `modular-workflow` 文档里那套 `ModuleBase -> ModuleRegistry -> Orchestrator` 说明。

## 内容

- `SKILL.md`：新版工作流架构的使用入口
- `openclaw-workflow-scripts.tar.gz`：快速复刻所需源码、配置和文档压缩包

## 适用场景

- 想新增或修改 `workflows/*.py`
- 想理解 `step()` / `parallel()` / `ask()` 执行链
- 想调整 `Classifier`、`HookRunner`、`IterationStrategy`
- 想扩展 Worker 后端、标签和调度逻辑
- 想把这套工作流架构快速复制到另一台 OpenClaw

## 快速开始

1. 先阅读 `SKILL.md` 了解架构分层和关键入口。
2. 解压压缩包：

```bash
tar -xzf openclaw-workflow-scripts.tar.gz
```

3. 优先阅读这些文件：

- `docs/WORKFLOW_DESIGN.md`
- `modules/orchestrator.py`
- `modules/controller/reconciler.py`
- `modules/dsl/primitives.py`
- `modules/dsl/runtime.py`
- `modules/scheduler/scheduler.py`
- `modules/worker/worker.py`

## 覆盖关系

本目录用于补充并覆盖旧的工作流说明：

- 旧 kb：`kb/openclaw/modular-workflow-guide.md`
- 旧 skill：`skills/modular-workflow/`

旧内容可以继续作为历史参考，但不再适合作为当前架构主入口。
