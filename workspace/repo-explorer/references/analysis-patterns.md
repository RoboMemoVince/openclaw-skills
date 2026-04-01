# 代码分析模式参考

## 项目类型识别

### 检测文件优先级

按以下顺序检测项目类型：

```bash
# 检测脚本
check_project_type() {
    if [ -f "package.json" ]; then echo "nodejs"; fi
    if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then echo "python"; fi
    if [ -f "Cargo.toml" ]; then echo "rust"; fi
    if [ -f "go.mod" ]; then echo "go"; fi
    if [ -f "pom.xml" ] || [ -f "build.gradle" ]; then echo "java"; fi
    if ls *.csproj 1>/dev/null 2>&1; then echo "dotnet"; fi
    if [ -f "Gemfile" ]; then echo "ruby"; fi
    if [ -f "mix.exs" ]; then echo "elixir"; fi
    if [ -f "composer.json" ]; then echo "php"; fi
    if [ -f "CMakeLists.txt" ]; then echo "cpp"; fi
}
```

### 各语言详细识别模式

#### Node.js / JavaScript / TypeScript

| 特征文件 | 说明 |
|----------|------|
| `package.json` | 主项目配置 |
| `tsconfig.json` | TypeScript 项目 |
| `webpack.config.js` | 使用 Webpack 打包 |
| `vite.config.js` | 使用 Vite 打包 |
| `.babelrc` | 使用 Babel 转译 |
| `next.config.js` | Next.js 项目 |
| `nuxt.config.js` | Nuxt.js 项目 |

**框架识别：**

```json
// package.json dependencies 关键词
{
  "react": "React 项目",
  "vue": "Vue 项目",
  "angular": "Angular 项目",
  "express": "Express 后端",
  "fastify": "Fastify 后端",
  "nestjs": "NestJS 后端",
  "next": "Next.js 全栈",
  "nuxt": "Nuxt.js 全栈"
}
```

#### Python

| 特征文件 | 说明 |
|----------|------|
| `pyproject.toml` | 现代 Python 项目配置 |
| `setup.py` | 传统安装脚本 |
| `setup.cfg` | 传统配置文件 |
| `requirements.txt` | 依赖列表 |
| `Pipfile` | Pipenv 管理 |
| `poetry.lock` | Poetry 管理 |
| `tox.ini` | 测试配置 |
| `pytest.ini` | Pytest 配置 |

**框架识别：**

```python
# 依赖关键词
{
    "django": "Django Web 框架",
    "flask": "Flask 微框架",
    "fastapi": "FastAPI 异步框架",
    "starlette": "Starlette ASGI 框架",
    "tornado": "Tornado 异步框架",
    "celery": "Celery 任务队列",
    "sqlalchemy": "SQLAlchemy ORM",
    "pytorch": "PyTorch 深度学习",
    "tensorflow": "TensorFlow 深度学习"
}
```

#### Rust

| 特征文件 | 说明 |
|----------|------|
| `Cargo.toml` | 项目配置 |
| `Cargo.lock` | 依赖锁定 |
| `rust-toolchain.toml` | 工具链配置 |
| `.cargo/config.toml` | Cargo 配置 |

**项目类型：**

```toml
# Cargo.toml 结构
[lib]        # 库项目
[[bin]]      # 可执行项目
[workspace]  # 工作空间（多包项目）
```

#### Go

| 特征文件 | 说明 |
|----------|------|
| `go.mod` | 模块定义 |
| `go.sum` | 依赖校验 |
| `Makefile` | 构建脚本 |

**目录结构识别：**

```
/cmd/           # 命令入口（多个可执行文件）
/internal/      # 内部包（不对外暴露）
/pkg/           # 公开包
/api/           # API 定义（protobuf, OpenAPI）
/web/           # Web 资源
```

#### Java

| 特征文件 | 说明 |
|----------|------|
| `pom.xml` | Maven 项目 |
| `build.gradle` | Gradle 项目 |
| `build.gradle.kts` | Gradle Kotlin DSL |
| `mvnw` / `gradlew` | 包装器脚本 |

**框架识别：**

```xml
<!-- pom.xml dependencies -->
spring-boot: Spring Boot 项目
spring-cloud: 微服务项目
quarkus: Quarkus 项目
micronaut: Micronaut 项目
```

## 架构模式识别

### 分层架构 (Layered Architecture)

**特征目录结构：**

```
src/
├── controllers/    # 或 handlers/, routes/
├── services/       # 或 business/, domain/
├── repositories/   # 或 data/, dao/
├── models/         # 或 entities/
└── utils/          # 或 helpers/, common/
```

