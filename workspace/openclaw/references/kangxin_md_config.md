# 康欣 OpenClaw 工作流 MD 配置文件

## 症状
需要备份/迁移 OpenClaw 工作流配置时，不知道哪些 MD 文件是必需的，也不清楚每个文件的具体内容

## 原因
OpenClaw 工作流涉及多个 MD 文件，分散在根目录和 skills/ 目录，内容各不相同

## 解决方案
本文档汇总 OpenClaw 工作流所需的所有 MD 文件，并附带每个文件的完整内容，供备份/迁移使用

---

## 文件清单

### 根目录 MD 文件（9个）

| 文件 | 说明 |
|------|------|
| INDEX.md | 工作流总入口、文件关系图、快速索引 |
| SOUL.md | 行为准则、技术规则、执行规范 |
| USER.md | 用户信息（康欣的基础信息） |
| MEMORY.md | 长期经验积累、快速索引 |
| IDENTITY.md | 身份索引、快速入口 |
| AGENTS.md | 工作手册、会话流程 |
| PROJECTS.md | 项目汇总（相亲App、Skills） |
| HEARTBEAT.md | 定期任务配置 |
| TOOLS.md | 工具本地配置 |

### skills/ 技能 MD 文件（6个）

| 技能 | 文件 |
|------|------|
| competitor-analysis | SKILL.md |
| market-research | SKILL.md, competitor-analysis.md, validation.md |
| paper-recommendation | SKILL.md, WORKFLOW.md |

---

## 各文件详细内容

### 1. INDEX.md - 工作流索引

**路径**: `~/.openclaw/workspace/INDEX.md`

**核心内容**:
- 文件关系图：INDEX 为总入口，连接 SOUL、USER、AGENTS、MEMORY、PROJECTS、TOOLS、HEARTBEAT
- 快速索引表：8 个需求场景对应的查阅文件
- 核心工作流：每次会话必读顺序（SOUL→USER→memory→MEMORY）
- 触发任务表：智囊库同步、项目状态更新、对话日志优化、MD文件优化、自我反思、飞书API配额检查
- 引用规范：文档内引用格式、锚点命名规范
- 更新原则：索引优先、单一职责、避免重复、锚点稳定

---

### 2. SOUL.md - 行为准则

**路径**: `~/.openclaw/workspace/SOUL.md`

**核心内容**:
- 核心观点：做一个真正有用的 AI 助手，而非表演式助手
- 金字塔结构：行为准则、执行规范、技术规则、根本原则
- 行为准则（9条）：真正有帮助、始终验证修复、要有观点、先自己想办法、用能力赢得信任、记得记录修复、规则添加遵循结构化思维、每日结构化复习、定期自我反思
- 风格定位：做一个你愿意与之交谈的助手、需要简洁时简洁、不是公司职员
- 边界规则：私人事务保持私密、有疑问先问清楚、不发送半生不熟的回复、群聊中谨言慎行
- 连续性：每次会话 fresh 醒来，读取并更新记忆文件
- 知识管理：整理格式（一个文件一个问题）、上传位置（memory/team-kb/）、定期更新
- 执行规范：飞书任务执行脚本、智囊库上传流程（5步）、确认变更规则
- 技术规则：MiniMax MCP（驼峰命名）、飞书API配额保护（channelHealthCheckMinutes、probe.ts 缓存配置）、Skill Creator 目录结构
- 根本原则：记住你是客人，尊重用户隐私

---

### 3. USER.md - 用户信息

**路径**: `~/.openclaw/workspace/USER.md`

**核心内容**:
- Name: 刘康欣
- What to call them: 康欣
- Pronouns: 他
- Timezone: 北京时区 (UTC+8)
- Notes: 学习使用 agent 的小白，关注如何用 AI 工具赋能
- 上下文：正在学习 OpenClaw 和 AI Agent 的使用，对 AI 工具赋能感兴趣，适合从基础开始讲解，耐心指导

---

### 4. MEMORY.md - 长期记忆

**路径**: `~/.openclaw/workspace/MEMORY.md`

