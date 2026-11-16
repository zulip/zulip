---
name: write-security-advisory
description: "Draft or revise a GitHub security advisory for a Zulip vulnerability. Use whenever writing, reviewing, or editing advisory text, such as a GHSA or CVE description."
---

# Writing a Zulip security advisory

A security advisory is read by administrators deciding whether they're affected and
how urgently to upgrade. Every sentence should help that decision. Anything that only
matters to Zulip developers (how the fix works internally, data model history,
migrations, backfills) is noise, and gets cut in review.

Read `references/examples.md` before drafting: it has three advisories that show
the expected style. Match their tone, length, and structure.

## Before writing: verify the facts

Advisories get cited for years, so every factual claim must come from the code or git
history, not from a bug report or memory. Before drafting, establish:

- **Affected versions.** Find the introducing commit and run
  `git tag --contains <sha> | sort -V | head` for the first affected release, and
  `git tag -l '<major>.*' | sort -V | tail` for the latest release. Write the range as
  "Zulip Server X.Y through A.B". The fixed version is usually the next patch release
  of the stable branch, but confirm it with the user.
- **Who can trigger it.** Check the permission decorators and checks on the endpoint
  (e.g., `@require_realm_admin`, owner-only checks), and say which role is needed.
- **Every code path that leads to the vulnerable state.** E.g., if users can be deleted
  with or without their messages, the advisory has to be accurate for both cases.
- **Where a feature exists.** Code in `corporate/` (such as the `/activity/support`
  panel) only exists on Zulip Cloud, not on self-hosted servers.
- **User-facing names.** Use the names from the help center
  (`starlight_help/src/content/docs/`), e.g., "Public and private data (with consent)"
  export or "reusable invitation link", rather than internal names, except where
  Details explains the mechanism.

## Structure

Start the file with a `Title:` line, then the sections as `###` headings.

**Title.** Describe the behavior in plain language, as an admin would notice it.
"Sign-up via reusable invitation links skips single sign-on" is good;
"Fix missing check in HomepageForm" is not. If the attacker gains more than one
capability, the title should cover all of them, without overstating any.

**Summary.** Must work alone for triage. Say what an attacker can do, to whom, and under
which conditions. End with a severity sentence that names the preconditions that limit
it, e.g., "Severity is low: it requires a valid reusable invitation link, which only
administrators can create by default." If a precondition is rare, state the fact that
makes it rare (for example "User deletion isn't available in the Zulip apps…"), not a
guess like "deleted users are rare".

**Details.** The root cause: what the feature normally does, what went wrong, and why.
Naming functions and files is fine (`get_consented_user_ids` (`zerver/lib/export.py`)),
as is referencing an earlier CVE whose check was incomplete. Name an API endpoint
or parameter only when it's needed to explain the root cause. Don't include
reproduction steps or exploit scripts.

**Impact.** What the attacker gains, and from whom. List the conditions an
organization must meet to be affected, as bullets if there are several. If it helps,
say what the attacker does _not_ gain, e.g., "This is an integrity issue only". End with
the affected version range and then simply "This is fixed in Zulip Server X.Y." Leave out:

- how the fix works, migrations, or backfills;
- anything an admin can't act on.

**Severity** (optional, for serious issues). A CVSS score, plus a note when CVSS misses
the real-world impact.

**Workarounds** (only if a real one exists). A workaround must neutralize the bug
without upgrading, e.g., revoking reusable invitation links, or removing the configured
email domains. "Don't use the affected feature" is not a workaround. When there's no
real workaround, leave the section out entirely rather than writing "None" or a weak
mitigation.

**References** (optional). Links to relevant `https://zulip.com/help/...` articles,
with anchors where useful.

Don't credit the reporter in the body. GitHub's credit field handles that.

## Prose

Reviewers read every sentence closely. These are the most common problems in drafts:

- **Imprecise words.** "never allowed" when the accurate phrase is "had not allowed"
  (a user may have allowed it and later turned it off), or "messages of the deleted
  user" when some deletion paths remove them ("any remaining messages").
- **Inconsistent terms across sections.** If Details says the setting is "disabled",
  Impact must not say it was "reset".
- **Overloaded sentences.** One idea per sentence. Avoid tacked-on clauses
  ("…, even when …"), hedges ("generally"), and repeated words
  ("included … including").
- **Sentences that don't help an admin decide anything.** Delete them.

## Workflow

1. Verify the facts above and read `references/examples.md`.
2. Write the draft to a `.md` file in the repository root (e.g.,
   `advisory-<short-slug>.md`), so it can be copied into GitHub.
3. After the draft, briefly list anything the user should confirm: the fixed version,
   claims you couldn't fully verify, and places where the wording is a deliberate
   simplification (e.g., describing the common case when a rare case differs slightly).
4. When the user pastes their own tweaks, review them for accuracy and clarity and
   suggest specific replacement wording, but don't edit the file until they agree.
   When asked to fix something, change only that.
