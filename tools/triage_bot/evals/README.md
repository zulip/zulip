# Evals for the triage bot

These evals check whether a change to the bot's prompt, its input, or
its model gives better triage cards. Run them before changing
`../prompt.md` or `../assemble.py`, and before switching to a new
model.

The evals picked Opus over Sonnet as the bot's model. They also
picked the current `../prompt.md` and the input layout in
`../assemble.py`.

The cases are in `cases.txt`: 54 issues and PRs from zulip/zulip,
opened between February and October 2026. The file says how they
were chosen.

There is no runner script here. This file gives the procedure and
the prompts, and an agent can write the scripts from it.

## Procedure

Each case is replayed as of a cutoff: 5 minutes after the item was
opened, or after a draft PR was marked ready. A bot model writes a
card from what was known then. A judge model then scores the card
against what maintainers later did with the item.

1. Gather the item twice with the lookups in `../gather.py`:
   - As of the cutoff, for the bot. Use the description as it was
     then, only comments and CZO messages from before the cutoff,
     labels and assignees rebuilt from timeline events, and only
     similar items and author history from before the cutoff. Use
     CI results only if the head commit at the cutoff is still the
     head. Otherwise, say that CI is unknown.
   - With no cutoff, for the judge. This includes everything that
     happened later.
2. Build the bot input from the cutoff data with `../assemble.py`.
3. Build the answer key once per case, with the key-facts prompt
   below. The key-facts model reads both gatherings. Save the keys
   and reuse them, so that every judge call scores against the same
   targets. Spot-check a few keys by hand before using them.
4. Call the bot model with `../prompt.md` as the system prompt and
   the input as the user message, as `../triage_bot.py` does.
5. Call the judge with the judge prompt below. It sees all the
   cards for one case at once, under random letters and in random
   order. Keep the mapping from letters to configurations in a file
   the judge never sees. Show identical cards only once, and copy
   the score back to each.
6. Judge each case twice, with a different order and letters each
   time, and average the two.

Each call must be a fresh model with no tools and none of this
repository's instructions or skills loaded.

Save every input, card, key, and judgment under the repository's
`var/` directory, which Git ignores, so that a rerun only does
missing work. Read the cards and the judges' reasons, not only the
scores.

Items by maintainers are left out of the cases. The bot writes their
card without the model, so they say nothing about the prompt.

## Key-facts prompt

Replace `{prompt}` with the text of `../prompt.md`, `{cutoff_facts}`
with the item gathered as of the cutoff, and `{all_facts}` with the
item gathered with no cutoff.

```
You prepare the scoring targets ("key facts") for an eval of a
triage bot for the Zulip open-source project. The bot writes a card
for each new GitHub PR or issue: a verdict, a plain summary, short
points, a reviewer (PRs only), a next step, and a ready-to-paste
reply to the author. These are the bot's instructions:

<bot_prompt>
{prompt}
</bot_prompt>

What was known when the item was opened (what the bot sees):

<cutoff_facts>
{cutoff_facts}
</cutoff_facts>

Everything about the item up to now, including what happened later:

<all_facts>
{all_facts}
</all_facts>

Reply with only a JSON object of this shape:

{"verdict": "close|ask_author|review|discuss_design|no_action",
 "verdict_why": "one sentence",
 "reply_ask": "one sentence: the main thing the reply must ask or say",
 "must_have": [{"id": "f1", "fact": "...", "decisive": true,
                "at_cutoff": true}]}

Rules:
- `verdict`:
  - `close`: tell the author to close
  - `ask_author`: the author must change or answer something first
  - `review`: nothing to ask the author; it needs a reviewer
  - `discuss_design`: it needs a design decision on CZO or the issue
  - `no_action`: an issue that needs nothing now
  Take it from what maintainers did: closed as a duplicate, as not
  "help wanted", or as untested → `close`; asked for changes or
  asked a question → `ask_author`; reviewed or merged with no ask →
  `review`; pointed to a design discussion → `discuss_design`; a
  labeled issue needing nothing more → `no_action`.
- `must_have`: 3-6 items. Each `fact` is one checkable sentence that
  names the number or person a card must contain, for example
  "names #39720 as the PR this continues". `decisive` is true when
  missing it alone would change the verdict. `at_cutoff` is true
  only if the fact is in the cutoff facts. Prefer facts that drive
  the decision (earlier attempts, duplicates, labels like "help
  wanted", failing CI, a maintainer's earlier comment, a CZO
  decision, who should review) over descriptive ones.
```

## Judge prompt

Replace `{prompt}` with the text of `../prompt.md`, `{all_facts}`
with the item gathered with no cutoff, `{key}` with the case's key
facts, and `{cards}` with the cards, each under a
`=== CARD <letter> ===` line.

