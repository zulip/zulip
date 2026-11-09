# AI assistance — CoreX AV2

- Tool: OpenAI Codex, local workspace and connected GitHub read tools.
- Date: 2026-11-08 (America/Guatemala).
- Objective: implement the second-deliverable increment for Zulip #7719.
- Prompt reference: the team's task in this Codex conversation beginning
  “Implement the CoreX second-deliverable increment for Zulip issue #7719”,
  including CA1–CA5, architecture, evidence and publishing restrictions.
- Human review: **pending**. No teammate review or acceptance is implied.

Validation continued on 2026-11-09 after the user reported Docker working.
The agent provisioned the official Linux CI image, executed backend and Node
tests, corrected a transaction regression, OpenAPI encoding, migration field
type, test cleanup and active-user detection, and added a Puppeteer integration
test. The 134-test backend run includes a real two-connection race. The complete
Node suite and migration consistency checks passed. Mermaid CLI rendered the
sequence. Browser integration exposed a remaining keyboard-selection assertion
and is pending a rerun with corrected session focus and event waiting. Source
inspection then identified the global Space hotkey intercepting banner buttons.
A localized handler and regression test preserve native activation of both
mention actions. This final web change awaits execution and final lint.

Commands and outcomes from the continuation are recorded in the resumed
validation section of the evidence document. Docker-dependent checks were paused
after the latest synchronization/execution approval request was rejected. The
agent requested clarification before continuing those actions.

Affected areas: compose warning templates and validation/setup/send/recipient
lifecycle; local echo and transmit request types; send endpoint; new internal
notification action; unique delivery model and migration; backend and web tests;
OpenAPI and generated unmerged API changelog; help article; architecture and
evidence documentation. See the scoped diff for the exact file list.

Decisions requiring human validation: synchronous atomic delivery and its
latency; silently skipping newly ineligible recipients; current private-channel
join/access semantics; rollback of the original on unexpected DM failure;
database race-test correctness; no subscriptions changed; accessibility and
composer lifecycle, including retries and scheduled-message exclusion.

Commands and actual results, baseline, environment, test blockers, metrics,
traceability and the Spanish PDF handoff are recorded in
[docs/evidence/av2.md](evidence/av2.md). Source inspection used `rg`, `Get-Content`,
Git status/log/diff/remotes and file inventory. Static checking used Python Ruff
on the six affected Python files. Repository tests and lint were attempted using
the actual scripts and failed before collection on Windows. The generated API
changelog helper ran; its automatic Git staging failed. No dependencies or
provision checks were bypassed. No credentials or private test data are included.

No AI-generated messages were sent to Zulip development chat. No GitHub issue
comment, PR, review, CI trigger, push, or merge was performed. The team must read,
understand and test this work before submitting it, per Zulip's AI use policy.
