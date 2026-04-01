# 架构分析指南

## 架构分析流程

### Step 1: 鸟瞰视图

首先获取项目整体结构：

```bash
# 获取顶层目录结构
ls -la

# 获取源码目录结构（限制深度）
find . -type d -maxdepth 3 \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/vendor/*" \
    -not -path "*/target/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.venv/*" \
    -not -path "*/dist/*" \
    -not -path "*/build/*"
```

### Step 2: 识别边界

**找入口点：**

```bash
# 命令行入口
rg "if __name__|func main\(\)|fn main\(\)" --type-add 'code:*.{py,go,rs}'

# HTTP 入口
rg "app\.(listen|run)|createServer|http\.Server"

# 导出的 API
rg "^export|module\.exports|pub fn|pub struct"
```

**找配置边界：**

```bash
# 环境变量
rg "process\.env\.|os\.getenv|env::|os\.environ"

# 配置文件加载
rg "config|settings|\.env" --type-add 'code:*.{ts,js,py,go,rs}'
```

### Step 3: 追踪数据流

**HTTP 请求流：**

```
Request → Router → Middleware → Controller → Service → Repository → Database
                                    ↓
Response ← Formatter ← Service Response ← Query Result
```

**分析方法：**

1. 找路由定义：`rg "router\.|app\.(get|post|put|delete)|@(Get|Post)"`
2. 追踪 handler：找到路由对应的处理函数
3. 分析业务逻辑：handler 调用了哪些 service
4. 检查数据访问：service 如何访问数据库

### Step 4: 理解模块关系

**导入分析：**

```bash
# JavaScript/TypeScript
rg "^import.*from" --type ts | awk -F'from' '{print $2}' | sort | uniq -c | sort -rn | head -20

# Python
rg "^from.*import|^import" --type py | sort | uniq -c | sort -rn | head -20

# Go
rg "^\s+\"" --type go | sort | uniq -c | sort -rn | head -20
```

**依赖方向分析：**

检查是否遵循依赖倒置原则：
- 高层模块不应依赖低层模块
- 抽象不应依赖细节

```bash
# 检查 domain/core 是否依赖 infrastructure
rg "import.*infrastructure|from.*database|require.*db" src/domain/ src/core/
```

## 依赖关系分析方法

### 模块依赖图

使用以下模式绘制 ASCII 依赖图：

```
模块 A ──depends on──▶ 模块 B
         │
         └──▶ 模块 C ──▶ 模块 D
```

**绘制原则：**

1. 核心模块放中间
2. 依赖箭头从依赖方指向被依赖方
3. 循环依赖用双向箭头标记（需重构）

### 依赖类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 编译依赖 | 编译时需要 | import, require |
| 运行时依赖 | 运行时需要 | 动态加载、插件 |
| 可选依赖 | 增强功能 | peer dependencies |
| 开发依赖 | 仅开发时 | devDependencies |

### 循环依赖检测

```bash
# 检测可能的循环依赖
# 模块 A import B，同时 B import A

# 先列出所有导入关系，然后分析
rg "^import|^from.*import" --type py -l | while read f; do
    echo "=== $f ==="
    rg "^import|^from.*import" "$f"
done
```

## 数据流追踪技术

### 追踪单个请求

1. **找入口**：路由定义
2. **追踪 handler**：处理函数
3. **分析调用链**：service → repository → database
4. **检查响应**：数据如何返回

### 状态管理分析

**前端状态流：**

```
User Action → Action Creator → Reducer → Store → Component Update
                    ↓
              Side Effect (API Call) → Action
```

**后端状态：**

```
Request → Session/Auth Check → Business Logic → Database Transaction → Response
              ↓                                        ↓
         Cache Check                            Cache Invalidation
```

### 事件流分析

```bash
# 找事件定义
rg "emit\(|publish\(|dispatch\("

# 找事件处理
rg "on\(|subscribe\(|addEventListener"
```

**绘制事件流图：**

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Producer  │──────▶│  Event Bus  │──────▶│  Consumer   │
│             │ emit  │             │ on    │             │
└─────────────┘       └─────────────┘       └─────────────┘
                            │
                            ▼
                    ┌─────────────┐
                    │  Consumer 2 │
                    └─────────────┘
```

## 架构文档模板

### 架构概览

```markdown
# [项目名] 架构文档

## 架构风格

[项目采用的架构风格，如：分层架构、微服务、事件驱动等]

## 系统上下文

```
                    ┌─────────────────┐
                    │   External API  │
                    └────────┬────────┘
                             │
┌──────────┐        ┌────────▼────────┐        ┌──────────┐
│  Client  │◀──────▶│     System      │◀──────▶│ Database │
└──────────┘        └─────────────────┘        └──────────┘
```

## 模块划分

| 模块 | 职责 | 位置 |
|------|------|------|
| Core | 核心业务逻辑 | `src/core/` |
| API | HTTP 接口 | `src/api/` |
| Data | 数据访问 | `src/data/` |

## 数据流

[描述主要数据流向]

## 关键设计决策

### 决策 1: [决策名称]

- **问题**: [要解决的问题]
- **决策**: [采取的方案]
- **原因**: [选择该方案的理由]
- **后果**: [该决策带来的影响]

## 部署架构

[描述如何部署，包括容器、负载均衡等]
```

### 模块详细设计

```markdown
# [模块名] 设计文档

## 概述

[模块的职责和边界]

## 接口

### 公开 API

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `methodName()` | `param: Type` | `ReturnType` | 方法说明 |

### 事件

| 事件名 | 数据 | 触发时机 |
|--------|------|----------|
| `eventName` | `{...}` | 何时触发 |

## 内部结构

```
模块/
├── index.ts      # 公开导出
├── service.ts    # 核心逻辑
├── types.ts      # 类型定义
└── utils.ts      # 工具函数
```

## 依赖

- **依赖模块 A**: 用途说明
- **依赖模块 B**: 用途说明

## 测试策略

- 单元测试覆盖核心逻辑
- 集成测试覆盖外部交互
```

## 常见架构问题诊断

### 问题 1: 循环依赖

**症状：**
- 编译错误
- 初始化顺序问题
- 模块难以独立测试

**诊断方法：**

```bash
# 分析导入关系
rg "^import|^from.*import" --type py | grep -E "(module_a.*module_b|module_b.*module_a)"
```

**解决方向：**
- 提取公共依赖到新模块
- 使用依赖注入
- 使用接口隔离

### 问题 2: 大泥球 (Big Ball of Mud)

**症状：**
- 单个文件/类过大（>500 行）
- 职责不清晰
- 到处都有依赖

**诊断方法：**

```bash
# 找大文件
find . -name "*.ts" -exec wc -l {} \; | sort -rn | head -10

# 找高扇入/扇出
rg "import.*from" --type ts | awk -F':' '{print $1}' | sort | uniq -c | sort -rn | head -10
```

### 问题 3: 不必要的复杂性

**症状：**
- 过度抽象
- 过多的间接层
- 简单功能需要理解大量代码

**诊断方法：**
- 追踪一个简单请求需要经过多少层
- 检查抽象是否有多个实现（如果只有一个，可能过度设计）

### 问题 4: 紧耦合

**症状：**
- 修改一处影响多处
- 难以独立测试
- 难以替换组件

**诊断方法：**

```bash
# 检查具体类型的直接使用
rg "new ConcreteClass|ConcreteClass\(" --type ts
# 应该使用接口/抽象
```
