#!/bin/bash

# Repo Stats Script
# 快速获取仓库统计信息
# 用法: bash repo-stats.sh [repo-path]

REPO_PATH="${1:-.}"

cd "$REPO_PATH" || { echo "Error: Cannot access $REPO_PATH"; exit 1; }

echo "======================================"
echo "        仓库统计信息"
echo "======================================"
echo ""

# 检查是否是 git 仓库
if [ -d ".git" ]; then
    echo "📁 Git 仓库信息"
    echo "--------------------------------------"

    # 获取仓库名
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "无远程仓库")
    echo "远程地址: $REMOTE_URL"

    # 提交统计
    COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "N/A")
    echo "提交总数: $COMMIT_COUNT"

    # 分支数
    BRANCH_COUNT=$(git branch -a 2>/dev/null | wc -l | tr -d ' ')
    echo "分支总数: $BRANCH_COUNT"

    # 最近提交
    echo ""
    echo "最近 5 次提交:"
    git log --oneline -5 2>/dev/null || echo "无提交记录"

    # 贡献者统计
    echo ""
    echo "Top 5 贡献者:"
    git shortlog -sn --no-merges HEAD 2>/dev/null | head -5 || echo "无法获取"

    echo ""
fi

echo "📊 文件类型统计"
echo "--------------------------------------"

# 文件类型统计函数
count_files() {
    local ext=$1
    local count=$(find . -name "*.$ext" \
        -not -path "*/node_modules/*" \
        -not -path "*/.git/*" \
        -not -path "*/vendor/*" \
        -not -path "*/target/*" \
        -not -path "*/__pycache__/*" \
        -not -path "*/.venv/*" \
        -not -path "*/dist/*" \
        -not -path "*/build/*" \
        2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        echo "$ext: $count"
    fi
}

# 常见文件类型
count_files "ts"
count_files "tsx"
count_files "js"
count_files "jsx"
count_files "py"
count_files "rs"
count_files "go"
count_files "java"
count_files "rb"
count_files "php"
count_files "c"
count_files "cpp"
count_files "h"
count_files "cs"
count_files "swift"
count_files "kt"
count_files "vue"
count_files "svelte"

echo ""
echo "📄 配置文件统计"
echo "--------------------------------------"

count_files "json"
count_files "yaml"
count_files "yml"
count_files "toml"
count_files "xml"
count_files "md"

echo ""
echo "📦 项目类型检测"
echo "--------------------------------------"

if [ -f "package.json" ]; then
    echo "✓ Node.js 项目 (package.json)"
    # 检测框架
    if grep -q '"react"' package.json 2>/dev/null; then echo "  → React"; fi
    if grep -q '"vue"' package.json 2>/dev/null; then echo "  → Vue"; fi
    if grep -q '"angular"' package.json 2>/dev/null; then echo "  → Angular"; fi
    if grep -q '"next"' package.json 2>/dev/null; then echo "  → Next.js"; fi
    if grep -q '"express"' package.json 2>/dev/null; then echo "  → Express"; fi
    if grep -q '"fastify"' package.json 2>/dev/null; then echo "  → Fastify"; fi
    if grep -q '"nestjs"' package.json 2>/dev/null; then echo "  → NestJS"; fi
fi

if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then
    echo "✓ Python 项目"
    if [ -f "pyproject.toml" ]; then echo "  → 使用 pyproject.toml"; fi
    if [ -f "requirements.txt" ]; then echo "  → 使用 requirements.txt"; fi
fi

if [ -f "Cargo.toml" ]; then
    echo "✓ Rust 项目 (Cargo.toml)"
fi

if [ -f "go.mod" ]; then
    echo "✓ Go 项目 (go.mod)"
fi

if [ -f "pom.xml" ]; then
    echo "✓ Java Maven 项目 (pom.xml)"
fi

if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
    echo "✓ Java/Kotlin Gradle 项目"
fi

if ls *.csproj 1>/dev/null 2>&1; then
    echo "✓ .NET 项目 (*.csproj)"
fi

if [ -f "Gemfile" ]; then
    echo "✓ Ruby 项目 (Gemfile)"
fi

if [ -f "mix.exs" ]; then
    echo "✓ Elixir 项目 (mix.exs)"
fi

if [ -f "composer.json" ]; then
    echo "✓ PHP 项目 (composer.json)"
fi

echo ""
echo "📂 目录结构 (深度 2)"
echo "--------------------------------------"

find . -type d -maxdepth 2 \
    -not -path "*/node_modules/*" \
    -not -path "*/.git/*" \
    -not -path "*/vendor/*" \
    -not -path "*/target/*" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.venv/*" \
    -not -path "*/dist/*" \
    -not -path "*/build/*" \
    -not -path "*/.idea/*" \
    -not -path "*/.vscode/*" \
    2>/dev/null | sort | head -30

echo ""
echo "======================================"
echo "        统计完成"
echo "======================================"
