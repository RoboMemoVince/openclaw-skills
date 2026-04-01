---
name: repo-explorer
description: 深度探索和分析开源代码仓库。帮助用户理解项目架构、阅读源码、解释核心概念。支持 GitHub URL 或本地仓库路径。当用户想要了解某个开源项目、需要代码阅读指南、想理解项目架构或实现细节时使用此 skill。关键词：探索仓库、分析项目、阅读指南、理解代码、项目架构。
tools: Read, Glob, Grep, Bash, WebFetch, WebSearch
platform: [openclaw, claude-code]
---

# Repo Explorer - 代码仓库深度探索工具

帮助用户深入理解开源代码仓库，提供架构分析、代码阅读指南和核心概念解释。

## 输出语言规范

- **解释说明**: 使用中文
- **代码和技术术语**: 保持英文原文
- **文件路径和命令**: 保持原文
- **引用格式**: `文件路径:行号`

## 触发条件

当用户出现以下情况时激活此 skill：

1. 提供 GitHub URL 并想了解该项目
2. 询问某个开源项目的架构或实现
3. 需要代码阅读指南或学习路线
4. 想深入理解特定模块、函数或设计模式
5. 使用关键词："探索仓库"、"分析项目"、"阅读指南"、"理解代码"

## 核心工作流程

### Phase 1: 项目获取与识别

#### 1.1 获取仓库

**GitHub URL 输入：**

```bash
# 克隆仓库到当前项目目录下的 ./repo-explorer/
REPO_DIR="./repo-explorer/$(basename "${GITHUB_URL%.git}")"
mkdir -p "$(dirname "$REPO_DIR")"

if [ ! -d "$REPO_DIR" ]; then
    git clone --depth 50 "$GITHUB_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
```

**本地路径输入：**
- 直接使用用户提供的路径
- 验证路径是否为有效的 git 仓库或项目目录

#### 1.2 识别项目类型

使用 Glob 检测项目类型：

| 文件 | 项目类型 |
|------|----------|
| `package.json` | Node.js / JavaScript |
| `pyproject.toml` / `setup.py` / `requirements.txt` | Python |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `pom.xml` / `build.gradle` | Java |
| `*.csproj` | .NET / C# |
| `Gemfile` | Ruby |
| `mix.exs` | Elixir |

详细模式参考 [references/analysis-patterns.md](references/analysis-patterns.md)

### Phase 2: 项目概览分析

#### 2.1 读取关键文档

按优先级读取：

1. `README.md` / `README` - 项目介绍
2. `CONTRIBUTING.md` - 贡献指南（了解开发流程）
3. `docs/` 目录 - 详细文档
4. `ARCHITECTURE.md` / `DESIGN.md` - 架构文档
5. `CHANGELOG.md` - 版本历史

#### 2.2 分析目录结构

```bash
# 快速了解项目结构（排除常见的依赖目录）
find . -type d -maxdepth 3 \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/vendor/*" \
    -not -path "*/target/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.venv/*" | head -50
```

或使用辅助脚本：

```bash
bash ~/.claude/skills/repo-explorer/scripts/repo-stats.sh
```

#### 2.3 生成项目概览报告

输出格式参考 [references/output-templates.md](references/output-templates.md)

**必须包含：**

- 项目名称和简介
- 技术栈和主要依赖
- 目录结构说明
- 核心模块概述
- 入口点位置

### Phase 3: 深度分析

根据用户需求提供以下分析：

#### 3.1 架构分析

参考 [references/architecture-guide.md](references/architecture-guide.md)

- 识别架构模式（分层、微服务、插件、事件驱动等）
- 分析模块依赖关系
- 绘制数据流图（使用 ASCII 字符）
- 识别核心抽象和接口

#### 3.2 代码阅读指南

为用户提供推荐的阅读顺序：

```markdown
## 推荐阅读顺序

### 第一阶段：了解入口和核心
1. `src/index.ts` - 应用入口点
2. `src/core/app.ts` - 核心应用类
3. `src/types/index.ts` - 核心类型定义

### 第二阶段：理解核心机制
4. `src/router/index.ts` - 路由机制
5. `src/middleware/` - 中间件系统

### 第三阶段：深入具体功能
6. 根据兴趣选择具体模块...
```

#### 3.3 关键概念解释

当遇到复杂概念时：

