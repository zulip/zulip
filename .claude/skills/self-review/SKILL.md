---
name: self-review
description: "Zulip's self-review checklist. Use when you believe a branch is complete, before presenting the work or opening a PR."
---

# Self-Review Checklist

Before finalizing, verify:

- [ ] The PR addresses all points described in the issue
- [ ] All relevant tests pass locally
- [ ] Code follows existing patterns in the codebase
- [ ] Names (functions, variables, tests) are clear and greppable
- [ ] Commit messages, comments, and PR description are well done.
- [ ] Each commit is a minimal coherent idea
- [ ] No debugging code or unnecessary comments remain
- [ ] Type annotations are complete and correct
- [ ] User-facing strings are tagged for translation
- [ ] User-facing error messages are clear and actionable
- [ ] No secrets or credentials are hardcoded
- [ ] Documentation is updated if behavior changes
- [ ] Refactoring is complete (`git grep` for remaining occurrences)
- [ ] Security audit of changes. Always check for XSS in UI changes
      and for incorrect access control in server changes.

Always output a recommend pull request summary+description that
follow's Zulip's guidelines once you finish preparing a series of
commits.
