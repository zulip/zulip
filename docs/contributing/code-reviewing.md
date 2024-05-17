# Reviewing Zulip code

Code review is a key part of how Zulip does development. It's an essential
aspect of our process to build a high-quality product with a maintainable
codebase. See the [pull request review process](../contributing/review-process.md)
guide for a detailed overview of Zulip's PR review process.

## Principles of code review

Zulip has an active contributor community, and just a small handful
of maintainers who can do the final rounds of code review. As such, we would
love for contributors to help each other with making pull requests that are not
only correct, but easy to review. Doing so ensures that PRs can be finalized and
merged more quickly, and accelerates the pace of progress for the entire
project.

If you're new to open source, this may be the first time you do a code review of
anyone's changes! We have therefore written this step-by-step guide to be
accessible to all Zulip contributors.

### Reviewing your own code

One of the best ways to improve the quality of your own work as a software
engineer is to do a code review of your own work before submitting it to others for
review. We thus strongly encourage you to get into the habit of reviewing you
own code. You can often find things you missed by taking a step back to look
over your work before asking others to do so, and this guide will walk you
through the process. Catching mistakes yourself will help your PRs be merged
faster, and folks will appreciate the quality and professionalism of your
work.

### Reviewing other contributors' code

Doing code reviews is a valuable contribution to the Zulip project.
It's also an important skill to develop for participating in
open-source projects and working in the industry in general. If
you're contributing to Zulip and have been working in our code for a
little while, we would love for you to start doing code reviews!

Anyone can do a code review -- you don't have to have a ton of experience, and
you don't have to have the power to ultimately merge the PR. The sections below
offer accessible, step-by-step guidance for how to go about reviewing Zulip PRs.

For students participating in Google Summer of Code or a similar
program, we expect you to spend a chunk of your time each week (after
the first couple of weeks as you're getting going) doing code reviews.

## How to review code

Whether you are reviewing your own code or somebody else's, this section
describes how to go about it.

If you are reviewing somebody else's code, you will likely need to first fetch
it so that you can play around with the new functionality. If you're working in
the Zulip server codebase, use our [Git tool][git-tool]
`tools/fetch-rebase-pull-request` to check out a pull request locally and rebase
it onto `main`.

### Code review checklist

The following review steps apply to the majority of PRs.

**Think about the issue:**

1. Start by **rereading the issue** the PR is intended to solve. Are you
   confident that you **understand everything the issue is asking for**? If not,
   try exploring the relevant parts of the Zulip app and reading any linked
   discussions on the [development community server][czo] to see if the
   additional context helps. If any part is still confusing, post a GitHub
   comment or a message on the [development community server][czo] explaining
   precisely what points you find confusing.

2. Now that you're confident that you understand the issue, **does the PR
   address all the points described in the issue**? If not, is it easy to tell
   without reading the code which points are not addressed and why? Here is a
   handful of good ways for the author to communicate why the issue as written
   might not be fully solved by the PR:

   - The issue explicitly notes that it's fine for some parts to be completed
     separately, and the PR clearly indicates which parts are solved.
   - After discussion of initial prototypes (in GitHub comments or on the
     [development community server][czo]), it was decided to change some part of
     the specification, and the PR notes this.
   - The author explains why the PR is a better way to solve the issue than what
     was described.
   - The solution changed because of changes in the project or application since
     the issue was written, and the author explains the adjustments that were
     made.

**Think about the code:**

1. Make sure the PR uses **clear function, argument, variable, and test names.**
   Every new piece of Zulip code will be read many times by other developers, and
   future developers will `grep` for relevant terms when researching a problem, so
   it's important that variable names communicate clearly the purpose of each
   piece of the codebase.

1. Make sure the PR **avoids duplicated code.** Code duplication is a huge
   source of bugs in large projects and makes the codebase difficult to
   understand, so we avoid significant code duplication wherever possible.
   Sometimes avoiding code duplication involves some refactoring of existing
   code; if so, that should usually be done as its own series of commits (not
   squashed into other changes or left as a thing to do later). That series of
   commits can be in the same pull request as the feature that they support, and
   we recommend ordering the history of commits so that the refactoring comes
   _before_ the feature. That way, it's easy to merge the refactoring (and
   minimize risk of merge conflicts) if there are still user experience issues
   under discussion for the feature itself.

