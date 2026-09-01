---
name: commit-message
description: "Write a commit message following Zulip's format. Use whenever writing or rewording any commit message."
---

# Commit Message Format

```
subsystem: Summary in 72 characters or less.

The body explains why and how. Include context that helps reviewers
and future developers understand your reasoning, analysis, and
verification of the work above and beyond CI, without repeating
details already well presented in the commit metadata (filenames,
etc.). Explain what the change accomplishes and why it won't break
things one might worry about.

Line-wrap at 68-70 characters, except URLs and verbatim content
(error messages, etc.).

Fixes #123.
```

## Commit summary format

- Before the colon is a lower-case brief gesture at subsystem (ex: "nginx" config) or
  feature (ex: "compose" for the compose box) being modified.
- Use a period at the end of the summary
- Example: `compose: Fix cursor position after emoji insertion.`
- Example: `nginx: Refactor immutable cache headers.`
- Bad examples: `Fix bug`, `Update code`, `gather_subscriptions was broken`

## Linking issues

- `Fixes #123.` - Automatically closes the issue
- `Fixes part of #123.` - Does not close (for partial fixes)
- In a multi-commit PR, use `Fixes part of #123.` in earlier commits
  and `Fixes #123.` in the final commit.
- Never: `Partially fixes #123.` (GitHub ignores "partially")
