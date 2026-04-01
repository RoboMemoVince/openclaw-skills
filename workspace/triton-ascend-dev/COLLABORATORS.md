# Triton-Ascend Development Team Structure

## 协作者权限概览 / Collaborator Permissions Overview

**详细权限说明**: 查看 [`.github/PERMISSIONS.md`](.github/PERMISSIONS.md) 获取完整的权限参考文档  
**Detailed Permissions**: See [`.github/PERMISSIONS.md`](.github/PERMISSIONS.md) for complete permission reference

### 快速权限对照表 / Quick Permission Reference

| 权限级别 Level | 适用角色 Role | 推送代码 Push | 创建PR Create PR | 审查代码 Review | 合并PR Merge | 管理设置 Admin |
|--------------|--------------|-------------|----------------|---------------|------------|---------------|
| Read | 观察者 Observer | ❌ | ❌ | ❌ | ❌ | ❌ |
| Triage | Issue管理 Issue Manager | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Write** | **算子开发者 Operator Dev** | ✅ | ✅ | ✅ | ❌ | ❌ |
| Maintain | 文档维护者 Doc Maintainer | ✅ | ✅ | ✅ | ✅* | ❌ |
| Admin | 仓库管理员 Repo Admin | ✅ | ✅ | ✅ | ✅ | ✅ |

*需满足分支保护规则 / Must meet branch protection rules

**推荐配置**: 大多数贡献者使用 **Write** 权限  
**Recommended**: Most contributors use **Write** permission level

---

## Repository Access Configuration

### Current Team Structure

**Primary Maintainer**: @Qubhu
- Manages NPU operator implementation workflows
- Reviews all operator correctness and performance changes
- Approves modifications to profiling and benchmarking procedures

### Collaboration Model for NPU Operator Development

This repository follows a specialized workflow for Ascend NPU operator development. Team members working on different aspects should understand:

#### Operator Implementation Contributors
Focus areas: Writing triton-ascend kernels, reference implementations
- Must validate correctness before submitting (see SKILL.md § Prerequisites)
- Submit operators following the 4-file structure defined in SKILL.md
- Include accuracy test results in PR description

#### Performance Tuning Contributors  
Focus areas: msprof analysis, kernel optimization, benchmarking
- Must work inside triton-ascend-hcq container environment
- Document baseline performance before optimization attempts
- Follow "one variable per iteration" principle from SKILL.md

#### Documentation Contributors
Focus areas: guides/, references/, troubleshooting.md updates
- Keep documentation synchronized with actual workflow changes
- Add new profiling cases or debugging scenarios as discovered

### Request Access Procedure

For team members needing repository access:

1. Identify your primary contribution area (implementation/tuning/documentation)
2. Contact repository owner @Qubhu with:
   - Your GitHub username
   - Specific areas you'll be contributing to
   - Whether you need push access or will work via forks

3. Repository owner will configure access level:
   - **Push rights**: For regular contributors working on operator implementations
   - **Review rights**: For contributors validating operator correctness
   - **Maintain rights**: For contributors managing issues and documentation PRs

### Pull Request Review Requirements

Based on change type:
- **Operator code** (demo/, new kernels): Requires correctness validation + performance check
- **Guides** (guides/, references/): Requires technical accuracy review
- **Workflow** (SKILL.md, tools/): Requires workflow coherence review

Review assignments are automated via .github/CODEOWNERS file.

### Working with triton-ascend-hcq Container

Contributors with operator implementation or tuning responsibilities need:
- Access to the Ascend NPU development environment
- Ability to execute within triton-ascend-hcq container
- Proper ASCEND_TOOLKIT_HOME environment configuration

See SKILL.md section "Environment and Execution Template" for container setup.

### Branch Strategy

- Direct pushes to feature branches allowed for authorized contributors
- All merges to main branch require PR review
- Operator implementations should include: _triton.py, _ref.py, _test.py files

## Contact

Questions about team access or permissions: Open an issue or contact @Qubhu