**核心内容**:
- 快速索引表：12 条经验索引（minimax mcp、飞书 api 配额、飞书插件重复加载、相亲 app、飞书集成、智囊库、git 验证、mini-agent 任务分发、上下文传递、同步汇报、MD 文件优化、自动测试闭环）
- 经验写作模板：标题、症状、原因、解决方案、环境、贡献者
- 工具使用：MiniMax MCP 配置和报错处理、OpenClaw Feishu 插件重复加载
- 项目经验：相亲偏好评估 App、飞书→OpenClaw→Mini-Agent 全流程
- 仓库管理：智囊库仓库管理规范、Git 推送后验证
- 流程规范：任务处理优先用 mini-agent、调用 mini-agent 时传递完整上下文、智囊库同步自动汇报规则、MD 文件优化流程、添加或更新可测试目标时自动测试
- 团队知识库索引：8 条 openclaw 相关经验索引

---

### 5. IDENTITY.md - 身份索引

**路径**: `~/.openclaw/workspace/IDENTITY.md`

**核心内容**:
- 快速入口表：8 个类别的详情位置（用户信息、行为准则、技术规则、执行规范、项目信息、经验积累、工作流程、工具配置）
- 身份信息：角色定位为"真正有用的 AI 助手，而非表演式助手"，符号为 🦞，设定日期为 2026-02-28
- 索引优先原则：本文件遵循"索引优先"原则，所有详细内容引用外部文档

---

### 6. AGENTS.md - 工作手册

**路径**: `~/.openclaw/workspace/AGENTS.md`

**核心内容**:
- 会话流程（每次必读 4 步）：SOUL.md → USER.md → memory/YYYY-MM-DD.md → MEMORY.md
- 记忆系统：日常笔记位置、用途、核心准则
- 交互规范：
  - 外部操作 vs 内部操作（读取/探索/学习自由，发送邮件/推文需先问用户）
  - 群聊规范（何时发言、保持沉默的场景）
  - 表情使用（👍😂🤔✅等使用场景）
- 工具与任务：工具使用（详见 TOOLS.md）、心跳任务（详见 HEARTBEAT.md）
- 项目管理：项目索引流程（自动读取 PROJECTS.md、判断意图、自动进入项目目录）
- 知识管理：存放位置（memory/team-kb/）、内容（团队共享踩坑记录）、检索规则（报错/异常等问题必须先 memory_search）
- 安全规范：永不泄露私人数据、不随意执行破坏性命令、有疑问就问
- 结构原则：详见 SOUL.md 金字塔结构

---

### 7. PROJECTS.md - 项目汇总

**路径**: `~/.openclaw/workspace/PROJECTS.md`

**核心内容**:
- 快速索引表：相亲偏好评估 App（开发中）、竞品分析技能、市场研究技能、论文推荐技能
- 核心项目 - 相亲偏好评估 App：
  - 项目类型：AI 驱动的婚恋偏好评估工具
  - 核心功能：AI 识别 + 动态偏好学习，从文本/图片中提取信息，评估相亲对象匹配度
  - 技术栈：Python FastAPI + React
  - 已实现功能：文本信息提取 (15+ 维度)、图片识别 (人脸 + 年龄/颜值)、偏好学习引擎、多维度评分引擎、网页爬取框架
  - 待完成：二狗相亲 App 抓包接入（高优先级）、完善前端界面、用户系统
  - 关键文档：4 个方案文档路径
- 技能库：competitor-analysis（竞品研究）、market-research（商业机会评估）、paper-recommendation（学术研究辅助）

---

### 8. HEARTBEAT.md - 定期任务

**路径**: `~/.openclaw/workspace/HEARTBEAT.md`

**核心内容**:
- 快速索引表：6 个任务（智囊库同步、项目状态更新、对话日志优化、MD文件结构优化、自我反思、飞书API配额检查）
- 日常任务（每天）：
  - 智囊库同步：每天 00:00，git pull 并汇报新增经验
  - 项目状态更新：每天 00:00，按项目列出已完成/进行中/待开始
  - 对话日志优化：每天 01:00，优化前一天日志并提取关键信息
- 手动任务（用户触发）：MD 文件结构优化，读取所有 MD 文件检查重复/冲突/优化
- 周期任务（每周）：自我反思与成长记录，每周日 23:00
- 事件任务（触发式）：飞书 API 配额保护检查，每次开启 Gateway 时执行

---

### 9. TOOLS.md - 工具配置

**路径**: `~/.openclaw/workspace/TOOLS.md`