```
You are judging cards written by a triage bot for the Zulip
open-source project. Each card is the message the bot would post in
a Zulip topic about one new GitHub PR or issue. Several cards for
the SAME item were written by different models, prompts, or inputs.
They are labeled with random letters and shown in random order; the
order carries no information.

The bot's instructions: <bot_prompt>{prompt}</bot_prompt>
The full facts about the item, including what happened later:
<all_facts>{all_facts}</all_facts>
The key facts, prepared in advance: <key>{key}</key>
The cards: <cards>{cards}</cards>

Use only these inputs. Use the key facts as given; don't re-derive
them. Facts marked `at_cutoff: false` happened after the item was
opened. They may explain the maintainers' decision, but no card loses
points for missing them.

Step 1: check each card.
- Classify its verdict as close, ask_author, review, discuss_design,
  or no_action, from the verdict line and next step, not the reply.
  `decision_correct` is true only when it matches the key's verdict.
- Mark every `must_have` id present, missing, hedged, or wrong. A
  hedge ("unclear from the input") about a fact that is in the full
  facts counts as missing.
- List rule failures: places where the card breaks a rule in the
  bot's instructions. Name each in snake_case. A bullet a maintainer
  wouldn't act on, and that the verdict doesn't rest on, is a
  `filler_point`. A reply to a close candidate that invites more
  work is a `soft_closing_reply`.
- List wrong facts: false statements, even plausible guesses.

Step 2: score each card from 1 to 10.
summary_score (verdict, summary, points, reviewer, next step):
- 9-10: right verdict, every cutoff must-have present, plain
  user-facing summary, nothing to cut
- 7-8: right verdict; one non-decisive must-have missing, or one
  point too long or with code details
- 5-6: right verdict, but a decisive must-have missing, or two or
  more must-haves missing
- 3-4: wrong verdict
- 1-2: wrong verdict plus wrong facts
reply_score:
- 9-10: a maintainer would paste it as is
- 7-8: paste after changing a word or two
- 5-6: right decision and ask, but the tone or a missing reference
  (earlier attempt, CZO thread, maintainer comment) means rewriting
  a sentence
- 3-4: wrong ask, or misses `reply_ask`
- 1-2: wrong decision, such as welcoming an author who should be
  told to close
When the verdict is `no_action` or `review`, "No reply needed." or a
single reviewer ping line scores 9-10, and a reply of two or more
sentences to the author scores at most 6.

Adjustments: a wrong fact that the verdict or the reply's ask rests
on caps that part at 4. Any other wrong fact subtracts 2 from its
part. Each rule failure subtracts 1 from its part. Then look at the
cards that share a score, and if two aren't interchangeable, adjust
one. Make at most 3 such adjustments.

Step 3: rank by overall = (2 × reply_score + summary_score) / 3.
Break ties by fewer wrong facts, then fewer rule failures, then
fewer words.

Reply with only this JSON, with one sentence for each "why":
{"cards": {"<letter>": {"verdict": "close", "decision_correct": true,
   "facts": {"<id>": "present|missing|hedged|wrong"},
   "rule_failures": ["..."], "wrong_facts": ["..."],
   "summary_score": 8, "reply_score": 7,
   "summary_why": "...", "reply_why": "..."}},
 "ranking": ["<best letter>", "..."]}
```

## What to report

- The mean overall score, where overall = (2 × reply + summary) / 3.
  The reply counts double because maintainers paste it.
- How often the verdict is right.
- Wrong facts per card. Statements the input doesn't show, such as
  commit counts or "no conflicts", show up here.
- The most common rule failures.
- Every comparison as a paired difference over the same cases: the
  mean of the per-case differences ± SE, where SE = stdev / √n.

## Reading the results

- Always compare configurations with the same judge model. Scores
  from different judges can't be compared.
- A difference under 2 SE is noise. The judge's two passes differ
  by about 0.4 points per card, and two runs of the same bot
  configuration differed by 0.27 to 0.51 on average.
- Tune on some cases and report on others. Prompts tuned on 21 hard
  cases gained about 1 to 1.5 points there and lost up to 0.82 on
  the other 33. The rules written for the hard cases were wrong for
  new ones. For example, "ask the author to fix failing CI" turned
  correct closes into requests.
- Judging cards side by side ranks them well, but a card's score
  depends on what it is shown next to. The same cards scored about
  0.3 lower in a second round with different neighbors. Only
  compare scores from the same judging run.
- A full run of 4 configurations is 54 × 4 bot calls and 108 judge
  calls.

## Checking by hand

The judge's score alone is not enough to accept a change. Have a
maintainer who triages issues and PRs check a sample:

1. Pick 10 cases, spread over issues and PRs and over verdicts.
2. Show the maintainer one case at a time: the item, and the cards
   from the old and the new configuration.
3. Ask which card they would act on, whether they would paste its
   reply, and what is wrong with each card.
4. Save the comments word for word. They show what to change in the
   prompt better than any score does.
5. If the maintainer and the judge disagree on the verdict, check
   the answer key before trusting the judge.

Have a maintainer read the answer keys too. When the keys for these
cases were first built, a maintainer's reading changed several
verdicts.

## Known limits

- The replay can see CZO threads that were linked or found only
  after the cutoff, so it may find the right thread more often than
  the live bot does.
- The live bot posts PR cards after the first CI run, so it sees CI
  results the replay may mark as unknown. A check that failed at the
  cutoff and later passed on a re-run makes the replay ask for a CI
  fix that maintainers never asked for.
- Some duplicates can't be found from the title, so every card
  misses them.
- Judges reading a very long item sometimes read only its first
  part, and may miss wrong facts in a card.
