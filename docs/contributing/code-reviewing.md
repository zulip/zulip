# Reviewing Zulip code

Code review is a key part of how Zulip does development! If you've
been contributing to Zulip's code, we'd love for you to do reviews.
This is a guide to how. (With some thoughts for writing code too.)

## Protocol for authors

When you send a PR, try to think of a good person to review it --
outside of the handful of people who do a ton of reviews -- and
`@`-mention them with something like "`@person`, would you review
this?". Good choices include

- someone based in your timezone or a nearby timezone
- people working on similar things, or in a loosely related area

Alternatively, posting a message in
[#code-review](https://chat.zulip.org/#narrow/stream/91-code-review) on [the Zulip
development community server](https://zulip.com/developer-community/), would
help in reaching out to a wider group of reviewers. Either way, please be
patient and mindful of the fact that it isn't possible to provide a
quick reply always, but that the reviewer would get to it sooner or later.
Lastly, ensuring the your PR passes CI and is organized into coherent
commits would help save reviewers time, which could otherwise be used
to dive right into reviewing the PR's core functionality.

### Responding to a review feedback

Once you've received a review and resolved any feedback, it's critical
to update the GitHub thread to reflect that. Best practices are to:

- Make sure that CI passes and the PR is rebased onto recent `main`.
- Post comments on each feedback thread explaining at least how you
  resolved the feedback, as well as any other useful information
  (problems encountered, reasoning for why you picked one of several
  options, a test you added to make sure the bug won't recur, etc.).
- Mark any resolved threads as "resolved" in the GitHub UI, if
  appropriate.
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
in the Zulip development community server. Be sure to provide links
from the GitHub PR to the conversation (and vice versa) so that it's
convenient to read both conversations together.

## Principles of code review

### Anyone can review

Anyone can do a code review -- you don't have to have a ton of
experience, and you don't have to have the power to ultimately merge
the PR. If you

- read the code, see if you understand what the change is
  doing and why, and ask questions if you don't; or

- fetch the code (for Zulip server code,
  [tools/fetch-rebase-pull-request][git tool] is super handy), play around
  with it in your dev environment, and say what you think about how
  the feature works

those are really helpful contributions.

### Please do reviews

Doing code reviews is an important part of making the project grow.
It's also an important skill to develop for participating in
open-source projects and working in the industry in general. If
you're contributing to Zulip and have been working in our code for a
little while, we would love for some of your time contributing to come
in the form of doing code reviews!

For students participating in Google Summer of Code or a similar
program, we expect you to spend a chunk of your time each week (after
the first couple of weeks as you're getting going) doing code reviews.

### Fast replies are key

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

People in the Zulip project live and work in many timezones, and code
reviewers also need focused chunks of time to write code and do other
things, so an immediate reply isn't always possible. But a good
benchmark is to try to always reply **within one workday**, at least
with a short initial reply, if you're working regularly on Zulip. And
sooner is better.

## Things to look for

- _The CI build._ The tests need to pass. One can investigate
  any failures and figure out what to fix by clicking on a red X next
  to the commit hash or the Detail links on a pull request. (Example:
  in [#17584](https://github.com/zulip/zulip/pull/17584),
  click the red X before `49b10a3` to see the build jobs
  for that commit. You can see that there are 7 build jobs in total.
  All the 7 jobs run in GitHub Actions. You can see what caused
  the job to fail by clicking on the failed job. This will open
  up a page in the CI that has more details on why the job failed.
  For example [this](https://github.com/zulip/zulip/runs/2092955762)
  is the page of the `Ubuntu 18.04 Bionic (Python 3.6, backend + frontend)` job.
  See our docs on [continuous integration](../testing/continuous-integration.md)
  to learn more.

- _Technical design._ There are a lot of considerations here:
  security, migration paths/backwards compatibility, cost of new
  dependencies, interactions with features, speed of performance, API
  changes. Security is especially important and worth thinking about
  carefully with any changes to security-sensitive code like views.

- _User interface and visual design._ If frontend changes are
  involved, the reviewer will check out the code, play with the new
  UI, and verify it for both quality and consistency with the rest of
  the Zulip UI. We highly encourage posting screenshots to save
  reviewers time in getting a feel for what the feature looks like --
  you'll get a quicker response that way.

- _Error handling._ The code should always check for invalid user
  input. User-facing error messages should be clear and when possible
  be actionable (it should be obvious to the user what they need to do
  in order to correct the problem).

- _Testing._ The tests should validate that the feature works
  correctly, and specifically test for common error conditions, bad
  user input, and potential bugs that are likely for the type of
  change being made. Tests that exclude whole classes of potential
  bugs are preferred when possible (e.g., the common test suite
  `test_markdown.py` between the Zulip server's [frontend and backend
  Markdown processors](../subsystems/markdown.md), or the `GetEventsTest` test for
  buggy race condition handling).

- _Translation._ Make sure that the strings are marked for
  [translation].

- _Clear function, argument, variable, and test names._ Every new
  piece of Zulip code will be read many times by other developers, and
  future developers will grep for relevant terms when researching a
  problem, so it's important that variable names communicate clearly
  the purpose of each piece of the codebase.

- _Duplicated code._ Code duplication is a huge source of bugs in
  large projects and makes the codebase difficult to understand, so we
  avoid significant code duplication wherever possible. Sometimes
  avoiding code duplication involves some refactoring of existing
  code; if so, that should usually be done as its own series of
  commits (not squashed into other changes or left as a thing to do
  later). That series of commits can be in the same pull request as
  the feature that they support, and we recommend ordering the history
  of commits so that the refactoring comes _before_ the feature. That
  way, it's easy to merge the refactoring (and minimize risk of merge
  conflicts) if there are still user experience issues under
  discussion for the feature itself.

- _Completeness._ For refactorings, verify that the changes are
  complete. Usually one can check that efficiently using `git grep`,
  and it's worth it, as we very frequently find issues by doing so.

- _Documentation updates._ If this changes how something works, does it
  update the documentation in a corresponding way? If it's a new
  feature, is it documented, and documented in the right place?

- _Good comments._ It's often worth thinking about whether explanation
  in a commit message or pull request discussion should be included in
  a comment, `/docs`, or other documentation. But it's better yet if
  verbose explanation isn't needed. We prefer writing code that is
  readable without explanation over a heavily commented codebase using
  lots of clever tricks.

- _Coding style._ See the Zulip [code-style] documentation for
  details. Our goal is to have as much of this as possible verified
  via the linters and tests, but there's always going to be unusual
  forms of Python/JavaScript style that our tools don't check for.

- _Clear commit messages._ See the [Zulip version
  control][commit-messages] documentation for details on what we look
  for.

### Zulip server

Some points specific to the Zulip server codebase:

- _Testing -- Backend._ We are trying to maintain ~100% test coverage
  on the backend, so backend changes should have negative tests for
  the various error conditions.

- _Testing -- Frontend._ If the feature involves frontend changes,
  there should be frontend tests. See the [test
  writing][test-writing] documentation for more details.

- _mypy annotations._ New functions should be annotated using [mypy]
  and existing annotations should be updated. Use of `Any`, `ignore`,
  and unparameterized containers should be limited to cases where a
  more precise type cannot be specified.

## Tooling

To make it easier to review pull requests, if you're working in the
Zulip server codebase, use our [git tool]
`tools/fetch-rebase-pull-request` to check out a pull request locally
and rebase it onto `main`.

If a pull request just needs a little fixing to make it mergeable,
feel free to do that in a new commit, then push your branch to GitHub
and mention the branch in a comment on the pull request. That'll save
the maintainer time and get the PR merged quicker.

## Additional resources

We also strongly recommend reviewers to go through the following resources.

- [The Gentle Art of Patch Review](https://sage.thesharps.us/2014/09/01/the-gentle-art-of-patch-review/)
  article by Sarah Sharp
- [Zulip & Good Code Review](https://www.harihareswara.net/sumana/2016/05/17/0)
  article by Sumana Harihareswara
- [Code Review - A consolidation of advice and stuff from the
  internet](https://gist.github.com/porterjamesj/002fb27dd70df003646df46f15e898de)
  article by James J. Porter
- [Zulip code of conduct](../code-of-conduct.md)

[code-style]: ../contributing/code-style.md
[commit-messages]: ../contributing/version-control.html#commit-messages
[test-writing]: ../testing/testing.md
[mypy]: ../testing/mypy.md
[git tool]: ../git/zulip-tools.html#fetch-a-pull-request-and-rebase
[translation]: ../translating/translating.md
