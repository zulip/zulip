---
name: write-changelog
description: Update docs/overview/changelog.md with entries for changes since a base commit, in Zulip's curated changelog style.
argument-hint: "[base_commit]"
---

# Write Changelog

Surveys commits since a base point and folds user-facing entries into
`docs/overview/changelog.md` in the historical curated style. The hard
part is judgment — which commits matter to users, how tersely to phrase
them, and when to fold a refinement into an existing entry rather than
add a new bullet.

This tool is designed to replace a laborious manual

```bash
git log --stat <base>..upstream/main
```

not-taking process for identifying changes to consider recording in
the changelog.

## When to use

- An in-development major release (`### Zulip Server X.0` is
  `_Unreleased_`) needs its draft refreshed. Typical cadence: every
  1–4 weeks between betas.
- A maintenance release on a stable branch (e.g., `11.5` on
  `11.x`) is being prepared. Section shape and rules differ —
  see "Maintenance release mode" below.

## Workflow

### 1. Identify scope

Resolve the base commit (use the user's argument if given; otherwise
default to the last commit on `upstream/main` that materially touched
the changelog):

```bash
git log -10 --format=%H upstream/main -- docs/overview/changelog.md
```

If the base is a stable release tag (e.g., `11.4`), this is a
maintenance release — switch to "Maintenance release mode" below.

Read the existing in-progress section
(`### Zulip Server X.0` / `X.0-betaN`) end-to-end. The skill folds
new content into the existing organization rather than reinventing it.

The changelog for a beta is always a draft of the changelog of a final
release. So if the existing section is `### Zulip Server X.0-betaN`
and a new beta is being cut, **rename the heading and update the
`_Released_` date in place**, rather than adding new changes.

Check for a parallel maintenance release that may also have shipped
in the same window. List tags by date and look for any stable
release whose major version differs from the target's:

```bash
git for-each-ref --sort=creatordate --format='%(refname:short) %(creatordate:short)' 'refs/tags/*'
```

Changelogs for maintenance releases always enter the `main` branch via
cherry-picking from the original changelog on the maintenance release
branch.

### 2. Survey commits

Start with the commit list:

```bash
git log --stat <base>..upstream/main --format="%H %s"
```

Then walk these signal sources, in roughly decreasing reliability:

- **`api_docs/changelog.md` deltas.** For each new feature-level
  entry, ask: "Does this need a Full changelog bullet, an Upgrade
  note, both, or neither?" Keep in mind that sometimes, backend
  changes for an unfinished feature and merged months before the
  feature is completed.

  ```bash
  git diff <base>..upstream/main -- api_docs/changelog.md
  ```

- **Help-center source tree.** Newly-added articles signal newly
  documented features. The path varies by era: currently
  `starlight_help/src/content/docs/*.mdx`; pre-Starlight (≤9.x) it
  was `help/*.md` then `templates/zerver/help/*.md`. Help-center
  commits often land days to weeks after the underlying feature,
  so this can catch features whose original commit predates the
  base. Bulk migration deltas inside existing files are noise.

  ```bash
  git log --diff-filter=A --name-only <base>..upstream/main \
      -- starlight_help/ help/ templates/zerver/help/
  ```

- **`zulip_update_announcements.py`.** The in-app "what's new" feed is curated
  here; every new entry is a changelog highlight candidate.

  ```bash
  git diff <base>..upstream/main -- zerver/lib/zulip_update_announcements.py
  ```

- **Added, Removed, or greatly changed integrations.**

  ```bash
  git diff --stat <base>..upstream/main zerver/lib/integrations.py zerver/webhooks/*/*.{md,py}
  ```

- **CVEs are not detected mechanically.** They're managed manually
  by the security team and are essentially always backported. By
  the time a major release ships, the relevant CVEs are already
  documented in the maintenance changelogs that shipped during the
  cycle — cross-reference those rather than re-discovering. Ask the
  security team if anything is unclear.

For ambiguous commit subjects, read the body with `git show <sha>`.
Cluster commits sharing a `Fixes #N` reference; they often map to
one entry. For commits whose user impact is still unclear, consider
having a subagent follow links to GitHub issues or chat.zulip.org
threads.