**核心内容**:
- 快速索引：MCP 服务、飞书配置、技能目录、项目路径、关键脚本
- MCP 服务：MiniMax MCP 配置文件路径（~/.mcporter/mcporter.json）
- 飞书配置：凭证位置（~/.openclaw/openclaw.json）、OpenClaw 内置 feishu 插件
- 技能目录：个人技能（~/.openclaw/skills/）、团队技能（memory/team-kb/）
- 项目路径：工作空间、相亲偏好 App、智囊库
- 关键脚本：飞书任务执行脚本路径

---

### 10. competitor-analysis/SKILL.md

**路径**: `~/.openclaw/workspace/skills/competitor-analysis/SKILL.md`

**核心内容**:
- 功能：竞争对手 SEO/GEO 分析，包括关键词排名、内容策略、反向链接、AI 引用模式
- 使用场景：新市场进入、内容策略规划、竞品排名分析、寻找外链机会、识别内容缺口、竞品 AI 引用分析
- 数据来源：SEO 工具、Analytics、AI 监控，或用户手动提供
- 分析步骤：
  1. 竞争对手识别（直接/间接/内容竞争对手）
  2. 收集竞争对手数据（基本信息、商业模式、流量估算）
  3. 关键词排名分析（Top 10/Top 3、搜索量、流量预估、关键词缺口）
  4. 内容策略审计（内容数量、性能、主题分布、成功因素）
  5. 反向链接分析（链接数量、域名评级、链接类型、链接资产）
  6. 技术 SEO 评估（Core Web Vitals、网站结构、内部链接）
  7. GEO/AI 引用分析（AI 可见性、引用策略、机会识别）
  8. 合成竞争情报（执行摘要、竞争格局、优劣势、机会、行动计划）
- 验证检查点：输入验证（竞争对手相关性、范围定义）、输出验证（数据支撑、可执行性）
- 高级分析类型：内容缺口分析、链接交叉、SERP 特征分析、历史跟踪
- 消息比较框架：消息矩阵、叙事分析框架、价值主张比较
- 定位策略框架：定位图（2x2 矩阵）、定位声明反向工程
- 竞争战斗卡模板：概述、他们的宣传、优势、弱点、差异化、异议处理、埋设地雷、胜负主题

---

### 11. market-research/SKILL.md

**路径**: `~/.openclaw/workspace/skills/market-research/SKILL.md`

**核心内容**:
- 核心框架：在做任何研究之前先澄清问题，明确具体可行动的指标
- 市场估算：
  - 自下而上：客户数 × 价格 × 频率
  - 自上而下：TAM → SAM → SOM
  - 可比法：竞品收入 × 市场份额估算
  - 免费数据源：政府人口普查、行业协会、公共公司文件、Statista 免费层、Google Trends、LinkedIn
- 竞争对手分析：映射景观、直接/间接/潜在竞争对手、挖掘评论（G2/Capterra/App Store）、跟踪信号（招聘/定价/功能发布）、评估护城河
- 客户验证：构建前与 20+ 潜在客户交谈，使用 Jobs-to-be-Done 或 Mom Test 框架
- 强信号：意向书、预付款、等待名单转化、重复使用
- 弱信号："我会用这个"、"好主意"、调查热情、社交媒体点赞
- 常见陷阱：确认偏差、幸存者偏差、过时来源、虚荣指标
- 边界：不能提供投资建议、不能保证、市场预测是概率性的

---

### 12. market-research/competitor-analysis.md

**路径**: `~/.openclaw/workspace/skills/market-research/competitor-analysis.md`

**核心内容**:
- 景观映射：直接 vs 间接 vs 潜在竞争对手
- 定位矩阵：价格 vs 功能、企业 vs SMB、垂直 vs 水平、简单 vs 复杂
- 评论挖掘：B2B SaaS（G2/Capterra/TrustRadius）、消费应用（App Store/Play Store）、实体产品（Amazon）、服务（Yelp/Google Reviews）
- 提取内容：重复投诉、功能请求、使用模式、切换触发因素
- 竞争情报来源：
  - 公共信息：10-K/10-QCrunchbase、招聘公告、产品发布变化
  - 合规情报：公共文件、定价页面、用户评论、会议演讲、开源贡献
