---

name: ckpt
description: Save a checkpoint of the current dialogue for resuming work later. Invoke with /ckpt to create a summary of session goals, progress, decisions, and pending tasks.
platform: [openclaw, claude-code]
---


# Checkpoint Skill

Save a checkpoint of the current dialogue for resuming work later.

## Instructions

When invoked, create a checkpoint file that summarizes the current session:

1. **Generate a summary** of the dialogue up to this point, including:
   - **Session Goal**: What the user is trying to accomplish
   - **Progress Made**: Key actions completed, files created/modified
   - **Current State**: Where we are in the workflow
   - **Key Decisions**: Important choices or configurations made
   - **Pending Tasks**: What remains to be done
   - **Important Context**: File paths, variable names, technical details needed to resume

2. **Save the checkpoint** to a markdown file:
   - Location: `.claude/checkpoints/` directory
   - Filename format: `ckpt_YYYYMMDD_HHMMSS.md` (using current timestamp)
   - If the checkpoints directory doesn't exist, create it

3. **Output format** for the markdown file:

```markdown
# Session Checkpoint

**Created**: [timestamp]
**Working Directory**: [current directory]

## Session Goal
[Brief description of what the user is trying to accomplish]

## Progress Summary
[Numbered list of completed tasks and milestones]

## Current State
[Description of where we are in the workflow]

## Key Decisions Made
[Important choices, configurations, or approaches decided]

## Files Modified/Created
[List of relevant files with brief descriptions]

## Pending Tasks
[What still needs to be done]

## Resume Context
[Technical details, commands, or context needed to continue work]

## Next Steps
[Suggested actions when resuming this session]
```

4. **Confirm** the checkpoint was saved and display the file path.

## User-Invocable

This skill can be invoked with `/ckpt` to save the current session state.
