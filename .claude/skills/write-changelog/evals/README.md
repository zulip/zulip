# Evals for the write-changelog skill

These evals check whether a change to `../SKILL.md` makes agents
write better changelog entries. Run them before changing the skill's
wording, and when a new model changes how agents write.

The cases are six past maintenance releases: 8.1, 8.3, 9.2, 10.1,
11.1 and 11.5. Each has 83 to 110 commits and 17 to 33 published
entries. For each one, an agent drafts the release's changelog
section from its commits, and the draft is compared with the section
the maintainers published.

Parts of the 11.0 and 10.0 development cycles are cases too:
`481f7ca4eb..11.0-beta1`, `11.0-beta1..11.0-beta2`,
`11.0-beta2..11.0`, `1031a97d0c..10.0-beta1`,
`10.0-beta1..10.0-beta2` and `10.0-beta2..10.0`.

There is no runner script and no saved data here. This file gives
the procedure and the prompts.

## Procedure

The steps use 11.1 as the example. Its base is `11.0`, the release
before it.

1. Get the published entries: the bullets under
   `### Zulip Server 11.1` in `docs/overview/changelog.md`.
2. Make a copy of the repository, outside this checkout, where the
   commits from 11.0 to 11.1 leave the changelog file as it was in
   11.0, and no branch or tag is newer than 11.0. The drafter must
   not be able to find the published section.
3. Draft. Start an agent in a fresh clone of that copy with the
   draft prompt below. It needs to run `git`, read and edit files,
   and start subagents. The draft's entries are the bullets of the
   section it adds.
4. Match the draft to the published entries, by calling a model with
   the match prompt below.
5. Compare the wording of the old and new skill. Take each published
   entry that both drafts cover, and call a model with the wording
   prompt below, with the two drafted entries in random order.
6. Check accuracy. For each draft entry, start a read-only agent in
   a fresh clone with the accuracy prompt below. An entry it does
   not call accurate is flagged.

For a part of a major release, the base is the start of its range.
The entries, published and drafted, are the bullets added or
reworded in the range. Report new and reworded bullets apart.

Each call must be a fresh session with web search turned off, and
with none of the checkout's instructions or skills loaded. Otherwise
the drafter can read the published changelog on the web, or follow a
copy of the skill in the checkout.

Each prompt below is the whole user message. In all of them,
`{release}` is `11.1` and `{base}` is `11.0`. For a part of 11.0,
`{version}` is `11.0`, `{base}` is the start of its range, and
`{history_base}` is `10.0`. The models in steps 4 and 5 get no
tools.

Save every reply, so that a rerun only does missing work. Read the
drafted entries, not only the numbers.

## Draft prompt

Replace `{skill}` with the full text of the skill file being tested,
and `{branch}` with `11.x`.

```
You are preparing the changelog for the next maintenance release,
Zulip Server {release}. The `{branch}` release branch is checked out
in the current directory, and the previous release is the tag
`{base}`.

Follow the write-changelog skill below with base `{base}`. Notes for
this checkout:

- There is no `upstream` remote and no `stable-N` ref. `HEAD` is the
  tip of the release branch, so the commits to survey are
  `git log {base}..HEAD`.
- Add the new section to `docs/overview/changelog.md` as
  `### Zulip Server {release}` with `_Unreleased_`.
- Do not run `./tools/lint`; this checkout is not provisioned.
- Nobody is available to answer questions. Make your best call and
  finish with the summary the skill asks for.

<skill>
{skill}
</skill>
```

For a part of 11.0 or 10.0:

```
You are refreshing the draft changelog for Zulip Server {version},
which is in development. The `main` branch is checked out in the
current directory. The {version} section of
`docs/overview/changelog.md` was last updated at commit `{base}`.

Follow the write-changelog skill below with base `{base}`. Notes for
this checkout:

- There is no `upstream` remote. `HEAD` is the tip of `main`, so the
  commits to survey are `git log {base}..HEAD`.
- No release is being cut right now. Do not rename the section
  heading or change its release date.
- Do not run `./tools/lint`; this checkout is not provisioned.
- Nobody is available to answer questions. Make your best call and
  finish with the summary the skill asks for.

<skill>
{skill}
</skill>
```

## Match prompt

Replace `{published}` and `{draft}` with the two lists of entries,
each numbered from 0.

```
Below are two sets of changelog entries for the same Zulip Server
release, {release}. The PUBLISHED section is what the maintainers
shipped. The DRAFT section was written independently from the same
commits.

For each published entry, list the draft entries that cover the same
change. One draft entry may cover several published entries, and the
reverse. Do not check facts against code.

Reply with only a JSON object:

{"published": [{"index": 0, "covered_by": [<draft indexes>]}, ...]}

PUBLISHED:

{published}

DRAFT:

{draft}
```

## Wording prompt

Replace `{items}` with the pairs for one release, numbered from 0.
Each is three lines: `PUBLISHED:` with the published entry, then
`A:` and `B:` with the two drafted entries. Keep a note of which
skill wrote A.

```
Below are changelog entries for Zulip Server {release}. Each item
has the entry the maintainers PUBLISHED for a change, and two
candidate entries, A and B, written independently for the same
change.