1. **Good comments** help. It's often worth thinking about whether explanation
   in a commit message or pull request discussion should be included in
   a comment, `/docs`, or other documentation. But it's better yet if
   verbose explanation isn't needed. We prefer writing code that is
   readable without explanation over a heavily commented codebase using
   lots of clever tricks.

1. Make sure the PR follows Zulip's **coding style**. See the Zulip [coding
   style documentation][code-style] for details. Our goal is to have as much of
   this as possible verified via the linters and tests, but there will always be
   unusual forms of Python/JavaScript style that our tools don't check for.

1. If you can, step back and think about the **technical design**. There are a
   lot of considerations here: security, migration paths/backwards compatibility,
   cost of new dependencies, interactions with features, speed of performance,
   API changes. Security is especially important and worth thinking about
   carefully with any changes to security-sensitive code like views.

**Think about testing:**

1. **The CI build tests need to pass.** One can investigate
   any failures and figure out what to fix by clicking on a red X next
   to the commit hash or the Detail links on a pull request. (Example:
   in [#17584](https://github.com/zulip/zulip/pull/17584),
   click the red X before `49b10a3` to see the build jobs
   for that commit. You can see that there are 7 build jobs in total.
   All the 7 jobs run in GitHub Actions. You can see what caused
   the job to fail by clicking on the failed job. This will open
   up a page in the CI that has more details on why the job failed.
   For example [this](https://github.com/zulip/zulip/runs/2092955762)
   is the page of the "Ubuntu 20.04 (Python 3.8, backend + frontend)" job.
   See our docs on [continuous integration](../testing/continuous-integration.md)
   to learn more.

2. Make sure **the code is well-tested**; see below for details. The PR should
   summarize any [manual testing](#manual-testing) that was done to validate
   that the feature is working as expected.

**Think about the commits:**

1. Does the PR follow the principle that “**Each commit is a minimal coherent
   idea**”? See the [commit discipline guide][commit-discipline] to learn more
   about commit structure in Zulip.

2. Does each commit have a **clear commit message**? Check for content, format,
   spelling and grammar. See the [Zulip commit discipline][commit-messages]
   documentation for details on what we look for.

You should also go through any of the following checks that are applicable:

- _Error handling._ The code should always check for invalid user
  input. User-facing error messages should be clear and when possible
  be actionable (it should be obvious to the user what they need to do
  in order to correct the problem).

- _Translation._ Make sure that the strings are marked for
  [translation].

- _Completeness of refactoring._ When reviewing a refactor, verify that the changes are
  complete. Usually, one can check that efficiently using `git grep`,
  and it's worth it, as we very frequently find issues by doing so.

- _Documentation updates._ If this changes how something works, does it
  update the documentation in a corresponding way? If it's a new
  feature, is it documented, and documented in the right place?

- _mypy annotations in Python code._ New functions should be annotated using
  [mypy] and existing annotations should be updated. Use of `Any`, `ignore`, and
  unparameterized containers should be limited to cases where a more precise
  type cannot be specified.

### Automated testing

- The tests should **validate that the feature works correctly**, and
  specifically test for common error conditions, bad user input, and potential
  bugs that are likely for the type of change being made. Tests that exclude
  whole classes of potential bugs are preferred when possible (e.g., the common
  test suite `test_markdown.py` between the Zulip server's [frontend and backend
  Markdown processors](../subsystems/markdown.md), or the `GetEventsTest` test
  for buggy race condition handling). See the [test writing][test-writing]
  documentation to learn more.

- We are trying to maintain ~100% test coverage on the backend, so backend
  changes should have negative tests for the various error conditions. See
  [backend testing documentation][backend-testing] for details.

- If the feature involves frontend changes, there should be frontend tests. See
  [frontend testing documentation][frontend-testing] for details.

### Manual testing

If the PR makes any frontend changes, you should make sure to play with the part
of the app being changed to validate that things look and work as expected.
While not all of the situations below will apply, here are some ideas for things
that should be tested if they are applicable. Use the [development
environment][development-environment] to test any web app changes.

This might seem like a long process, but you can go through it quite quickly
once you get the hang of it. Trust us, it will save time and review round-trips
down the line!

**Visual appearance:**

- Open up the parts of the UI that were changed, and make sure they look as
  you were expecting.
- Is the new UI consistent with similar UI elements? Think about fonts, colors,
  sizes, etc. If a new or modified element has multiple states (e.g. "on" and
  "off"), consider all of them.
- Is the new UI aligned correctly with the elements around it, both vertically and
  horizontally?
- If the PR adds or modifies a clickable element, does it have a hover behavior
  that's consistent with similar UI elements?
- If the PR adds or modifies an element (e.g. a button or checkbox) that is
  sometimes disabled, is the disabled version of the UI consistent with similar
  UI elements?
- Did the PR accidentally affect any other parts of the UI? E.g., if the PR
  modifies some CSS, look for other elements that may have been altered
  unintentionally. Use `git grep` to see if the code you modified is being used
  elsewhere.
- Now check all of the above in the other theme (light/dark).

**Responsiveness and internationalization:**

- Check the new UI at different window sizes, including mobile sizes (you can
  use Chrome DevTools if you like). Does it look good in both wide and narrow
  windows?
- To simulate what will happen when the UI is translated to different languages,
  try changing any new strings, or ones that are now displayed differently, to
  make them 1.5x longer, and check if anything breaks. What would happen if the
  strings were half as long as in English?

**Strings (text):**
If the PR adds or modifies strings, check the following:

- Does the wording seem consistent with similar features (similar style, level
  of detail, etc.)?
- If there is a number, are the `N = 1` and `N > 1` cases both handled properly?

**Tooltips:**

- Do elements that require tooltips have them? Check similar elements to see
  whether a tooltip is needed, and what information it should contain.

**Functionality:**
We're finally getting to the part where you actually use the new/updated
feature. :) Test to see if it works as expected, trying a variety of scenarios.
If it works as described in the issue but seems awkward in some way, note this
on the PR.

If relevant, be sure to check that:

- Live updates are working as expected.
- Keyboard navigation, including tabbing to the interactive elements, is working
  as expected.

Some scenarios to consider:

- Try clicking on any interactive elements, multiple times, in a variety of orders.
- If the feature affects the **message view**, try it out in different types of
  narrows: topic, stream, Combined feed, direct messages.
- If the feature affects the **compose box** in the web app, try both ways of
  [resizing the compose box](https://zulip.com/help/resize-the-compose-box).
  Test both stream messages and direct messages.
- If the feature might require **elevated permissions**, check it out as a user who has
  permissions to use it and one who does not.
- Think about how the feature might **interact with other features**, and try out
  such scenarios. For example:
  - If the PR adds a banner, is it possible that it would be shown at the same
    time as other banners? Does something reasonable happen?
  - If the feature has to do with topic editing, do you need to think
    about what happens when a topic is resolved/unresolved?
  - If it's a message view feature, would anything go wrong if the message was
    collapsed or muted? If it was colored like an `@`-mention or a direct message?

## Review process and communication

### Asking for a code review

The [pull request review process](../contributing/review-process.md) guide
provides a detailed overview of Zulip's PR review process. Your reviewers and
Zulip's maintainers will help shepherd your PR through the process. There are
also some additional ways to ask for a code review:

- Are there folks who have been working on similar things, or a loosely related
  area? If so, they might be a good person to review your PR. `@`-mention them
  with something like "`@person`, would you be up for reviewing this?" If
  you're not sure whether they are familiar with how Zulip code reviews work, you
  can also include a link to this guide.

- If you're not sure who to ask, you can post a message in
  [#code-review](https://chat.zulip.org/#narrow/stream/91-code-review) on [the Zulip
  development community server](https://zulip.com/development-community/) to reach
  out to a wider group of potential reviewers.

Please be patient and mindful of the fact that it isn't always possible to
provide a quick reply. Going though the [review process](#how-to-review-code)
described above for your own PR will make your code easier and faster to review,
which makes it much more likely that it will be reviewed quickly and require
fewer review cycles.

### Reviewing someone else's code

#### Fast replies are key

For the author of a PR, getting feedback quickly is really important
for making progress quickly and staying productive. That means that
if you get @-mentioned on a PR with a request for you to review it,
it helps the author a lot if you reply promptly.

A reply doesn't even have to be a full review; if a PR is big or if
you're pressed for time, then just getting some kind of reply in
quickly -- initial thoughts, feedback on the general direction, or
just saying you're busy and when you'll have time to look harder -- is
still really valuable for the author and for anyone else who might
review the PR.

People in the Zulip project live and work in many time zones, and code
reviewers also need focused chunks of time to write code and do other
things, so an immediate reply isn't always possible. But a good
benchmark is to try to always reply **within one workday**, at least
with a short initial reply, if you're working regularly on Zulip. And
sooner is better.

#### Communication style

Any time you leave a code review, be sure to treat the author with respect.
Remember that they are generously spending their time on an effort to improve
the Zulip project. Thank them for their work, and express your appreciation for
anything the author did especially well, whether it's a nice commit message, a
prompt response to earlier feedback, or a well-written test.

Be as clear and direct as you can when describing requested changes. There is no
need to apologize when asking for a change; you're collaborating with the
author to make the PR as good as you can together.

Be sure to explain the motivation for the changes you're requesting if it's not
obvious, so that the author can learn for next time. It may be helpful to point
to developer documentation, such as the [commit discipline
guide][commit-discipline].

#### Fixing up the PR

If a pull request just needs a little fixing to make it mergeable,
feel free to do that in a new commit, then push your branch to GitHub
and mention the branch in a comment on the pull request. That'll save
the maintainer time and get the PR merged quicker.

### Responding to review feedback

Once you've received a review and resolved any feedback, it's critical
to update the GitHub thread to reflect that. Best practices are to:

- Make sure that CI passes and the PR is rebased onto recent `main`.
- Post comments on each feedback thread explaining at least how you
  resolved the feedback, as well as any other useful information
  (problems encountered, reasoning for why you picked one of several
  options, a test you added to make sure the bug won't recur, etc.).
- Post a summary comment in the main feed for the PR, explaining that
  this is ready for another review, and summarizing any changes from
  the previous version, details on how you tested the changes, new
  screenshots/etc. More detail is better than less, as long as you
  take the time to write clearly.

If you resolve the feedback, but the PR has merge conflicts, CI
failures, or the most recent comment is the reviewer asking you to fix
something, it's very likely that a potential reviewer skimming your PR
will assume it isn't ready for review and move on to other work.

If you need help or think an open discussion topic requires more
feedback or a more complex discussion, move the discussion to a topic
in the [Zulip development community server][czo]. Be sure to provide links
from the GitHub PR to the conversation (and vice versa) so that it's
convenient to read both conversations together.

## Additional resources

We also recommend the following resources on code reviews.

- [The Gentle Art of Patch Review](https://sage.thesharps.us/2014/09/01/the-gentle-art-of-patch-review/)
  article by Sarah Sharp
- [Zulip & Good Code Review](https://www.harihareswara.net/sumana/2016/05/17/0)
  article by Sumana Harihareswara
- [Code Review - A consolidation of advice and stuff from the
  internet](https://gist.github.com/porterjamesj/002fb27dd70df003646df46f15e898de)
  article by James J. Porter
- [Zulip code of conduct](../code-of-conduct.md)

[code-style]: code-style.md
[commit-discipline]: commit-discipline.md
[commit-messages]: commit-discipline.md#commit-messages
[test-writing]: ../testing/testing.md
[backend-testing]: ../testing/testing-with-django.md
[frontend-testing]: ../testing/testing-with-node.md
[mypy]: ../testing/mypy.md
[git-tool]: ../git/zulip-tools.md#fetch-a-pull-request-and-rebase
[translation]: ../translating/translating.md
[czo]: https://zulip.com/development-community/
[development-environment]: ../development/overview.md
