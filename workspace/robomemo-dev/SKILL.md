---
name: robomemo-dev
description: "RoboMemo Platform development — Embodied Data Platform for robot data annotation, VLM integration, and RoboForce data management. Use when developing, debugging, or deploying RoboMemo. Triggers: 'RoboMemo', 'Platform开发', '标注系统', 'annotation order'."
platform: [openclaw]
---

# RoboMemo Platform Development

## Project Location
- **Code**: `/Volumes/MOVESPEED/Project/RoboMemo/Platform`
- **GitHub**: `https://github.com/RoboMemo/RoboMemo`
- **Branch**: `siyu-developing` (active dev), `main` (stable)

## Architecture
- **Frontend**: React + TypeScript + Vite + shadcn/ui
  - `app/src/sections/` — main page components
  - `app/src/components/` — shared UI components
  - `app/src/services/api.ts` — backend API client
- **Backend**: Node.js + Express + SQLite (better-sqlite3)
  - `backend/server.js` — main server (~2000+ lines, all API routes)
  - `backend/db.js` — database schema + seeding
  - `backend/services/auth.js` — JWT auth, user management
- **Database**: SQLite at `backend/data/robomemo.db`

## Running Locally
- Frontend: `cd app && npm run dev` → `http://localhost:5174`
- Backend: `cd backend && node server.js` → `http://localhost:3001`
- CORS: backend must allow frontend origin (check `CORS_ORIGINS` in server.js)
- Default admin: `admin@robomemo.io / admin123` (auto-login enabled)

## Key Features (Existing)
1. **Dataset Management** — LeRobot datasets, episodes, video preview
2. **Auto-Annotation with VLM** — Gemini API + Ollama local models (SmolVLM etc.)
3. **Structured VQA** — 7-category structured video QA
4. **Multi-annotator Collaboration** — tasks, assignments, login
5. **Quality Control** — reviews, IAA calculation
6. **Order Management** — annotation orders, progress tracking
7. **Batch Operations** — bulk import/assign/export
8. **RoboForce Integration** — sensor presets, import wizard
9. **Billing Management** — rate management, billing summary

## Development Rules (CRITICAL)
1. **Use Claude Code for all code changes** — Lucy coordinates, CC executes
2. **Test before committing** — `cd app && npx tsc --noEmit` for TS, manual browser check
3. **Never break existing features** — always compare with main branch when modifying
4. **One commit per logical change** — descriptive commit messages
5. **CORS awareness** — if frontend port changes, update `CORS_ORIGINS` in server.js

## CC (Claude Code) Usage for RoboMemo
- **Working dir**: `/Volumes/MOVESPEED/Project/RoboMemo/Platform`
- **Model aliases**: `sonnet` (default), `opus` (complex tasks)
  - yunwu maps: `sonnet` → `claude-sonnet-4-6`, `opus` → `claude-opus-4-6`
  - DO NOT use `claude-opus-4-5` or `claude-sonnet-4-5` — 503 error on yunwu
- **Permission mode**: `--permission-mode dontAsk`
- **Scope restriction**: always tell CC to only modify files inside Platform/

## RoboMemo 战略定位 — Embodied Data as a Service (DaaS)

### 第一性原理背景
- 当前具身智能尚未到 GPT-2 时刻；从 LLM/自动驾驶发展历程来看，Data 是先决条件
- 具身数据在数量/模态/质量/场景上严重欠缺，需 5 年积累才能喂到 GPT-3 时刻
- **做泛化 Skill 为时尚早**；Embodied Data + Data Infra 才是"共用的铲子"
- 生态位类比：NVIDIA（硬件基础设施） + ScaleAI（数据标注工厂）

### 战略核心
RoboMemo 是 **Embodied Data Infra**，目标岗位是未来 1-3 年机器人大概率落地的场景（增薪仍招不到人、当前机器人技术暂时无法解决）。

**第一性原理**：替代人类岗位 = 需要凝结该岗位所有人类专家智能的数据  
→ 数据必须覆盖该垂类岗位所需全部模态：**语言、视觉、连续运动、离散动作、听觉、触觉、温度等**  
→ 被采集者必须是该岗位人类专家，且采集时 have access to all modalities  
→ **遥操作不是最 SOTA 的采集方式**  
→ 将与 Manifold Tech 合作研发不同岗位的最小成本 SOTA 采集硬件

### 采集行业/场景策略
**预埋 Navigation + Loco-Manipulation 任务所必须的多模态高质量数据**  
→ 相当于对具身物理智能必经之路提前修好高速公路  
→ Figure、RoboForce 等高速赛车驶来时畅通无阻，我们逐车收费  
→ 终局：边际成本近零的卖铲子生意（源数据=原油，RoboMemo pipeline=炼油厂）

### 三大技术栈
**A. Data Augmentation**（一次采集，多次使用）
- 跨本体：retargeting（人/机器人本体互转）
- 跨场景：AIGC 生成式场景增广
- 跨视角：egocentric 视角转换（第三人称→第一人称，臂部相机→手腕相机）

**B. Self Labeling**（两条线）
- VQA 语言自标注模型（针对 RoboForce 近期需求）
- World Model 物理预测与物理自标注模型（泛化需求）

**C. 数采技术栈**
- 无感可穿戴设备，采集该任务全部人类智能数据
- 不同岗位不同硬件，最小成本原则

### 一句话总结
> **Learning Based Model => Garbage in, Garbage out**  
> **With RoboMemo: Golden Data in, Golden Skill Out.**

---

## Pitfalls & Lessons Learned

### CORS 问题
- Vite dev server port 可能是 5173 或 5174（取决于端口占用）
- 后端 CORS_ORIGINS 必须包含实际前端端口
- 症状: "Failed to fetch" on login/API calls

### CC 模型名
- yunwu 上的模型名和 CC 默认模型名不一致
- 用别名 `sonnet` / `opus` 而不是完整模型 ID
- `claude-opus-4-5` / `claude-sonnet-4-5` 在 yunwu 上无渠道 → 503

### CC 工作目录逃逸
- CC 可能修改 Platform 目录之外的文件
- Prompt 里必须强调 "ONLY work inside this directory"
- 每次 CC 完成后检查 `git status` 确认改动范围

### 后端重启
- 修改 server.js 后需要手动重启后端
- `ps aux | grep "node server.js"` → kill → 重新启动
- 前端 Vite 支持 HMR，不需要重启

### Episode 视频路径
- Episodes 的 `h5_path` 字段存视频路径
- 同一 dataset 所有 episode 可能指向同一个 mp4（种子数据限制）
- 视频文件在 `data/datasets/*/videos/` 下

### 子 agent 代码质量
- sub-agent (sessions_spawn) 生成的代码可能有 bug
- 必须逐个测试新增功能
- 对比 main branch 确保不破坏现有功能

## Video Streaming
- Route: `/api/episodes/:episodeId/video` — HTTP range request support
- Route: `/api/episodes/:episodeId/frame` — single frame extraction
- Multi-camera: ALOHA datasets have 4 cameras (cam_high, cam_left_wrist, cam_low, cam_right_wrist)

## Data on Disk
- `lerobot_aloha_shrimp/videos/observation.images.cam_high/` (4 files, 1.2G)
- `lerobot_aloha_cups/videos/observation.images.cam_*/` (4 cameras, 488M)
- `lerobot_xarm_lift/videos/observation.image/` (18M)
- `lerobot_pusht/videos/observation.image/` (7.5M)
