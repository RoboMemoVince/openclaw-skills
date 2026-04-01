---
name: claw-backup
description: |
  Backup and restore claw (OpenClaw agent) memory/personality to GitHub.
  Use when user says "存一下", "备份", "同步到仓库", "复活", or mentions backing up/restoring agent state.
platform: [openclaw]
---

# Claw Backup Skill

把 Claw 的"灵魂"存到 GitHub，换机器时一键复活。

## 配置

首次使用时，在 `TOOLS.md` 中添加配置：

```markdown
### Claw Backup
- 仓库: git@github.com:YOUR_NAME/YOUR_REPO.git
- 本地目录: ~/.openclaw/claw-backup
```

如果没有配置，执行备份时会提示用户先设置。

## 文件范围

备份这些文件：
- `SOUL.md` — 人格定义
- `IDENTITY.md` — 身份信息（名字、emoji）
- `USER.md` — 用户信息
- `AGENTS.md` — 行为准则
- `MEMORY.md` — 长期记忆
- `TOOLS.md` — 本地工具配置
- `HEARTBEAT.md` — 心跳任务
- `memory/` — 每日记忆目录

## 使用方式

### 首次设置

1. 在 GitHub 创建一个**私有仓库**（名称随意，如 `claw-memory`）
2. 在 `TOOLS.md` 中添加配置（见上方格式）
3. 告诉 Claw "初始化备份"

Clow 会执行：
- 创建本地备份目录
- 复制所有文件
- 初始化 git 并 push 到远程仓库

### 备份（用户说"存一下"）

1. 复制文件到备份目录
2. git add -> commit -> push

```bash
BACKUP_DIR="$HOME/.openclaw/claw-backup"
WORKSPACE="$HOME/.openclaw/workspace"

# 确保备份目录存在
mkdir -p "$BACKUP_DIR"

# 复制文件
for f in SOUL.md IDENTITY.md USER.md AGENTS.md MEMORY.md TOOLS.md HEARTBEAT.md; do
  [ -f "$WORKSPACE/$f" ] && cp "$WORKSPACE/$f" "$BACKUP_DIR/"
done

# 复制 memory 目录
[ -d "$WORKSPACE/memory" ] && rsync -a --delete "$WORKSPACE/memory/" "$BACKUP_DIR/memory/"

# 提交
cd "$BACKUP_DIR"
git add -A
git commit -m "backup: $(date '+%Y-%m-%d %H:%M:%S')"
git push
```

### 恢复（新机器复活）

1. 在 `TOOLS.md` 中添加仓库配置
2. 告诉 Claw "从备份复活"

Claw 会执行：
```bash
BACKUP_DIR="$HOME/.openclaw/claw-backup"
WORKSPACE="$HOME/.openclaw/workspace"

# Clone（仓库地址从 TOOLS.md 读取）
git clone <REPO_URL> "$BACKUP_DIR"

# 恢复文件
for f in SOUL.md IDENTITY.md USER.md AGENTS.md MEMORY.md TOOLS.md HEARTBEAT.md; do
  [ -f "$BACKUP_DIR/$f" ] && cp "$BACKUP_DIR/$f" "$WORKSPACE/"
done

# 恢复 memory 目录
[ -d "$BACKUP_DIR/memory" ] && rsync -a "$BACKUP_DIR/memory/" "$WORKSPACE/memory/"

# 重启 OpenClaw
```

## 注意事项

- 仓库必须是**私有**的（包含个人信息）
- 确保 SSH 密钥已配置（能 push 到 GitHub）
- 恢复后需要重启 OpenClaw 才能加载新的记忆文件