**识别要点：**
- 清晰的层级划分
- 依赖方向单一（上层依赖下层）
- 每层有明确职责

### 微服务架构 (Microservices)

**特征目录结构：**

```
/
├── services/
│   ├── user-service/
│   ├── order-service/
│   └── payment-service/
├── gateway/
├── shared/
└── docker-compose.yml
```

**识别要点：**
- 多个独立服务目录
- 每个服务有自己的依赖配置
- 存在服务发现/网关配置
- Docker/K8s 编排文件

### 插件架构 (Plugin Architecture)

**特征目录结构：**

```
src/
├── core/           # 核心系统
├── plugins/        # 插件目录
│   ├── plugin-a/
│   └── plugin-b/
└── plugin-api/     # 插件接口定义
```

**识别要点：**
- 核心与插件分离
- 存在插件接口/抽象
- 动态加载机制
- 插件有统一结构

### 事件驱动架构 (Event-Driven)

**代码特征搜索：**

```bash
# 搜索事件相关代码
rg "EventEmitter|on\(|emit\(|subscribe|publish|dispatch"
rg "MessageQueue|RabbitMQ|Kafka|Redis.*pub"
```

**识别要点：**
- 事件总线/消息队列
- 发布-订阅模式
- 异步处理
- 事件处理器

### 六边形架构 (Hexagonal / Ports & Adapters)

**特征目录结构：**

```
src/
├── domain/          # 领域模型（核心业务）
├── application/     # 应用服务（用例）
├── ports/           # 端口（接口定义）
│   ├── inbound/     # 入站端口
│   └── outbound/    # 出站端口
└── adapters/        # 适配器（接口实现）
    ├── primary/     # 主适配器（HTTP, CLI）
    └── secondary/   # 次适配器（DB, 外部 API）
```

**识别要点：**
- 领域核心与基础设施分离
- 依赖倒置原则
- 端口和适配器明确分离

## 核心代码定位策略

### 找入口点

```bash
# Node.js
cat package.json | jq '.main, .bin, .scripts.start'

# Python
grep -r "if __name__" --include="*.py" | head -5
cat pyproject.toml | grep "scripts\|entry"

# Rust
cat Cargo.toml | grep -A5 "\[\[bin\]\]"
ls src/main.rs src/bin/ 2>/dev/null

# Go
find . -name "main.go" -type f | head -5

# Java (Spring Boot)
rg "@SpringBootApplication" --type java
```

### 找核心抽象

```bash
# 接口定义
rg "^(export )?(interface|abstract class|trait|protocol)" --type-add 'code:*.{ts,java,go,rs,swift}'

# 基类
rg "^(export )?class.*extends" --type-add 'code:*.{ts,java}'
rg "^class.*\(.*\):" --type py  # Python 继承
```

### 找配置中心

```bash
# 配置文件
find . -name "config.*" -o -name "*.config.*" -o -name "settings.*" | head -20

# 环境变量使用
rg "process\.env\.|os\.environ|env::"
```

## 常见设计模式识别

### 单例模式 (Singleton)

```bash
rg "getInstance|_instance|shared\s*="
rg "private\s+(static\s+)?constructor"
```

### 工厂模式 (Factory)

```bash
rg "Factory|create[A-Z]|new[A-Z]"
rg "switch.*case.*return new"
```

### 观察者模式 (Observer)

```bash
rg "addObserver|removeObserver|notify|subscribe|unsubscribe"
rg "on\(['\"]|addEventListener|emit\("
```

### 策略模式 (Strategy)

```bash
rg "Strategy|setStrategy|execute\("
# 通常伴随接口和多个实现类
```

### 装饰器模式 (Decorator)

```bash
rg "@\w+|decorator|Decorator"
rg "wrap|Wrapper|enhance"
```

### 依赖注入 (Dependency Injection)

```bash
# 构造函数注入
rg "constructor\(.*private|@Inject|@Autowired"
# 容器
rg "Container|Injector|Provider|resolve\("
```

## 代码质量快速评估

### 测试覆盖

```bash
# 测试文件比例
find . -name "*.test.*" -o -name "*_test.*" -o -name "test_*" | wc -l
find . -name "*.ts" -o -name "*.js" -o -name "*.py" | wc -l
```

### 文档覆盖

```bash
# 文档文件
find . -name "*.md" -o -name "*.rst" | wc -l
# JSDoc/docstring
rg "/\*\*|'''" --type-add 'code:*.{ts,js,py}' | wc -l
```

### 代码复杂度指标

```bash
# 文件行数分布
find . -name "*.ts" -exec wc -l {} \; | sort -n | tail -10

# 长函数（可能需要重构）
rg "^(export )?(async )?function" -A 100 | head -200
```
