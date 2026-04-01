---
name: feishu-doc-writer
description: |
  Write structured content to Feishu cloud documents efficiently and reliably.
  Activate when: creating Feishu docs, writing long-form content to docx, generating reports/guides/notes as Feishu documents.
  NOT for: reading docs, wiki operations, bitable, or drive file management (use feishu-doc, feishu-wiki, feishu-drive skills instead).
platform: [openclaw]
updated: 2026-03-11
---

# Feishu Doc Writer

Reliable workflow for creating and writing content to Feishu cloud documents. Updated for feishu plugin v2026.3.7+.

## Critical Rules

1. **`create` only creates an empty doc** — content param is ignored. Always follow up with `write` or `append`.
2. **Always pass `owner_open_id`** when creating docs — so the requesting user automatically gets `full_access`. Without it, only the bot has access.
3. **`write` works on empty docs** — (confirmed v2026.3.7) it clears all content and rewrites. Safe for both new and existing docs.
4. **`append` is safer for incremental writes** — use when adding to existing content without disturbing what's already there.
5. **Split long content into chunks** — for content exceeding ~3000 chars, append in segments by logical sections to avoid API failures.
6. **No markdown tables** — the `convertMarkdown` API does not support `| col |` syntax. Use `create_table_with_values` for native Docx tables instead.
7. **Avoid emoji in headings** — some emoji cause block conversion failures. Keep headings plain text.

## Workflow

### Create + Write New Document (Recommended)

```
Step 1: Create empty doc
  feishu_doc → action: "create", title: "文档标题", owner_open_id: "ou_xxx"
  → save document_id from response

Step 2: Write content
  feishu_doc → action: "write", doc_token: "<document_id>", content: "<full_markdown>"
```

If content is very long (5000+ chars), use chunked append instead:

```
Step 2a: Append first section
  feishu_doc → action: "append", doc_token: "<document_id>", content: "<section_1>"

Step 2b: Append remaining sections
  feishu_doc → action: "append", doc_token: "<document_id>", content: "<section_2>"
  ... repeat as needed
```

### Replace Existing Document Content

```
feishu_doc → action: "write", doc_token: "<document_id>", content: "<full_markdown>"
```

This clears all existing content and rewrites. Works on both empty and non-empty docs.

### Permission Setup

Best practice: pass `owner_open_id` at create time. If missed, use `feishu_perm`:

```
feishu_perm → action: "add", token: "<doc_token>", type: "docx",
              member_type: "openid", member_id: "ou_xxx", perm: "full_access"
```

## Content Formatting Guide

### Supported Markdown

- `# ## ###` — Headings (H1-H3)
- `- item` — Bullet lists
- `1. item` — Numbered lists
- `**bold**` `*italic*` `~~strikethrough~~` — Inline formatting
- `` `code` `` — Inline code
- ` ```lang ... ``` ` — Code blocks
- `> quote` — Block quotes
- `[text](url)` — Links
- `![alt](https://url)` — Images (auto-uploaded from URL)
- `---` — Dividers

### NOT Supported

- Markdown tables (`| col |`) — use native Docx tables (see below)
- Nested blockquotes
- HTML tags
- Footnotes

## Native Docx Tables

For tabular data, use `create_table_with_values` instead of markdown tables:

```
feishu_doc → action: "create_table_with_values",
  doc_token: "<document_id>",
  row_size: 3,
  column_size: 3,
  column_width: [200, 200, 200],
  values: [
    ["维度", "Claude Code", "OpenClaw"],
    ["编码深度", "⭐⭐⭐⭐⭐", "⭐⭐⭐"],
    ["自动化", "❌", "⭐⭐⭐⭐⭐"]
  ]
```

This creates a proper Docx table block with cell values in one call.

For updating existing table cells:
```
feishu_doc → action: "write_table_cells",
  doc_token: "<document_id>",
  table_block_id: "<table_block_id>",
  values: [["new A1", "new B1"], ["new A2", "new B2"]]
```

## Images and File Attachments (v2026.3.7+)

### Upload Image
```
feishu_doc → action: "upload_image",
  doc_token: "<document_id>",
  url: "https://example.com/image.png"
```

Or from local file with position control:
```
feishu_doc → action: "upload_image",
  doc_token: "<document_id>",
  file_path: "/tmp/image.png",
  parent_block_id: "<block_id>",
  index: 5
```

Note: Image display size = pixel dimensions. Scale small images to 800px+ width before uploading.

### Upload File Attachment
```
feishu_doc → action: "upload_file",
  doc_token: "<document_id>",
  file_path: "/tmp/report.pdf",
  filename: "Q1-report.pdf"
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| 400 on `write`/`append` | Content too long or malformed markdown | Split into smaller chunks; remove tables |
| 403 | Missing permissions | Check `feishu_app_scopes`, need `docx:document` + `docx:document.block:convert` |
| Empty doc after `create` | `content` param ignored by create | Use `write` or `append` as a separate step |
| "Request failed" | Network or rate limit | Retry once after 2s |

## Quick Reference

For detailed `feishu_doc` API actions and parameters, see the built-in feishu-doc skill at:
`/usr/lib/node_modules/openclaw/extensions/feishu/skills/feishu-doc/SKILL.md`