### 3. Filter to user-facing changes

**Skip — almost never changelog material:**

- Refactors and prep commits ("Extract", "Refactor", "Move",
  "Inline"); pure typing refactors ("Replace `dict[str, Any]` with
  dataclass", "Use literal types").
- Test infrastructure (`tests:`, `test_X:`).
- Dev tooling and CI (`requirements:`, `dependencies:`, `lint:`,
  `mypy:`, `eslint:`, `ruff:`, `ci:`, `provision:`, `install-*:`,
  `Vagrantfile:`, `pre-commit:`).
- Translation / metadata churn (`locale/`, `mailmap`).
- `docs:` commits that fix typos, dead labels, or canonical-URL
  meta. _Include_ `docs:` commits that document a behavior change
  or improve developer-facing tooling (e.g., autogenerated Sphinx
  labels, new install-flag documentation).
- API capability commits whose `api_docs/changelog.md` entry
  preserves the legacy event/endpoint format. Protocol
  optimizations behind a client capability flag aren't user-facing
  and need only be documented in the separate API changelog.
- Migrations whose user-visible effect is described by a separate
  feature commit.
- Reverts of unreleased commits (and remove the original entry from
  the changelog if it had been added).
- **Same-cycle fixups.** A bug fix or small extension to a feature
  added in the same release does not get its own entry — the
  original feature entry already represents the work.
- **Visual polish fixups** ("Increase gap", "Vertically align",
  "Fix spacing", "Restyle border-radius"). Don't emit a per-commit
  entry; if there are enough such commits, roll them up into one
  umbrella bullet ("Fixed several visual polish issues across
  modals, popovers, …").
- Anything internal that doesn't impact the experience of users,
  organization administrators, or server administrators. A handful
  of major technical improvements or extended migrations can be
  highlighted at the end of the section.

**Include:**

- New user-visible features, redesigns, settings, search operators,
  keyboard shortcuts, Markdown syntax additions.
- New webhook integrations, or material changes to existing ones
  (new event types, silent-mention support, output rewrites).
- Performance work users will notice ("2x faster web app load in
  large organizations").
- Security/hardening: non-CVE hardening (e.g., a dependency upgrade
  closing a low-severity issue, an XSS-resistance audit) lands as a
  short Improved/Hardened bullet in the Full feature changelog.
  CVEs use the dedicated format in "Maintenance release mode".
- Platform support changes (added/removed OS, Postgres,
  Python major versions).
- API/settings changes that might require a system administrator to update
  common classes of integrations with their Zulip server.
- Themed-cluster rollups: when many small improvements share an
  area, group them under one bullet — e.g., "Fixed several visual
  polish issues across modals, popovers, the saved-snippets
  dropdown, stream-privacy decoration, recent-view headers, and
  subscriber-list scrolling." (12.0-beta2) captures 10+ commits no
  one individually merits. The shape is "Fixed/Improved several X
  across A, B, C, …".

When in doubt: "can you imagine a user or administrator who would be
sad if this commit were silently reverted before release?" If no,
skip.

### 4. Draft Full feature changelog entries

(Skip in maintenance mode — that has its own ordering, see below.)

For each candidate, decide: **new entry**, **fold into an existing
entry**, or **skip**. Prefer folding when the new commit refines,
extends, or parallels something already covered (see "Folding
rules" below).

Group entries by the loose ordering used in existing sections:
Added → Redesigned → Improved → Renamed → (clusters in a subsystem) →
Integrations → Fixed → Performance/Security/Infrastructure. Slot each
new entry near existing entries of the same shape or adjacent
topic; don't append to the end of the list.

**Important behavior changes that don't cleanly fit any of the
above categories** can go _before_ the "Added" section as a small
lead cluster. The 11.0 section is the canonical example: it opens
with bullets like "The compose box now offers to convert large
amounts of pasted text into an uploaded file.", "Policies for
automatically following topics they initiate are now applied
when…", "Notices generated by moving messages are now always
marked as read for the acting user.", "Email notifications and
Notification Bot now use topic permalinks." Each names a behavior
change too narrative-weighted for "Added"/"Improved" but that the
reader needs to know up front.

**After drafting, scan for umbrella opportunities.** When 4+
commits cluster in one subsystem (`webhooks/*`, `compose:`,
`portico:`) and were individually skipped or look thin on their own,
write a single rollup bullet ("Improved many webhook integrations,
including Travis CI…, PagerDuty…, Jira…").

### 5. Promote Highlights

A new entry belongs in `#### Highlights` if it's one of:

- A top-level user-visible feature (a new view, compose mode, auth
  backend, media format, major settings panel).
- A redesign large enough that screenshots would change.
- An infrastructure change with broad self-hoster impact (new OS
  support, Postgres major version, Docker container rework).
- A protocol or security milestone (e.g., E2EE push notifications
  becoming generally available).
- Anything else that could reasonably change whether a reader
  is interested in choosing Zulip over alternative chat systems.

For each candidate:

- **Check the existing Highlights first.** for whether an existing
  highlight should be extended.
- **Move** (don't duplicate) the entry from the full list to
  `#### Highlights`. Sub-features that expand on the highlight stay
  in the full list, unless they flow naturally as a second sentence.
- Expand it slightly: Highlights are 1–3 sentences and can
  include some context.
- **Pattern-match for prominence level.** Find the most-similar
  existing Highlight (across all past releases) and match it.
- A newly-added help-center article (see Step 2's path list) often
  confirms a feature meets the bar.

When polishing existing Highlights (Step 8), aim for the same length
or shorter, not adding clarifying detail on each addition.

When uncertain, leave the entry in the full list and note it as a
Highlights candidate in the summary.

### 6. Propose Upgrade notes

Upgrade notes go under `### Upgrade notes for X.0`. Most runs find
none — that's normal. Propose one when the delta contains:

- A removed or renamed setting in `zproject/*settings.py`.
- A required setting that previously had a default, or a default
  changed in a way that affects behavior.
- A removed installation platform or dropped Postgres / Python /
  Node major version.
- Any other change that could be reasonably expected to require some
  system administrators to take manual action as part of the upgrade.
- A migration expected to take a long time on large installations,
  or any command admins must run manually.

Detection is mechanical, not abstract:

```bash
# Settings template — the server administrator's config file. Note many
# changes in inline comment documentation require no action.
git diff <base>..upstream/main -- \
    zproject/default_settings.py \
    zproject/prod_settings_template.py \
    zproject/computed_settings.py

# Removed config / scripts / puppet directories.
git log --diff-filter=D --name-status <base>..upstream/main -- \
    'puppet/' 'scripts/' 'zproject/'

# Subject-line signals (kept narrow because broader patterns add
# false positives faster than they catch true positives).
git log <base>..upstream/main \
    --grep='Remove .* support' \
    --grep='no longer support' -i
```

Treat any net removal from `prod_settings_template.py` as an
upgrade note candidate by default.

When drafting, mirror historical Upgrade notes style: link to the
relevant operations doc, name affected settings in backticks, and
tell the admin what concrete action to take.

### 7. Place entries

Edit `docs/overview/changelog.md` directly. When folding, edit the
existing bullet in place rather than adding a new one.

**Redundancy check before each new entry.** Grep the existing
target section for the feature/integration name; if something
matches, default to fold or skip. This catches commits whose
subjects look like new-feature additions but actually document or
extend something already in the changelog.

### 8. Verify

Re-read the full updated section once for:

- Duplicate or near-duplicate entries (dedupe pre-existing ones too
  — the previous draft sometimes has them).
- **Highlights vs. Full feature changelog dedupe.** No bullet
  should appear in both. (11.0's "Migrated translation platform
  from Transifex to Weblate" was a real historical case where it
  ended up in both.)
- Grammar, typos, missing periods.
- Operator and syntax formatting (operators with their colon, e.g.,
  `mentions:`, `is:followed`; settings in backticks).
- Compound entries that should split, or sibling entries that
  should fold.
- Style consistency with the last few releases' sections.

**Polish pass.** Re-read each existing bullet you didn't touch and
copyedit obvious infelicities.

**Retraction check** — look for commits walking back prior claims:

```bash
git log <base>..upstream/main --grep='retract\|walk back\|incorrectly\|never shipped' -i
```

If a feature was claimed in the previous draft but reverted or
scoped down, edit or remove the prior entry — don't leave it stale.

Then:

```bash
./tools/lint --fix docs/overview/changelog.md
```

Report a summary: candidate commits surveyed, entries added/folded,
Highlights or Upgrade notes proposed, parallel maintenance release
section if any. Include interesting choices — places where rules
conflicted or you weren't sure what was accurate.

## Style rules

When uncertain, find the closest existing bullet in the file and
mimic it.

- **One sentence per entry**, two only when truly necessary
  (e.g., a redesign with multiple aspects worth naming).
- **Active voice.** Start with `Added`, `Improved`, `Redesigned`,
  `Renamed`, `Removed`, `Fixed`, or a noun-phrase ("The Markdown
  process now…", "Channel privacy icons now appear…"). End with a
  period.
- **No commit-message-style justification.** Don't say "matching
  Y" or "(Fixes #N)". State _what_ changed, not _why_. Use
  "previously…" only when the prior behavior is itself the
  user-visible point of the bullet (e.g., 11.0's "Topic permalinks
  now consistently prefer the latest message in a topic for
  anchoring; previously, the oldest message was sometimes used.")
  — not as bare commit-message justification for a change.
- **No exhaustive enumeration.** "Many event types" beats listing
  five of them.
- **Technical names in backticks.** Operators with their colon
  (`mentions:`, `is:followed`); settings, file types, env vars in
  backticks. Use `(e.g., ...)` (lowercase, with periods).
- **Avoid colloquial words** that don't fit the documentation's
  professional tone. Don't speculate about backports or future
  releases — flag those for the user instead.
- **Wrap at ~70 chars** except links and long identifiers.
- **Be precise.** Double-check implicatures — e.g., naming "a new
  type of GitHub integration" shouldn't suggest there was no prior
  GitHub integration.
- Linking to the Help Center on zulip.com or ReadTheDocs via
  relative links is welcome (historical entries don't because of
  time pressure, not policy).
- Use of Zulip standard terminology and readability for a sysadmin
  who has never look at the Zulip implementation. Highlights
  should use user-facing terminology like the help center does.

## Folding rules

When a new commit refines or extends an existing entry, edit that
entry in place. Examples from the `12.0-beta2` tag:

- KLIPY GIF provider → folded into the existing GIF picker
  redesign as "Giphy, Tenor, and KLIPY".
- GIF picker resize → folded into the same redesign as "with nice
  keyboard UI, a resizable popover, and…".
- Integrations catalog and integration doc page redesigns →
  folded into the existing API/legal docs redesign entry.
- SAML `full_name` sync → appended onto the existing SAML email-
  sync entry as a second sentence.
- LDAP email-sync extended to periodic `sync_ldap_user_data` runs
  → appended onto the existing LDAP/SAML email-sync entry rather
  than written as a parallel bullet. (When an X-on-event feature
  gets a Y-on-other-event follow-up, write one bullet covering both.)
- Mattermost importer gaining bot/self-DM/multi-team support →
  folded onto the existing data-import-tools entry as a second
  sentence ("…The Mattermost importer now supports combining
  multiple teams, importing bot users, and self-DMs.").
- Removed-integrations cluster (Hubot, Dark Sky, Codeship-as-legacy
  in 12.0-beta2) → folded into the existing "Removed several
  integrations…" parenthetical list rather than as new bullets.
  **Only fold removals that share both subsystem path AND feature
  category** — e.g., webhook removals fold together; data-import
  tool removals fold together; don't mix the two (Gitter's data
  import tool removal does _not_ fold into a webhook list).
- Operational-follow-up fold: when a bug-fix commit lands together
  with a follow-up that adds a cron job, retry, validation, or
  detection tool guarding the same class of bug, fold the follow-up
  as a second sentence on the originating fix. The 11.1
  subscriber-count bullet is the canonical example: "Fixed
  subscriber counts after data import being incorrect in the
  database, which could cause removing channel subscribers to
  crash after a data import. Also added a daily refresh to cached
  subscriber counts, in case of race conditions."

**When NOT to fold:** if no existing entry names the feature area,
write a new bullet. E.g., Discord auth got its own bullet in
12.0-beta2 because no prior auth-backend bullet covered it. The
folding rule is "look for a home" not "always fold."

**Within-subsystem rollup.** When 4+ commits each lightly improve
distinct items in one subsystem (e.g., five separate webhook
integrations each getting 2–3 polish commits), write one rollup
bullet listing the affected items parenthetically — see the
12.0-beta2 webhook entry: "Improved many webhook integrations,
including Travis CI (…), PagerDuty (…), Jira (…), GitLab (…), and
Harbor (…)." Several consecutive refactor commits that appear
to be from a single pull request should not be treated as
distinct items.

The general pattern: if there's already an entry that names the
feature area, look for a way to grow it before writing a new bullet.
It's often necessary to remove less important details when folding to
preserve the overall level of conciseness of the entry.

## Maintenance release mode

When the base is a stable release tag (e.g., `11.4`), the workflow
runs but with several differences. **10.3 is the strongest single
exemplar** to compare against — it has a clear non-XSS CVE bullet,
a "Fixed an important bug where…" admin-impact phrasing, and
infrastructure tooling bullets at the right granularity. 11.5, 11.6,
and 10.4 are useful secondary references.

**Section shape:** add `### Zulip Server N.M` under
`## Zulip Server N.x series` — no `#### Highlights`, no
`#### Full feature changelog`. Body is a flat bulleted list with
`_Released YYYY-MM-DD_` (or `_Unreleased_` while drafting).

**Survey range:** the stable branch, not `upstream/main`:

```bash
git log <prev-stable-tag>..stable-N --format="%H %s"
```

`api_docs/changelog.md` will typically be empty for this range —
that's expected, _not_ a signal nothing is user-facing.

**Ordering:** CVEs first, then user-visible fixes (web/mobile,
email/imports), then self-hosting and infrastructure, then
translations. CVE entries describe the _vulnerability_, not the
fix — e.g., from 10.3, "CVE-2025-47930: Restrictions on creating
public or private channels were incorrectly not applied when
editing the channel type for an existing channel. This issue only
impacted configurations where users could create private channels
but not public channels, or vice versa." Note any required user
interaction; credit reporters when commit metadata names them.

**Same-release fix analysis.** Compare against the previous
maintenance release within this major release series. Ask "would a
self-hoster running N.M-1 notice this?".

**CVE absorbs same-CVE hardening.** Backport commits that fix or
harden the same vulnerability as a CVE entry fold into that CVE
bullet rather than getting their own entry. Look for shared CVE
numbers in commit messages, or path-traversal/sanitize/XSS commits
clustered in time around the CVE-numbered commit.

**Splitter, not lumper, but with judgment.** Distinct bugs go in
distinct bullets — admins skim for the issue they hit. The folding
rules above are for major-release narrative flow; maintenance
changelogs are reference material. But the splitter rule is
_not_ "include everything you don't fold"; the
"would a self-hoster on N.M-1 actually notice and care" gut-check
still suppresses small internal Puppet refactors, dev-tooling
cleanups, etc. Several small fixes touching the same widget
across one cycle (`stream_list:`, `channel_folders:`, sidebar tweaks)
usually fold into a single "Fixed several bugs in the channel list
sidebar" bullet rather than three thin entries.

**Tone:** descriptive — "Fixed X.", "Improved Y.", "Updated Z." —
minimal prose, name affected settings in backticks, mention exact
subsystem (`postfix`, `setup-certbot`, `nginx`, `S3`, the email
gateway). Slightly more admin-facing detail than major-release
entries.

Upgrade notes are rare in maintenance releases (backports usually
preserve compatibility) but possible. Apply Step 6's commands; expect
zero hits most of the time.

## Final notes

Report to the user notes on any changelog items that might need
follow-up work or documentation before we can happily advertise them
in a release blog post. Report to the user any changelog items that
should perhaps be advertised in landing pages
(`templates/corporate/`).
