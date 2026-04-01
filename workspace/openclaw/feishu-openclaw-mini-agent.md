# 飞书机器人打通 OpenClaw 和 Mini-Agent 全流程

## 症状

在实现飞书机器人自动调用 Mini-Agent 执行任务时遇到以下问题：
1. 不知道如何让飞书 Bot 发送的任务交给 Mini-Agent 处理
2. OpenClaw 无法识别新配置的 MCP 服务器
3. MCP 服务器创建后无法正常被 OpenClaw 调用
4. Mini-Agent 命令行参数不熟悉，无法正确调用
5. MCP 服务器显示 offline，无法启动

关键词：飞书机器人, Feishu Bot, OpenClaw, Mini-Agent, MCP, mcporter, 任务自动化, 消息转发, mini-agent-executor, Rate limit

## 原因

1. **架构理解不清**: 不理解飞书 Bot、OpenClaw、Mini-Agent 三者之间的调用关系和数据流
2. **配置路径错误**: 误以为 MCP 配置应该放在 `~/.openclaw/config/mcporter.json`，实际上应该是 `~/.mcporter/mcporter.json`
3. **MCP 依赖缺失**: MCP 服务器需要 Python 依赖（mcp, pydantic），未安装会导致服务器无法启动
4. **MCP 服务器未启动**: mini-agent-executor 需要手动启动或确保 mcporter 能自动管理
5. **测试方法不当**: 使用命令行直接调用而不是通过 MCP 协议进行测试

## 解决方案

### 1. 理解架构关系

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   飞书用户   │────▶│   OpenClaw  │────▶│  Mini-Agent │
│  (发送任务)  │     │  (任务路由)  │     │  (任务执行)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

- **飞书 Bot**: 通过 OpenClaw 内置的飞书集成自动接收消息
- **OpenClaw**: 负责消息路由、MCP 工具管理、Agent 调度
- **Mini-Agent**: 通过 MCP 工具被调用，执行实际任务

### 2. 确认飞书 Bot 已配置

```bash
openclaw status
```

配置 `~/.openclaw/openclaw.json`：
```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxxxxxxxxxxxx",
      "appSecret": "xxxxxxxxxxxxxxxx"
    }
  }
}
```

### 3. 安装 MCP Python 依赖

```bash
pip install mcp pydantic --break-system-packages
```

### 4. 创建 Mini-Agent MCP 服务器

创建 `~/.openclaw/mcp-servers/mini-agent-mcp/server.py`：
```python
#!/usr/bin/env python3
"""Mini-Agent MCP Server - Execute tasks using Mini-Agent AI assistant"""

import json
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl
import asyncio

app = Server("mini-agent-executor")

@app.list_tools()
async def list_tools() -> list:
    """List available tools"""
    return [
        {
            "name": "execute_mini_agent_task",
            "description": "Execute a task using Mini-Agent AI assistant. Mini-Agent can handle complex tasks including file operations, code execution, and MCP tool interactions.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The task description for Mini-Agent to execute. Be specific about what you want accomplished."},
                    "workspace": {"type": "string", "description": "Working directory for Mini-Agent (default: /home/lkx)", "default": "/home/lkx"},
                    "timeout": {"type": "number", "description": "Timeout in seconds (default: 600)", "default": 600}
                },
                "required": ["task"]
            }
        },
        {
            "name": "get_mini_agent_status",
            "description": "Check if Mini-Agent is available and running",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workspace": {"type": "string", "description": "Working directory to check (default: /home/lkx)", "default": "/home/lkx"}
                }
            }
        }
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Execute a tool call"""
    if name == "execute_mini_agent_task":
        task = arguments.get("task")
        workspace = arguments.get("workspace", "/home/lkx")
        timeout = arguments.get("timeout", 600)
        
        cmd = [
            "npx", "mcporter", "call", "mini-agent-executor.execute_mini_agent_task",
            f"task={task}",
            f"workspace={workspace}",
            f"timeout={timeout}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr
    
    elif name == "get_mini_agent_status":
        return "Mini-Agent MCP server is running"
    
    return "Unknown tool"

async def main():
    await app.run(stdio_server, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

### 5. 配置 MCP 服务器

**关键：必须放在 `~/.mcporter/mcporter.json`**

```json
{
  "mcpServers": {
    "mini-agent-executor": {
      "command": "python3",
      "args": ["/home/lkx/.openclaw/mcp-servers/mini-agent-mcp/server.py"],
      "env": {},
      "description": "Execute tasks using Mini-Agent AI assistant"
    }
  }
}
```

### 6. 验证与测试

```bash
# 查看 MCP 服务器状态
npx mcporter list

# 应该看到：
# - mini-agent-executor — Execute tasks using Mini-Agent AI assistant (2 tools, 0.3s)

# 测试调用
npx mcporter call mini-agent-executor.execute_mini_agent_task task="列出 /home/lkx 目录下的文件" workspace="/home/lkx" timeout=60

# 检查状态
npx mcporter call mini-agent-executor.get_mini_agent_status
```

### 7. 通过飞书调用

飞书发送任务给机器人 → OpenClaw 接收 → 通过 mcporter 调用 mini-agent-executor → Mini-Agent 执行任务 → 结果返回

```bash
# 间接调用方式（当前可用）
npx mcporter call mini-agent-executor.execute_mini_agent_task task="你的任务" workspace="/home/lkx" timeout=60
```

## 环境

- OpenClaw 版本: 2026.2.26
- MCP 版本: 1.26.0
- Mini-Agent 版本: 0.1.0
- Node.js: 24.x
- Python: 3.12+
- OS: Linux (Ubuntu 24.04)

## 贡献者

刘康欣, 2026-02-28
