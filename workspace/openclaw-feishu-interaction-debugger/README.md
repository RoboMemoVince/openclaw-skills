# OpenClaw Feishu Interaction Debugger

用于排查 OpenClaw 工作流和飞书之间的交互闭环问题，特别是：

- 交互请求发出去了，但用户回复没有唤醒 `submit_response()`
- 群聊任务状态/结果跑到了私聊，而不是原群 thread

## 背景与目标

OpenClaw 的 Feishu 工作流交互问题通常会混在一起：

1. 平台层发不出去
2. Python bridge 收不到回复
3. thread 索引或机器头没命中
4. 群聊回包路径选错

这个 skill 的目标是把问题拆成“出站 vs 入站”两半，并用最短路径定位卡点。

## 适用场景

- `request_input()` / `request_decision()` 等待超时
- 飞书里明明回复了，工作流还是拿到 `None`
- 群任务消息错误地发到私聊
- 想确认问题到底在 `openclaw message send`、Feishu 权限，还是 Python bridge

## 快速开始

1. 先读 `SKILL.md` 的诊断流程。
2. 先验证三条真实发送：
   - 私聊直发
   - 群消息
   - 群 thread reply
3. 再看诊断文件：

```text
~/.openclaw/data/feishu_inbound_trace.jsonl
```

4. 按 `ws_event_received -> parse_message_event_ok -> interceptor_* -> submit_interaction_response_*` 这条链定位卡点。

## 关键文件

- `scripts/feishu_message_receiver.py`
- `scripts/feishu_bot_server.py`
- `modules/controller/interaction_interceptor.py`
- `modules/controller/feishu_gateway_notifier.py`
- `modules/orchestrator.py`

## 注意事项

- 先验证出站，再验证入站，不要一上来就改 `submit_response()`
- 群聊回包优先回原群 thread，不要默认私聊 `open_id`
- 如果诊断文件完全没有新增记录，问题基本不在 Python 拦截逻辑里

## 维护人

lkx, 2026-03-09