- 特征比较矩阵：功能对比、优先级（Must-have/Differentiator/Nice-to-have）
- 市场份额估算：基于流量、员工数、融资、应用下载

---

### 13. market-research/validation.md

**路径**: `~/.openclaw/workspace/skills/market-research/validation.md`

**核心内容**:
- 构建前验证：
  - Mom Test 问题：避免引导性问题，获取过去行为事实
  - Jobs-to-be-Done 框架：情况 → 动机 → 结果
  - 寻找访谈对象：Cold outreach（LinkedIn/Twitter/行业 Slack）、Warm introductions
- 验证信号：
  - 强信号：客户付款/花时间帮助/介绍他人/描述问题
  - 弱信号："我会用"/"好主意"/调查热情/社交媒体关注
- 调查设计：
  - 问题类型：筛选/行为/偏好/开放式
  - 样本量：95% 置信度 ±5% 需要 ~400 响应
  - 常见错误：引导问题、双重问题、社会期望偏差、问题过多
- 定价研究：
  - Van Westendorp 方法：太贵/有点贵/便宜/太便宜
  - 支付意愿访谈：如果产品存在你愿意付多少钱？2x 呢？
  - 竞争定价分析：定价模型、入门/中端/企业价格

---

### 14. paper-recommendation/SKILL.md

**路径**: `~/.openclaw/workspace/skills/paper-recommendation/SKILL.md`

**核心内容**:
- 概述：自动发现、深度阅读、生成简报 - AI 论文研究助手
- 功能：自动论文发现（arXiv）、并行审阅、子代理生成、结构化输出、每日自动化
- 脚本：
  - fetch_papers.py：获取 arXiv 论文，可选下载 PDF
  - review_papers.py：生成子代理并行审阅任务
  - read_pdf.py：提取 PDF 文本
- 工作流：获取论文 → 审阅 → 生成子代理任务 → 并行审阅 → 收集评论 → 生成简报 → 交付
- 标准简报格式：论文信息（标题/作者/机构/arXiv/PDF/日期/分类）、摘要（中文翻译）、核心贡献、主要结论、实验结果、Jarvis 笔记（评分/推荐度/研究方向/重要性）
- 每日工作流：每天 10:00 AM 自动执行
- 字段规则：机构必须是真实机构名、摘要必须中文完整翻译、实验结果必须有、每个字段必填
- 关键规则：永远遵循标准简报格式，不要偏离

---

### 15. paper-recommendation/WORKFLOW.md

**路径**: `~/.openclaw/workspace/skills/paper-recommendation/WORKFLOW.md`

**核心内容**:
- 完整工作流：用户请求 → 获取论文 → 审阅 → 生成子代理任务 → 并行审阅 → Jarvis 审阅 → 生成简报 → 交付
- 步骤详情：
  1. 获取论文：python3 fetch_papers.py --download --json
  2. Jarvis 审阅：检查论文列表，选择要发送审阅的论文
  3. 生成子代理任务：python3 review_papers.py --papers '<json>' --json
  4. 并行审阅：为每篇论文生成子代理，读取 arXiv HTML 输出 JSON 评分
  5. Jarvis 最终审阅：选择标准 score >= 4 AND recommended == yes
  6. 生成简报：获取 arXiv HTML，提取机构、中文摘要等，遵循标准格式
  7. 交付：通过 Telegram 发送
- 快速参考命令：每一步的完整命令行
- 常见问题与解决方案：缺失机构/不完整摘要/缺失实验/API 失败/JSON 解析错误

---

## 目录结构

```
~/.openclaw/workspace/
├── INDEX.md
├── SOUL.md
├── USER.md
├── MEMORY.md
├── IDENTITY.md
├── AGENTS.md
├── PROJECTS.md
├── HEARTBEAT.md
├── TOOLS.md
└── skills/
    ├── competitor-analysis/SKILL.md
    ├── market-research/
    │   ├── SKILL.md
    │   ├── competitor-analysis.md
    │   └── validation.md
    └── paper-recommendation/
        ├── SKILL.md
        └── WORKFLOW.md
```

---

## 环境

- OpenClaw: 最新版本
- OS: Linux (Ubuntu/Debian)
- 工作空间: /home/lkx/.openclaw/workspace/
- 技能目录: /home/lkx/.openclaw/workspace/skills/

---

## 贡献者

康欣, 2026-03-03
