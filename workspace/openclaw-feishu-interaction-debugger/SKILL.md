---
name: openclaw-feishu-interaction-debugger
description: Diagnoses OpenClaw workflow interaction problems on Feishu when request_input/request_decision messages are sent successfully but user replies do not wake submit_response(), or when group task status/results are routed to DM instead of the original group thread. Use when debugging Feishu thread reply, Python bridge inbound events, sender_type filtering, thread indexes, or group thread delivery.
platform: [openclaw]
---

# OpenClaw Feishu Interaction Debugger

Use this skill to debug the **full interaction loop** between OpenClaw workflows and Feishu:

- outbound interaction request
- user reply
- Python bridge inbound event
- `InteractionInterceptor`
- `submit_response()`
- group-thread vs DM result delivery

## 何时使用

- `StateBackedUserInteractor.request_input()` / `request_decision()` 发出了消息，但一直超时
- 用户明明在飞书里回复了，工作流还是拿到 `None`
- 群聊任务的“处理中 / 完成 / 失败”跑到了私聊，而不是原群 thread
- 你想确认问题在“发不出去”还是“收不到回复”

## 何时不用

- 单纯读写飞书文档、云盘、知识库：用 `feishu-doc` / `feishu-drive` / `feishu-wiki`
- 只想发一条普通飞书消息，不涉及工作流交互闭环

## 核心判断原则

先把问题拆成两半：

1. **出站是否成功**
2. **入站是否进入 Python bridge**

不要在没验证出站之前就改 `submit_response()`，也不要在没验证入站之前就改 thread 索引。

## 快速诊断流程

### 第 1 步：验证凭证和平台层发送

先验证 Feishu token 能拿到，再验证 3 条真实发送链：

```bash
# 私聊直发
openclaw message send --channel feishu --target user:<open_id> --message "直发测试" --json

# 群消息
openclaw message send --channel feishu --target chat:<chat_id> --message "群聊测试" --json

# 群 thread reply
openclaw message send --channel feishu --target chat:<chat_id> \
  --reply-to <root_message_id> --thread-id <root_message_id> \
  --message "thread reply 测试" --json
```

如果这三条都成功，说明：

- `openclaw message send`
- 平台层 `@openclaw/feishu`
- Feishu 凭证

这些都不是主问题。

### 第 2 步：看诊断文件

优先读：

```text
~/.openclaw/data/feishu_inbound_trace.jsonl
```

重点看这些 stage：

- `ws_event_received`
- `parse_message_event_ok`
- `bot_message_parsed`
- `bot_interceptor_hit`
- `bot_interceptor_miss`
- `interceptor_thread_index_hit`
- `interceptor_parent_header_hit`
- `submit_interaction_response_success`
- `submit_interaction_response_reject`

### 第 3 步：按现象分流

#### 情况 A：没有任何新 trace

说明用户回复**根本没进入** Python WebSocket 链。

优先检查：

- 飞书 app 事件订阅/权限
- 这条 Python bridge 是否真的收得到回复类消息
- 是否需要把交互回复识别迁到平台层 `@openclaw/feishu`

#### 情况 B：有 `ws_event_received`，但没有 `parse_message_event_ok`

说明 Python 接收器解析就挂了。

优先检查：

- `msg_type` vs `message_type`
- `root_id` / `parent_id` / `thread_id`
- `sender_type`

#### 情况 C：有 `parse_message_event_ok`，但只有 `bot_interceptor_miss`

说明入站进入了 Python，但没命中交互识别。

优先检查：

- thread 索引是否写入成功
- `chat_id + root_id/thread_id` 是否与发送时一致
- `parent_id` 对应的父消息内容能否读到机器头

#### 情况 D：有 `submit_interaction_response_reject`

看 reject reason：

- `request_missing`
- `response_already_exists`
- `envelope_missing`
- `sender_mismatch`

最常见是：

- 线程索引指向旧 task
- 用户不是任务发起人
- request 已超时后被清理

## 群聊回包规则

群聊不要直接按 `open_id` 私聊回包。

应该统一走上下文回包函数：

```python
send_context_message(
    user_id,
    metadata={"chat_id", "chat_type", "root_id", "thread_id"},
    text="...",
    fallback_text="..."
)
```

优先级：

1. `chat_type == "group"` 且有 `chat_id + root_id/thread_id` → 回原群 thread
2. 失败 → DM fallback
3. 私聊场景 → 直接发 `open_id`

## 关键文件

- `scripts/feishu_message_receiver.py`
- `scripts/feishu_bot_server.py`
- `modules/controller/interaction_interceptor.py`
- `modules/controller/feishu_gateway_notifier.py`
- `modules/controller/user_interactor.py`
- `modules/orchestrator.py`
- `scripts/openclaw_task_bridge.py`
- `~/.openclaw/data/feishu_inbound_trace.jsonl`

## 注意事项

- `sender_type != "user"` 的消息要优先忽略，否则机器人自己发的消息可能会被自己吞成新任务
- 群 thread 联调时，根消息 ID、thread anchor、`chat_id` 必须一致
- 如果出站真实可用但入站永远没有 trace，别继续在 Python 里猜，优先查飞书事件是否根本没送到这条链

## 关联经验

- `kb/openclaw/feishu-interaction-reply-missed-in-python-bridge.md`
