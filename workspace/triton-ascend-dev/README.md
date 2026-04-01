# Triton-Ascend Development Skill Repository

Triton-ascend operator development workflow repository for Ascend hardware.

## Quick Links

- **Operator Development Workflow**: See [SKILL.md](SKILL.md)
- **Team Access & Permissions**: See [COLLABORATORS.md](COLLABORATORS.md)
- **Detailed Permission Reference**: See [.github/PERMISSIONS.md](.github/PERMISSIONS.md) 
- **Problem Resolution**: See [troubleshooting.md](troubleshooting.md)

## Repository Structure

```
triton-ascend-dev/
├── demo/              # Operator implementation examples
├── guides/            # Technical guides (msprof, migration, pitfalls)
├── references/        # Reference documentation
├── tools/             # Utility scripts
├── SKILL.md           # Complete operator development workflow
├── COLLABORATORS.md   # Team structure and access configuration
└── troubleshooting.md # Common issues and solutions
```

## For Team Members

If you're joining this project:

1. Review [SKILL.md](SKILL.md) for the complete development workflow
2. Check [COLLABORATORS.md](COLLABORATORS.md) for access procedures
3. Understand the 4-file structure for operator implementations
4. Ensure you have access to triton-ascend-hcq container environment

## Code Review Process

Automated via `.github/CODEOWNERS`:
- Changes automatically route to appropriate reviewers
- Operator implementations require correctness validation
- Performance optimizations require baseline comparison

## Development Environment

All operator development and profiling must occur inside the triton-ascend-hcq container with proper Ascend toolkit configuration. See SKILL.md for environment setup details.
