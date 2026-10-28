# Evals for the commit-message skill

These evals check whether a change to `../SKILL.md` makes agents
write better commit messages. Run them before changing the skill's
wording, and when a new model changes how agents write.

The cases are in `cases.txt`: 100 commits by Tim Abbott and Lauryn
Menard, written before they used AI tools. Half are from each
author. They cover bug fixes, refactors, docs, and migrations, and
range from no body to several paragraphs. The file says how they
were chosen.

There is no runner script here. This file gives the procedure and
both prompts, and an agent can write a short script from it in a few
minutes.

## Procedure

For each case, a writer model gets the skill and the commit's diff,
and writes a commit message. A judge model then scores that message
from 1 to 10 against the message the maintainer wrote.

1. Get the maintainer's message with `git log -1 --format=%B <hash>`.
2. Build the case's context, as four parts separated by blank lines:
   - If the maintainer's message has a `Fixes #123.` line: "This
     change resolves GitHub issue #123: {the issue's title}."
   - "The author's previous commits, newest first:" and the summary
     lines of the same author's three commits before this one.
   - "The author's next commits, oldest first:" and the summary lines
     of the same author's next three commits.
   - "The diff:" and the output of
     `git show --format= --stat --patch <hash>`.
3. Call the writer with the writer prompt below.
4. Call the judge with the judge prompt below as the system prompt.
   The user message is the context in `<change>` tags, the
   maintainer's message in `<human_message>` tags, and the writer's
   message in `<candidate_message>` tags. The reply ends with the
   score.

Each call must be a fresh model with no tools and none of this
repository's instructions or skills loaded. Otherwise the writer
follows the checked-in skill, not the one being tested.

Save every reply under `var/`, which Git ignores, so that a rerun
only does missing work. Read the saved messages, not only the
scores.

The writer sees only the diff, so it can't know why a change was
made unless the code shows it. The judge is told not to mark a
message down for that.

## Writer prompt

Replace `{skill}` with the full text of the skill file being tested,
and `{context}` with the case's context.

The system prompt:

```
You write git commit messages for the Zulip project.
Follow these instructions:

{skill}
```

The user message:

```
You just made the change below in the Zulip repository.
Write its commit message. Reply with only the commit message.

{context}
```

## Judge prompt

```
You are a Zulip maintainer with high standards for commit messages.
You get a change (diff and context), the message its human author
actually wrote, and a candidate message for the same change.

The human message shows the house style: how much to say, in what
order, and what to leave out. Don't punish the candidate for missing
a fact that only the author could know. Do punish it for:

- missing the change's main point, or its reason when that is known;
- inventing reasons or effects;
- opening with a function name instead of the idea in plain words;
- repeating the summary line, or re-explaining it in the body;
- details the reader can see in the code, such as parameters or
  tests updated to pass. Naming a function, file, or setting is fine
  when the change is about it (a rename, a move, a new helper, an
  API field) or when it explains the bug;
- terms that add nothing, like "attribute", or internal names;
- any word the message doesn't need. Wordiness is a real cost.

Score the candidate from 1 to 10:

- 10: as good as the human message; merge as is.
- 8: one or two small wording changes.
- 6: rewrite a sentence or two.
- 4: rewrite most of it.
- 2: start over.

Use odd numbers for in-between cases. Name the main problem in one
sentence, then on the last line give a JSON object like {"score": 7}.
```

## What to report

- The mean score.
- The median length: the words in the writer's message divided by
  the words in the maintainer's. Count the summary line in both.
- How often the writer added a body where the maintainer wrote none,
  and how often it left one out.
- Format problems: a summary over 72 characters or without the
  `area: Summary.` form, a body line over 70 characters, a dropped
  `Fixes #123.` line, or a trailer line.

## Reading the results

- Always run the old and new skill with the same models. Scores from
  different writer or judge models can't be compared.
- With one message per case, a gap under 0.3 on all the cases is
  noise. Write three messages per case on a small set to see how
  much one case varies.
- Start with 15 to 20 cases that your change should affect, plus a
  few it shouldn't. Run all 100 only for a change that looks good.
  A full run is 200 model calls.
- Watch the length. A higher score with much longer messages is
  usually worse.
- The judge is a rough guide. It can miss problems a person would
  catch, such as an invented term. See "Checking by hand".

## Checking by hand

The judge's score alone is not enough to accept a change. Have a
person who knows Zulip's commit style check a sample:

1. Pick 10 cases, spread over both authors and all body lengths.
2. Show the person one case at a time: the maintainer's message
   and the writer's message.
3. Ask for a score from 1 (would rewrite it) to 5 (would merge it
   as is), and what is wrong with the message.
4. Save the comments word for word. They show what to change in
   the skill better than any score does.
5. Compare the scores with the judge's. If the judge ranks the
   messages differently, fix the judge prompt before trusting it.

Use new cases for each round.

## Results so far

These used `claude-opus-5-5` as the writer, `claude-fable-5-1` as
the judge, and one message per case, on all 100 cases.

| Skill              | Score | Length |
| ------------------ | ----- | ------ |
| Before these evals | 5.7   | 3.1x   |
| Current            | 7.5   | 1.3x   |

Things the evals showed:

- Without "Prefer a sentence or two", short messages grew to two or
  three times the maintainer's length.
- A skill tuned with one model may not suit another. Run the evals
  again before using the skill with a different model.

## Known limits

- The skill writes a short body for most small commits where the
  maintainer wrote only a summary. Rewording the skill did not
  reduce this.
- About 1 message in 25 has a body that is not wrapped at all.
  gitlint catches these.