1. **先搜索项目文档** - 使用 Grep 在 docs/ 和 README 中查找解释
2. **分析代码实现** - 定位相关代码并解释
3. **搜索背景知识** - 使用 WebSearch 查找算法、设计模式等背景
4. **关联官方文档** - 使用 WebFetch 获取依赖库的官方文档

#### 3.4 使用指南生成

- 安装和环境配置步骤
- 基本使用示例
- 常见配置选项
- 扩展和插件开发方法

### Phase 4: 交互式探索

支持用户追问和深入探索：

#### 4.1 定位特定实现

当用户问"X 是怎么实现的？"：

```bash
# 搜索函数/类定义
rg "function\s+functionName|class\s+ClassName|def\s+functionName" --type-add 'code:*.{ts,js,py,go,rs}'

# 搜索接口和类型
rg "interface\s+TypeName|type\s+TypeName" --type ts
```

#### 4.2 追踪调用链

1. 找到目标函数定义
2. 搜索调用点：`rg "functionName\("`
3. 分析调用上下文
4. 绘制调用关系图

#### 4.3 解释代码片段

当解释具体代码时，必须：

1. 引用具体的 `文件路径:行号`
2. 解释代码的目的和作用
3. 说明与其他模块的关系
4. 指出关键的设计决策

## 输出格式规范

### 项目概览报告

```markdown
# [项目名] 项目分析报告

## 基本信息

| 属性 | 值 |
|------|-----|
| 项目类型 | Node.js / TypeScript |
| 主要框架 | Express.js |
| 仓库地址 | https://github.com/... |

## 项目简介

[从 README 提取的项目描述]

## 技术栈

- **运行时**: Node.js 18+
- **语言**: TypeScript 5.x
- **框架**: Express.js 4.x
- **数据库**: PostgreSQL + Prisma

## 目录结构

```
project/
├── src/
│   ├── index.ts          # 应用入口
│   ├── routes/           # API 路由定义
│   ├── services/         # 业务逻辑层
│   ├── models/           # 数据模型
│   └── utils/            # 工具函数
├── tests/                # 测试文件
└── docs/                 # 文档
```

## 核心模块

### [模块名]
- **位置**: `src/core/module.ts`
- **职责**: [模块功能描述]
- **关键类/函数**: `ClassName`, `functionName()`

## 入口点

应用从 `src/index.ts:15` 开始执行...

## 推荐阅读顺序

1. ...
2. ...
```

### 架构图示例

```
┌─────────────────────────────────────────────────┐
│                   Application                    │
├─────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ Router  │──│Middleware│──│ Handler │         │
│  └────┬────┘  └─────────┘  └────┬────┘         │
│       │                         │               │
│  ┌────▼────────────────────────▼────┐          │
│  │           Service Layer           │          │
│  └────────────────┬─────────────────┘          │
│                   │                             │
│  ┌────────────────▼─────────────────┐          │
│  │           Data Layer              │          │
│  └───────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

## 常见项目类型分析要点

### Node.js / JavaScript 项目

- 查看 `package.json` 的 `main`、`bin`、`scripts`
- 检查 `src/index.js` 或 `lib/index.js`
- 分析 `exports` 字段了解公开 API

### Python 项目

- 查看 `pyproject.toml` 或 `setup.py` 的入口点
- 检查 `__main__.py` 和 `__init__.py`
- 分析 `console_scripts` 了解 CLI 工具

### Rust 项目

- 查看 `Cargo.toml` 的 `[bin]` 和 `[lib]`
- 检查 `src/main.rs` 或 `src/lib.rs`
- 分析 `pub` 导出了解公开 API

### Go 项目

- 查看 `go.mod` 了解模块名
- 检查 `main.go` 或 `cmd/` 目录
- 分析 `internal/` 和 `pkg/` 结构

## 错误处理

### 仓库克隆失败

- 检查 URL 是否正确
- 检查网络连接
- 尝试使用 `--depth 1` 浅克隆

### 项目类型无法识别

- 提示用户项目使用的技术栈
- 手动分析目录结构
- 查找常见的入口文件

### 文件过大无法读取

- 使用 `head` 或 `Read` 的 `limit` 参数只读取部分
- 优先读取文件开头的导入和类型定义
- 使用 Grep 定位特定代码段

## 参考资料

- [analysis-patterns.md](references/analysis-patterns.md) - 项目类型识别和分析模式
- [architecture-guide.md](references/architecture-guide.md) - 架构分析详细指南
- [output-templates.md](references/output-templates.md) - 中文输出模板
- [project-overview-example.md](examples/project-overview-example.md) - 完整分析示例
