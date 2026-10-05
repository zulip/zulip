---
name: commit-message
description: "Write a commit message following Zulip's format. Use whenever writing or rewording any commit message."
---

# Commit Message Format

```
subsystem: Summary in 72 characters or less.

The body says what a reviewer can't see in the diff: the problem,
why this fix is right, how you verified it, and why it won't break
things one might worry about.

Wrap lines at 70 characters or fewer, except URLs and verbatim
content (error messages, etc.).

Fixes #123.
```

## Writing the body

Don't list the files, functions, or tests you touched. Name a
function, setting, or endpoint only when the change is about it (a
rename, a move, a new helper, an API field), or when it explains a
bug. Don't guess at a reason; leave it out instead. Stop once the
reader knows what changed and why. Prefer a sentence or two. Write
more only when the change needs explaining. Small cleanups need no
body.

Common shapes:

- Bug fix: what was wrong, and in what case. What the user saw.
  Add "Fix this by ..." only if the fix isn't obvious from the
  summary. Then anything else that changed.
- Refactor: why it's better, and why behavior stays the same.
- Generated code: name the tool. Describe only where you deviated
  from its output.
- Part of a larger project: say so in one line.
- Prep commit: "This is a prep commit for the next commit."

For a bug, the summary names the bug, not the fix. Use the same
prefix as nearby commits in the same area.

The body is read once, with the summary:

- One idea per sentence. Don't join clauses with a colon.
- Say each thing once. Shorten a sentence by cutting words, not by
  splitting it in two.
- If the body is one long paragraph, split it in two.

Reread the body with the summary. Cut any sentence the reader could
get from the summary or the diff.

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