For each item, decide which candidate reads more like an entry the
maintainers would have written for this changelog. Judge wording
only: length, level of detail, how the change is framed (what a user
or administrator sees, versus internal components), terminology, and
tone. Use the published entry as the standard. Do not check facts,
and do not reward a candidate for containing more information than
the published entry has.

Answer "A", "B", or "tie" (use "tie" only when you cannot choose).
For the candidate that lost, name its main defect with one of these
labels:

- long: too long or too detailed for this changelog
- mechanism: explains how the bug happened or how it was fixed
- internal: uses internal names or frames the change by an internal
  component
- vague: too vague to tell what changed
- scope: describes a noticeably different or broader/narrower change
  than the published entry
- phrasing: awkward, or reads like a commit message
- none: both are fine

Reply with only a JSON object:

{"items": [{"index": 0, "winner": "A" | "B" | "tie",
            "defect": "<label>"}, ...]}

ITEMS:

{items}
```

## Accuracy prompt

Replace `{entry}` with one draft entry.

```
You are auditing one entry from the changelog of Zulip Server
{release}, a maintenance release.

The repository in the current directory is checked out at the
release. The changes in the release are the commits in
`git log {base}..HEAD`. The changelog file has not been updated for
this release, so do not look there for the answer.

The entry:

<entry>
{entry}
</entry>

Your job is to decide whether the entry tells a reader the truth
about what changed. Changelog entries are often written by someone
skimming commit subjects, and the usual failure is an entry that
sounds right but misstates a detail. Do the work to find out:

1. Find the commit or commits the entry describes. Search the commit
   list, and read commit messages and diffs until you are sure which
   ones it is.
2. Read those diffs in full, and enough of the surrounding code to
   understand how the software behaved before and after.
3. List every factual claim the entry makes or implies. For a bug
   fix: what the user-visible symptom was, how severe it was, who or
   which configurations were affected, under what conditions it
   happened, and what the fix does. For a feature or behavior
   change: what it does, where, and for whom.
4. Check each claim against the code.

Verdicts:

- `accurate`: every claim is supported. A reader would come away
  with a correct picture.
- `subtly_wrong`: the entry is about a real change in that history,
  but a reader would be misled about some detail. Examples: calling
  a page that fails to load a "crash"; saying all users were
  affected when only imported organizations were; naming the wrong
  symptom, cause, or trigger; overstating or understating what the
  fix covers; a detail the commits neither support nor contradict.
- `wrong`: the entry describes something that did not happen in that
  history, or you cannot find any commit it could be about.

A claim counts as supported only if the code or the commit message
shows it. Do not give the entry the benefit of the doubt: an effect
that is merely plausible (for example, that a missing limit could
"crash the server") is unsupported unless the commits show it, and
an unsupported claim about symptom, severity, scope, or trigger
makes the entry `subtly_wrong`.

Ignore reporter credits, advisory or CVE identifiers, and release
dates; they cannot be checked from the repository. There is no
network access, so do not try to look anything up.

When the verdict is not `accurate`, also say how much it matters:

- `material`: a reader would get a wrong idea of what the bug or
  change was, how bad it was, or whether it affected them. A
  maintainer proofreading the changelog would want it corrected.
- `minor`: technically imprecise, but a reader's picture is
  essentially right (for example, the fix also covers a closely
  related case the entry doesn't mention).

Judge accuracy only. Do not mark an entry down for style, for being
brief or general, or for leaving out detail, unless the omission
makes what remains misleading. Whether the change deserved an entry
is not your concern.

End your reply with a JSON object, and nothing after it:

{"commits": ["<short sha>", ...],
 "verdict": "accurate|subtly_wrong|wrong",
 "impact": "material|minor|none",
 "problem": "<one sentence naming the misleading claim, or empty>",
 "corrected": "<the entry rewritten to be accurate, or empty>"}
```

For a part of 11.0 or 10.0, replace the two paragraphs before "The
entry:" with:

```
You are auditing one entry from the draft changelog for Zulip Server
{version}, which is in development on the `main` branch.

The repository in the current directory is checked out at `main`.
The entry was just added or reworded to cover the commits in
`git log {base}..HEAD`, but it may also describe earlier work on the
same feature, so treat everything in
`git log {history_base}..HEAD` as the history it can describe. The
changelog file is a draft, so do not treat it as evidence.
```

## What to report

- Flagged: the share of draft entries that were flagged in step 6.
- Length: the median number of words in a draft entry, next to the
  same number for the published entries.
- Wording wins: how often the new skill's entry was picked over the
  old skill's. Count a tie as half a win.

## Reading the results

- Always run the old and new skill with the same models. Numbers
  from different models can't be compared.
- Compare flagged rates only with each other. The accuracy checker
  flags about 1 in 5 of the published entries too.
- One draft of one release is noise. Add up the six releases. A
  second set of drafts by the same skill won 49% of the wording
  comparisons, and its flagged rate was 1.5 points apart.
- Check wording first. Accuracy takes one agent session per entry.
- The checker is a rough guide. Have a person who knows the code
  read a sample of flagged and unflagged entries before accepting a
  change.
