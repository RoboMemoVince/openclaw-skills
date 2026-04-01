---
name: arxiv-translator
platform: [openclaw, claude-code]
description: "Translate arXiv papers from English to Chinese while preserving LaTeX formatting, figures, equations, and references. Use when user provides an arXiv link and wants a Chinese translation PDF. Triggers: 'translate paper', 'arXiv翻译', '论文翻译', 'translate to Chinese'."
---

# arXiv Paper Translator

## Overview

将 arXiv 英文论文翻译为中文，保持 LaTeX 排版、公式、图表、引用完整，输出可编译的中文 PDF。

## 流程

```
1. 下载源码 → 2. 分析结构 → 3. 术语表 → 4. 并行翻译 → 5. 后处理 → 6. 编译 → 7. 校验
```

## Step 1: 下载 LaTeX 源码

```bash
cd /tmp && mkdir paper-zh && cd paper-zh
curl -L -o source.tar.gz "https://arxiv.org/e-print/<ARXIV_ID>"
tar -xzf source.tar.gz
ls *.tex  # 确认 tex 文件存在
```

⚠️ 如果没有 LaTeX 源码（只有 PDF），此流程不适用。

## Step 2: 分析论文结构

1. 找到主 tex 文件（通常包含 `\documentclass` 和 `\begin{document}`）
2. 列出所有 `\input{}` 的章节文件
3. 记录使用的包和自定义命令
4. 检查 figures/ 目录和 ref.bib

## Step 3: 建立术语表

**翻译前必须建立统一术语表**，避免各章节翻译不一致。

规则：
- **专业术语缩写保留英文**：LLM, SFT, RL, MoE, MLP, GQA, MLA, DSA, MTP, AGI, KV cache, token, rollout, on-policy, off-policy 等
- **专有名词保留英文**：模型名(GPT, Claude, Gemini)、benchmark名(SWE-bench, HLE)、框架名(vLLM, SGLang)
- **需要翻译的**：段落正文、章节标题、图表 caption、表格 caption
- **不翻译的**：公式、LaTeX 命令、\cite{}、\ref{}、\label{}、表格数据、代码块、参考文献

将术语表写入 prompt 传给翻译子代理/任务。

## Step 4: 并行翻译

按章节拆分，并行翻译各文件。

**翻译 prompt 模板**：
```
翻译以下 LaTeX 文件为中文。规则：
1. 只翻译文本段落，保留所有 LaTeX 命令、公式、\cite、\ref、\label
2. 表格/图表 caption 翻译，表格内数据保留原样
3. 术语表：[粘贴术语表]
4. 直接输出翻译后的完整文件内容，保存为 xxx_zh.tex
5. 不要翻译参考文献（ref.bib 保持英文原样）
```

⚠️ **不要用 sed 全局替换术语** — 会破坏中文句子结构（如 sed 把"强化学习"→"RL"时可能产生"asynchronousRL"这种拼接）。术语保留规则应在翻译 prompt 中直接指定。

## Step 5: 后处理

### 5.1 创建中文版主文件

复制原始主文件，修改：
- `\input{xxx}` → `\input{xxx_zh}`
- 标题翻译（或保留英文）
- 作者信息按需翻译

### 5.2 适配 XeLaTeX 编译

**必须用 XeLaTeX**（不是 pdfLaTeX），因为需要 Unicode 中文支持。

### 字体安装（如缺失）
```bash
apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra
```

### 主文件头部模板（专业中文论文标准）

正文：宋体（思源宋体），标题：黑体（思源黑体），英文/数字：Times New Roman（TeX Gyre Termes 替代）。

```latex
\documentclass[a4paper, 12pt]{article}

\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}           % 英文 → Times New Roman 替代

\usepackage{xeCJK}
\setCJKmainfont{Noto Serif CJK SC}      % 正文 → 宋体
\setCJKsansfont{Noto Sans CJK SC}       % 标题 → 黑体
\setCJKmonofont{Noto Sans CJK SC}

\usepackage{geometry}
\geometry{a4paper, left=25mm, right=25mm, top=30mm, bottom=25mm}

\XeTeXlinebreaklocale "zh"
\XeTeXlinebreakskip = 0pt plus 2pt minus 0.5pt

\linespread{1.5}                         % 1.5 倍行距

\usepackage{titlesec}
% 一级标题：小三号黑体（≈15pt）
\titleformat{\section}
  {\sffamily\fontsize{15pt}{20pt}\selectfont\bfseries}{\thesection}{1em}{}
% 二级标题：四号黑体（≈14pt）
\titleformat{\subsection}
  {\sffamily\fontsize{14pt}{18pt}\selectfont\bfseries}{\thesubsection}{1em}{}
% 三级标题：小四号黑体（≈12pt）
\titleformat{\subsubsection}
  {\sffamily\fontsize{12pt}{16pt}\selectfont\bfseries}{\thesubsubsection}{1em}{}

\usepackage{caption}
\captionsetup{font=small, labelfont=bf, labelsep=period}

\tolerance=2000
\emergencystretch=3em
```

