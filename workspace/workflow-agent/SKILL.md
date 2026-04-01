---
name: workflow-agent
description: Explains and packages the OpenClaw workflow agent architecture built around Gateway, Controller, Scheduler, Worker, WorkflowRuntime, and DSL primitives. Use when working on workflow routing, `@workflow`, `step()/parallel()/ask()`, Worker scheduling, classifier rules, hook escalation, iteration logic, or reproducing the new workflow engine.
platform: [openclaw]
---

# Workflow Agent

OpenClaw 当前的工作流引擎不是旧的 `modular-workflow` 架构，而是四角色主路径：

```text
Gateway -> Controller -> Scheduler -> Worker
```

兼容入口仍然保留在：

- `scripts/openclaw_task_bridge.py`
- `modules/orchestrator.py`

但真正的核心逻辑已经拆到 Controller、DSL Runtime、Scheduler、Worker 这几层。

## 何时使用

在这些场景优先使用本 skill：

- 新增或修改 `workflows/*.py`
- 调试 `RECEIVED -> CLASSIFIED -> PREPARING -> EXECUTING` 生命周期
- 调整 `config/classifier.yaml` 的分类规则和升级阈值
- 调整 `config/workers.yaml` 的标签、后端和容量
- 排查 `step()`、`parallel()`、`ask()` 的执行路径
- 扩展 `HookRunner`、`IterationStrategy`、`UserInteractor`
- 想把新版工作流引擎快速复刻到别的 OpenClaw 实例

## 快速定位

| 目标 | 看这里 |
|------|--------|
| 兼容入口 | `scripts/openclaw_task_bridge.py`, `modules/orchestrator.py` |
| 状态机主循环 | `modules/controller/reconciler.py` |
| 分类策略链 | `modules/controller/classifier.py` |
| 预执行钩子与失败决策 | `modules/controller/hook_runner.py` |
| 迭代回退逻辑 | `modules/controller/iteration_strategy.py` |
| 系统层决策升级 | `modules/controller/escalation.py` |
| 执行中用户交互 | `modules/controller/user_interactor.py`, `modules/dsl/primitives.py` |
| DSL 注册与原语 | `modules/dsl/registry.py`, `modules/dsl/primitives.py` |
| 运行时与中间件链 | `modules/dsl/runtime.py`, `modules/dsl/middleware.py` |
| 调度与 Worker 池 | `modules/scheduler/scheduler.py`, `modules/scheduler/worker_pool.py` |
| 单步执行与后端 | `modules/worker/worker.py`, `modules/worker/backends.py` |

## 架构地图

```text
Gateway
  -> TaskController
  -> Reconciler
     -> Classifier
     -> HookRunner
     -> WorkflowRuntime
        -> step()/parallel()/ask()
        -> Scheduler
        -> WorkerPool / Worker
  -> Gateway.deliver()
```

旁路系统：

- `modules/observer/observer.py`
- `modules/observer/breaker.py`
- `modules/infra/event_bus.py`

## 生命周期规则

任务阶段：

```text
RECEIVED -> CLASSIFIED -> PREPARING -> EXECUTING -> DELIVERED
                                      \-> FAILED
                                      \-> CANCELLED
```

判断该改哪层时，用这张映射：

- 输入适配、交付失败重试：`Gateway`
- 选工作流、问不问用户确认：`Controller`
- 选哪个 Worker 执行某个步骤：`Scheduler`
- 具体命令执行、错误分类：`Worker`
- 工作流作者定义的步骤结构：`workflows/*.py` + DSL

## 新增工作流

1. 在 `workflows/` 下新增文件，使用 `@workflow()` 注册。
2. 在工作流函数中优先用 `step()`、`parallel()`、`ask()` 组合步骤。
3. 如果要被自动分类命中，更新 `config/classifier.yaml`。
4. 如果步骤依赖新能力，更新 `config/workers.yaml` 的 `labels` 和 `backend`。
5. 如果需要系统层确认，使用 `interaction_mode="adaptive"` 或 `interaction_mode="confirm"`。

示例：

```python
from modules.dsl.primitives import ask, step
from modules.dsl.registry import workflow


@workflow("my-workflow", timeout=300, interaction_mode="adaptive")
async def my_workflow(ctx):
    plan = await step("任务规划", ctx.task)
    choice = await ask(
        "确认方案",
        "是否继续执行当前方案？",
        options=["继续", "停止"],
        default="继续",
    )
    if choice != "继续":
        return "用户终止执行"
    result = await step("执行任务", plan.output, mcp=["file", "bash"])
    return result.output
```

## 配置要点

### `config/classifier.yaml`

- `rules`: 关键词到工作流的映射
- `instant_threshold`: 短文本直答阈值
- `confirmation_mode`: 全局系统层决策模式
- `iteration.reclassify_threshold`: 自动重分类阈值
- `escalation.*`: 分类、迭代、钩子失败的升级阈值和超时

### `config/workers.yaml`

- `backend`: `mini-agent` / `llm-direct` / `claude-code`
- `labels`: 调度匹配的能力标签，例如 `mcp.file`, `mcp.bash`, `review`
- `capacity`: 单个 Worker 并发容量

## 中间件与失败处理

默认中间件顺序：

```text
Cancellation -> Event -> Idempotency -> Retry
```

错误分类：

- `TRANSIENT`: 自动重试
- `PERMANENT`: 立即失败
- `DEGRADABLE`: 非必需步骤允许降级

如果是系统自己在做决策，改 `Controller`。
如果是工作流作者希望在执行中和用户交互，改 `ask()`。

## 注意事项

- `interaction_mode` 只控制系统层决策，不控制 DSL 里的 `ask()`
- `CommandStrategy` 仍然把旧命令 `/miniagent` 映射到 `general` 工作流
- `scripts/openclaw_task_bridge.py` 保留旧 API，但实际运行链路已经是新架构
- `modules/orchestrator.py` 是装配层，排查行为问题时不要只看它，要继续往下看 `Reconciler`、`WorkflowRuntime`、`Scheduler`、`Worker`
- 复刻时优先使用本目录附带的 `openclaw-workflow-scripts.tar.gz`

## 附带内容

- 经验文档：`kb/openclaw/workflow-agent-architecture.md`
- 复刻压缩包：`skills/workflow-agent/openclaw-workflow-scripts.tar.gz`
- 简介文档：`skills/workflow-agent/README.md`
