# 当前协作者权限 / Current Collaborator Permissions

## 权限配置状态 / Permission Configuration Status

### 仓库管理员 / Repository Administrators
- **@Qubhu** - Admin (完全管理权限 / Full administrative access)

### 协作者 / Collaborators
当前暂无其他协作者。如需申请权限，请查看下方流程。  
Currently no other collaborators. To request access, see the process below.

---

## 如何查看详细权限说明 / How to View Detailed Permissions

### 中文用户 / Chinese Users:
请查看以下文档了解完整的权限配置：
1. **[权限参考文档](.github/PERMISSIONS.md)** - 详细的权限级别说明、操作范围、申请流程
2. **[协作者文档](COLLABORATORS.md)** - 团队结构、贡献者角色、工作流程

### English Users:
Please refer to the following documents for complete permission configuration:
1. **[Permission Reference](.github/PERMISSIONS.md)** - Detailed permission levels, operation scope, request process
2. **[Collaborators Guide](COLLABORATORS.md)** - Team structure, contributor roles, workflows

---

## 权限级别快速对照 / Quick Permission Level Reference

| 级别 Level | 推荐用途 Recommended Use | 关键权限 Key Permissions |
|-----------|------------------------|------------------------|
| **Write** | 算子开发、性能调优<br>Operator dev, performance tuning | 推送代码、创建PR、代码审查<br>Push code, create PR, review |
| **Maintain** | 文档维护、高级贡献<br>Doc maintenance, senior contributions | Write权限 + 合并PR、管理Release<br>Write + merge PR, manage releases |
| **Admin** | 仓库管理<br>Repo management | 完全控制<br>Full control |

---

## 申请权限 / Request Permissions

联系仓库管理员 @Qubhu，提供以下信息：  
Contact repository admin @Qubhu with:

1. ✉️ GitHub 用户名 / GitHub username
2. 📋 贡献领域 / Contribution area (算子开发/性能调优/文档)
3. 🔑 所需权限级别 / Required permission level
4. 💻 是否需要NPU环境访问 / Need NPU environment access?

---

## 自动代码审查分配 / Automatic Code Review Assignment

通过 `.github/CODEOWNERS` 配置，以下变更会自动通知审查者：  
Via `.github/CODEOWNERS`, the following changes automatically notify reviewers:

- `/demo/` 目录 - 算子实现 → @Qubhu
- `/guides/` 目录 - 技术指南 → @Qubhu  
- `/references/` 目录 - 参考文档 → @Qubhu
- `/tools/` 目录 - 工具脚本 → @Qubhu
- `SKILL.md` - 工作流程定义 → @Qubhu

---

最后更新 / Last Updated: 2026-02-06