**标题字号对应**：
| 层级 | 字号 | 字体 |
|------|------|------|
| 论文标题 | 18pt ≈ 二号 | 黑体加粗居中 |
| 一级 (section) | 15pt ≈ 小三号 | 黑体加粗 |
| 二级 (subsection) | 14pt ≈ 四号 | 黑体加粗 |
| 三级 (subsubsection) | 12pt ≈ 小四号 | 黑体加粗 |

### 5.3 处理包冲突

| 问题 | 解决方案 |
|------|----------|
| `CJKutf8` 包 | XeLaTeX 下删除，用 fontspec + xeCJK 替代 |
| `\begin{CJK*}` 环境 | 直接删除（XeLaTeX 原生支持 Unicode） |
| `utfsym` 包 | XeLaTeX 下可能报错，删除或注释 |
| `inputenc` 包 | XeLaTeX 下忽略，可删除 |
| `\DeclareUnicodeCharacter` | XeLaTeX 下不可用，删除 |
| `landscape` 页面 | 保持纵向一致性，用 `\scriptsize` 缩小表格 |

### 5.4 表格适配

宽表格在翻译后可能溢出（中文字符比英文宽），解决方案：
- 缩小字号：`\scriptsize` 或 `\footnotesize`
- 减小列间距：`\setlength{\tabcolsep}{1.5pt}`
- **不要用 `\renewenvironment{table}`** — 会破坏 `\label` 和 `\ref` 机制

### 5.5 清理翻译残留

```bash
# 去掉 \paragraph{} 中的多余句号（翻译常见问题）
sed -i 's/\\paragraph{\(.*\)。}/\\paragraph{\1}/g' *_zh.tex
```

## Step 6: 编译（四步，顺序不可乱）

```bash
xelatex -interaction=nonstopmode main.tex    # 1. 生成 aux
bibtex main                                   # 2. 生成 bbl
xelatex -interaction=nonstopmode main.tex    # 3. 读入 bbl
xelatex -interaction=nonstopmode main.tex    # 4. 解析交叉引用
```

⚠️ **关键**：
- 四步之间**不要清除 aux/bbl 文件**
- 如果清除了 aux，必须从第1步重来
- bibtex 只需运行一次（除非改了 bib 文件）

## Step 7: 校验

```bash
grep -c "undefined citation" main.log    # 应为 0
grep -c "undefined reference" main.log   # 字体警告不算
grep -c "Overfull" main.log              # 越少越好
```

目视检查：
- [ ] 引用显示为 [1] 而非 [?]
- [ ] 交叉引用为数字而非 ??
- [ ] 图片/公式正常
- [ ] 中文无乱码
- [ ] 页面方向一致
- [ ] 标题层级有区分
- [ ] 行间距适当

## 常见踩坑

### 1. sed 全局替换灾难
**症状**："asynchronousRL基础设施" 等中英文拼接怪词
**原因**：sed 替换"强化学习"→"RL"时不考虑中文无空格连写
**解决**：不要 sed 后处理术语，在翻译 prompt 中直接指定

### 2. 引用全是 [?]
**症状**：所有 `\cite{}` 显示为 [?]
**原因**：编译顺序错误，或中途清了 aux
**解决**：严格四步编译，中间不清文件

### 3. 交叉引用全是 ??
**症状**：`\ref{tab:xxx}` 显示为 ??
**原因**：`\renewenvironment{table}` 破坏了 label 机制
**解决**：不要重定义 table/figure 环境

### 4. 中文乱码
**症状**：方块或乱码
**原因**：用了 pdflatex
**解决**：必须用 xelatex + fontspec/xeCJK

### 5. tcolorbox/utfsym 报错
**症状**：`Environment tcolorbox undefined` 或 `\DeclareUnicodeCharacter` 错误
**解决**：加 `\usepackage[most]{tcolorbox}`；删除 utfsym 相关

### 6. \paragraph{} 双句号
**症状**："结果。。图1展示了..."
**原因**：原文 `\paragraph{Results.}` 句号被翻译保留 + 格式定义又加句号
**解决**：`sed -i 's/\\paragraph{\(.*\)。}/\\paragraph{\1}/g' *_zh.tex`

### 7. 中文字体缺粗体/斜体
**症状**：`Font shape undefined` 警告
**影响**：不影响编译，自动回退。安装 fonts-noto-cjk-extra 可获取更多变体

## 依赖安装（Ubuntu）

```bash
apt-get install -y texlive-xetex texlive-latex-extra texlive-lang-chinese \
    texlive-science texlive-fonts-recommended \
    fonts-noto-cjk fonts-noto-cjk-extra
```

## 产出文件结构

```
paper-zh/
├── main.tex             # 中文版主文件
├── abstract_zh.tex      # 翻译后的各章节
├── 1_intro_zh.tex
├── ...
├── figures/             # 原始图片（不动）
├── ref.bib              # 参考文献（不翻译）
└── *.sty                # 原始样式文件
```

## 贡献者
Musk (OpenClaw), 2026-03-05
