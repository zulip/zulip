# CoreX AV2 — evidence and handoff

Date: 2026-11-08 (America/Guatemala). Status: implementation for review,
**acceptance blocked by missing runnable Zulip environment**.

## Verified baseline

- Fork: `https://github.com/cardenitass/zulip.git` (`origin`).
- Reference: `https://github.com/zulip/zulip.git` (`upstream`).
- Branch: `feature/7719-notify-without-subscribing`.
- Starting HEAD: `f0f02bcb08cb99ea161baec9a6c2edd008217dda`.
- Starting worktree: clean. No reset, overwrite, or rebase was needed:
  fetched `upstream/main` and `rev-list --left-right --count HEAD...upstream/main`
  returned `0 0`.
- Historical SHA supplied by the team:
  `46ed491f04a3b4f9cbabebeab7a3e2b437455851`; not used as a reset target.
- Tested state: uncommitted AV2 changes on the starting HEAD; no runtime-tested SHA.
  The eventual local commit identifier must be copied from `git rev-parse HEAD`
  after review. A commit is not evidence of passing tests.
- `pry_entregable2_CoreX.pdf`, C3-PSWE instructions, `docs/scope/project-scope.md`,
  and `docs/architecture/context.md` were not found. No academic budget,
  assignments, scope, or existing diagram was revised.

