---
name: pr-description
description: "Write a pull request description following Zulip's guidelines. Use when opening a pull request or drafting/revising its title or description."
---

# PR Descriptions

Output the PR description in a markdown code block so that formatting
(bold, headers, checkboxes, etc.) copy-pastes correctly into GitHub.

## A PR description should:

1. Start with a `Fixes: #...` line linking the issue being addressed.
2. Explain **why** the change is needed, not just what changed.
3. Describe how you tested the change, using checkbox format for the
   test plan (e.g., `- [x] ./tools/test-backend ...`).
4. Include screenshots for UI changes.
5. Link to relevant issues or discussions.
6. Call out any open questions, concerns, or decisions you are uncertain
   about, so they can be resolved during review.
7. Include the self-review checklist from
   `.github/pull_request_template.md` using checkbox format (`- [x]` /
   `- [ ]`), checking off all applicable items.

## A PR description should not:

- Regurgitate information visible from the diff
- Make claims you haven't double-checked
- Express more certainty than is justified given the evidence