The GitHub connector read [issue #7719](https://github.com/zulip/zulip/issues/7719)
and its 15 comments. It remains open, assigned upstream to `Ashwin14101`;
the last reported update was 2026-10-31. There is overlapping implementation
planning in [this comment](https://github.com/zulip/zulip/issues/7719#issuecomment-6108983429).
No equivalent implementation was found in the fetched baseline. A GitHub PR
search for `repo:zulip/zulip 7719` found
[PR #40364](https://github.com/zulip/zulip/pull/40364), closed and **not merged**,
from `Varadskulkarni2005/zulip:issue-7719`. It overlaps in explicit selection,
send parameters and internal bot delivery. Its reported approach does not
describe the database uniqueness boundary required by this increment. Review
comments request upstream design discussion before contributing UI changes;
that conversation was not retrieved and upstream UX acceptance remains pending.
No comment, assignment, PR, or message was posted remotely.

## Environment and reproduction

Windows PowerShell; Python 3.12.15; Node 22.9.0; Docker client 24.0.6.
No provisioned virtualenv, Django, node_modules, Vagrant executable, or working
Linux development environment was found. `bash -lc 'uname -a'` reports WSL must
be updated. Docker initially could not read its config under the sandbox;
an approved external `docker info` confirmed the daemon pipe is absent.
The user confirmed Docker Desktop currently fails to start.

Baseline warning is **code-inspected**, not reproduced in a browser:
`warn_if_mentioning_unsubscribed_user`, the unsubscribed warning template,
and the subscribe handler in `compose_setup.ts`. They offered Subscribe where
authorized and warned that mentioning alone does not notify an unsubscribed user.

## Implementation and failure semantics

- New web composer only: explicit toggle, separate Subscribe action, translated
  strings and native keyboard-operable button with `aria-pressed`.
- Selection stays on the draft's recipient/channel banner, is pruned on removed
  mentions and deselected on recipient change, and clears on composer reset or
  cancel. An invalidation generation guards outstanding subscriber lookups.
- Selected IDs accompany the ordinary send request. Local echo retains the
  request selection for retry; saved drafts, scheduled sends, edits, group and
  wildcard mentions do not acquire notification intent.
- Server uses canonical Markdown, active same-realm recipient checks, current
  join permissions and existing message access checks. No subscription mutation.
- Original, unique delivery record and internal Notification Bot DM share an
  atomic transaction. Ineligible recipients are silently skipped without exposing
  metadata. Unexpected delivery failure rolls back the original too.
- Deduplication is per persisted message and recipient, not identical content or
  two distinct POSTs. Original row locking plus a database unique constraint
  handles concurrent delivery attempts. No external service or queue was added.

Architecture: [sequence diagram](../architecture/mention-notification.md),
[ADR](../architecture/adr-001-mention-notification.md).

## Commands and observed outcomes

Git read commands used `git -c safe.directory=C:/Code/CENFOTEC/zulip` because
checkout owner SID differs from the executing account. This per-command exception
does not modify global Git configuration. Initial plain Git commands failed with
`detected dubious ownership`; initial fetch failed writing `.git/FETCH_HEAD`.
The approved escalated fetch succeeded.

| Command | Actual outcome |
| --- | --- |
| `git ... status --short`, `branch --show-current`, `rev-parse HEAD`, `remote -v`, `log -5 --oneline` | Baseline above; clean initial worktree |
| `git ... fetch upstream main` | Succeeded after sandbox escalation |
| `git ... rev-list --left-right --count HEAD...upstream/main` | `0 0` |
| `docker info` outside sandbox | Failed: Docker daemon pipe not found |
| `bash -lc 'uname -a'` | Failed: WSL update required |
| `python tools/test-backend zerver.tests.test_mention_notification` | Blocked before collection: `ValueError: cannot find context for 'fork'` |
| `python tools/test-js-with-node compose_validate` | Blocked before collection: `ModuleNotFoundError: No module named 'pwd'` |
| `python tools/test-js-with-node compose.test.cjs compose_validate.test.cjs echo.test.cjs transmit.test.cjs` | Final focused attempt also blocked on `pwd` before collection |
| `python tools/lint zerver/actions/mention_notification.py` | Blocked before lint: `ModuleNotFoundError: No module named 'pwd'` |
| `python -c "import django; print(django.get_version())"` | Failed: Django not installed |
| `python tools/create-api-changelog` | Created `ZF-22b239.md`; automatic staging failed due Git ownership check; retained and filled the generated file |
| `python -m ruff check` on six affected Python files | Passed after correcting imports, unused binding, mutable default and context-manager formatting |
| `python -m ruff format` on those files | Applied formatting; not a substitute for Zulip lint |
| Python `ast.parse` on six affected Python files | Passed |
| `node --check` on `compose.test.cjs`, `compose_validate.test.cjs`, `lib/compose_banner.cjs` | Passed syntax checks only |
| `python tools/test-migrations` | Incorrect invocation of a Bash script; SyntaxError. Corrected with the command below |
| `bash -lc './tools/test-migrations'` | Blocked: WSL update required |
| `git ... diff --check` | Passed final static review |

No backend, Node, migration, browser, integration, or remote CI pass is claimed.
No concurrency result is claimed: the test uses real connections but has not run.
Mermaid rendering is unverified; no installed renderer was found.

## CA1–CA5 acceptance matrix

| Criterion | Automated evidence authored | Outcome / remaining verification |
| --- | --- | --- |
| CA1 explicit consent | `test_no_consent_and_no_actual_mention`; web eligibility additions; `notify_toggle_requires_explicit_action` in `compose.test.cjs` | Execution blocked; keyboard verification pending |
| CA2 correct bot DM and unchanged subscription | `test_explicit_delivery_and_retry` checks bot count, recipient receipt, link, quote, before/after subscriptions | Execution blocked |
| CA3 authorization | `test_ineligible_recipients`, private/revoked-access test, allowed private/web-public test, code/silent-mention negatives, permission revocation between send and delivery | Execution blocked; generic API non-disclosure response tests still needed |
| CA4 cancel/failure/retry/concurrency | Existing stale-banner removal tests; rollback/failure tests; real two-connection `test_concurrent_delivery` | Execution blocked; automated click/cancel/channel-reset lifecycle tests still needed |
| CA5 regressions and integration | Subscribed-mention receipt test; existing subscribe handler retained; walkthrough below | Execution blocked; full browser/server/bot walkthrough pending |

## Required supported-environment checks

Repair Docker Desktop or WSL and use the repository's documented Linux setup.
Provision with `./tools/provision`; never bypass the provision check. Then run:

```bash
./tools/test-backend zerver.tests.test_mention_notification
./tools/test-backend zerver.tests.test_message_send zerver.tests.test_openapi
./tools/test-js-with-node compose.test.cjs compose_validate.test.cjs echo.test.cjs transmit.test.cjs
./tools/lint web/src/compose.ts web/src/compose_setup.ts web/src/compose_validate.ts web/src/compose_recipient.ts web/src/echo.ts web/src/transmit.ts web/tests/compose_validate.test.cjs zerver/actions/mention_notification.py zerver/views/message_send.py zerver/models/messages.py zerver/models/__init__.py zerver/tests/test_mention_notification.py zerver/migrations/0816_mentionnotification.py zerver/openapi/zulip.yaml
./tools/test-migrations
```

Inspect each command's current `--help` before adjusting flags. The migration
must be applied and checked on supported PostgreSQL, not SQLite. Add coverage
execution of the new test module and inspect uncovered authorization branches.
Run the visual-test skill's Puppeteer workflow once the environment works.

## Reproducible browser → server → bot walkthrough (pending execution)

1. Start `./tools/run-dev`. Use two active same-organization non-guest accounts,
   author A and recipient B. Create a public channel readable by B, subscribe A
   only. Record B's subscriptions and current Notification Bot conversation count.
2. As A, mention B in a new channel message. Record the warning and available
   actions. Without selecting Notify, send. As B, verify no new bot DM.
3. Compose another individual mention. Tab to Notify, press Space, verify the
   selected label and `aria-pressed=true`. Before send, verify no new DM. Send.
4. As B, verify one Notification Bot DM, original-message link and quoted text.
   Follow the link and compare subscriptions with step 1; they must be unchanged.
5. Repeat with Notify selected, then delete the mention; with channel changed;
   and with compose cancelled/reopened. Send the new drafts and verify no stale DM.
6. Force an original-send rejection (e.g. revoke A's channel send permission),
   verify no DM, restore permission and retry the same failed message. Check that
   intent belongs to that failed local message. Sending a second original is a
   separate notification pair.
7. Exercise Subscribe separately where allowed, subscribed mentions, guests,
   private history-inaccessible channels, and a joinable private channel with
   public history. Revoke B's access before sending and verify silent skip.
8. Capture screenshots at 1920/1280/tablet/480 widths, light/dark, long names and
   translated strings, keyboard focus and simultaneous banners. Record actual
   account roles, channel policy, IDs, tested SHA, commands, counts and results.

## CI, traceability and metrics

Inherited `.github/workflows/zulip-ci.yml` triggers on `pull_request` and
`workflow_dispatch`; its test job is not restricted to `zulip/zulip` (only certain
failure-reporting steps are). Keep the existing workflow. The team must enable
Actions if required, publish the feature branch, open a PR **to the CoreX fork**,
inspect the Zulip CI matrix and attach run/job URLs and outcomes. No workflow
change, remote run, branch protection, review, or merge is claimed.

| Acceptance | Issue | Branch / commit | PR | Review | CI | Acceptance |
| --- | --- | --- | --- | --- | --- | --- |
| CA1–CA5 | [#7719](https://github.com/zulip/zulip/issues/7719) | `feature/7719-notify-without-subscribing`; commit pending | Pending team publication | Pending teammate review | Pending fork PR run | Pending runtime checks and remaining tests |

- M1: 0 criteria verified at runtime; 5 pending. This is not 5 passing criteria.
- M2: unauthorized delivery and subscription-change counts unmeasured.
- M3: delivery/duplicate counts unmeasured; expected one/zero must be measured.
- M4: manual before/after action counts unmeasured; walkthrough not executed.
- Cycle time and real cost: pending reliable team timestamps and accounting.

## Resumen para el PDF

Se implementó la selección explícita de Notify en mensajes nuevos de canales web,
con Subscribe separado, autorización en el servidor y entrega mediante el bot
interno. Se añadió una migración con unicidad por mensaje/destinatario y una
transacción común para el original y el DM. No se cambian suscripciones.
Se escribieron pruebas de consentimiento, permisos, regresión, rollback y
concurrencia real; **su ejecución está bloqueada**, no aprobada. Ruff y la revisión
estática no sustituyen esas pruebas. La desviación principal es el entorno:
Docker Desktop no inicia y WSL requiere actualización. Faltan pruebas de ciclo
de vida web, verificación visual, migración PostgreSQL y recorrido completo.
La secuencia y el ADR están en `docs/architecture/`. PR, revisión humana, CI,
capturas, métricas observadas y aceptación quedan pendientes del equipo.
