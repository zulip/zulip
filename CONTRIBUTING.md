# Contributing guide

Welcome! This is a step-by-step guide on how to get started contributing code to
the [Zulip](https://zulip.com/) organized team chat [open-source
project](https://github.com/zulip). Thousands of people use Zulip every day, and
your work on Zulip will have a meaningful impact on their experience. We hope
you'll join us!

To learn about ways to contribute without writing code, please see our
suggestions for how you can [support the Zulip
project](https://zulip.com/help/support-zulip-project).

## How to use Zulip's documentation for contributors

::: note

**Reading and following our written guidelines** to the very best of your ability is
the only way to become a successful Zulip contributor.

:::

Zulip has a documentation-based approach to onboarding new contributors. As you
are getting started, this page will be your go-to for figuring out what to do
next. You will also explore other guides, learning about how to put together
your first pull request, diving into [Zulip's
subsystems](https://zulip.readthedocs.io/en/latest/subsystems/index.html), and
much more.

We hope you'll find this process to be a great learning experience. If you
_aren't_ excited to learn from our series of contributor guides, then Zulip is
not the right project for you.

Please read the following sections of this guide at the times described (or
earlier!).

Prior to picking up your first issue:

- [How to be a successful contributor](#how-to-be-a-successful-contributor)
- [AI use policy and guidelines](#ai-use-policy-and-guidelines)
- [Getting started](#getting-started)
- [Finding an issue to work on](#finding-an-issue-to-work-on)

When starting to work on your first issue:

- [Getting help](#getting-help) as you work on your first pull request
- Learning [best practices](#best-practices)

When getting ready to submit your first pull request:

- [Submitting a pull request](#submitting-a-pull-request)

After submitting your first pull request:

- [Going beyond the first issue](#beyond-the-first-issue)

Any time you feel lost, come back to this guide. The information you need is
likely somewhere on this page (perhaps in the list of [common
questions](#common-questions)), or in one of the many references it points to.

If you've done all you can with the documentation and are still feeling stuck,
join the [Zulip development community](https://zulip.com/development-community/)
to ask for help! Before you post, be sure to review [community
norms](https://zulip.com/development-community/#community-norms) and [where to
post](https://zulip.com/development-community/#where-do-i-send-my-message) your
question. The Zulip community is governed by a [code of
conduct](https://zulip.readthedocs.io/en/latest/code-of-conduct.html).

## How to be a successful contributor

In our experience, to become an effective Zulip contributor, you should be
excited to:

- **Learn from documentation.** Zulip has over 185,000 words of [documentation
  for contributors][documentation for contributors], and we expect you to make
  good use of it.
- **Aim for understanding**. To produce work that improves Zulip, you’ll need to
  understand the relevant existing code, and figure out a good set of changes to
  accomplish what you’re trying to do. Fiddling or vibe coding until things seem
  to work, and then asking maintainers to verify code that you don’t understand
  yourself, does not help the project.
- **Take pride in your work**. Strive to write the best
  [commits][commit discipline] you can, carefully [review][reviewing code] your
  own work, and take the time to [explain][submitting a PR] it clearly to
  project maintainers. Do your very best to overcome any challenges you run in
  to before asking for help.
- **Learn from feedback.** Every pull request undergoes a rigorous [review
  process][review process]. We need contributors to carefully apply and respond
  to the feedback they receive, and to take advantage of the learning experience
  to avoid similar mistakes in future work.
- **Communicate with intention.** Any piece of communication from you (a pull
  request, a [question][great-questions] in the development community, etc.), is
  a request for time and attention from Zulip’s maintainers. Successful
  contributors put in the reasoning and writing effort required to
  [communicate][how we communicate] clearly and succinctly, and don’t waste the
  community’s time with AI slop. See our [AI use policy and
  guidelines](#ai-use-policy-and-guidelines).
- **Communicate in the open.** Technical and product decisions are discussed
  openly in the [Zulip development
  community](https://zulip.com/development-community/) and [on
  GitHub](https://github.com/zulip), so that we can all learn from each other.

What about technical skills? You will need a baseline level of technical
expertise to be able to understand the part of Zulip’s code base you’re working
in, and make quality changes. If you find that you are constantly getting stuck
as you work towards this, it might be best to hold off on trying to contribute,
and focus on learning the relevant software engineering skills for now.

[documentation for contributors]: https://zulip.readthedocs.io/en/latest/index.html#zulip-documentation-overview
[commit discipline]: https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html
[reviewing code]: https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html
[submitting a PR]: https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html
[review process]: https://zulip.readthedocs.io/en/latest/contributing/review-process.html
[how we communicate]: https://zulip.readthedocs.io/en/latest/contributing/how-we-communicate.html

## AI use policy and guidelines

Our goal in the Zulip project is to develop an excellent software
system. This requires careful attention to detail in every change we
integrate. Maintainer time and attention is very limited, so it's
important that changes you ask us to review represent
your _best_ work.

You can use any tools that help you understand the Zulip codebase and
write good code, including AI tools. However, as noted above, you
always need to understand and explain the changes you're proposing to
make, whether or not you used an LLM as part of your process to
produce them. The answer to “Why is X an improvement?” should never be
“I'm not sure. The AI did it.”

::: warning
**Do not submit an AI-generated PR you haven't personally understood and
tested**, as this wastes maintainers' time. PRs that appear to violate this
guideline will be closed without review.
:::

### Using AI as a coding assistant

1. Don't skip **becoming familiar with the part of the codebase**
   you're working on. This will let you write better prompts and
   validate their output if you use an LLM. Code assistants can be a
   useful search engine/discovery tool in this process, but don't
   trust claims they make about how Zulip works. LLMs are often wrong,
   even about details that are clearly answered in the Zulip
   documentation.
1. Split up your changes into **[coherent
   commits](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html)**,
   even if an LLM generates them all in one go.
1. Don't simply ask an LLM to add **code comments**, as it will likely
   produce a bunch of text that unnecessarily explains what's already
   clear from the code. If using an LLM to generate comments, be
   really specific in your request, demand succinctness, and carefully
   edit the result.

### Using AI for communication

As noted above, Zulip's contributors are expected to communicate with
intention, to avoid wasting maintainer time with long, sloppy
writing. We strongly prefer clear and concise communication about
points that actually require discussion over long AI-generated
comments.

When you use an LLM to write a message for you, it remains **your
responsibility** to read through the whole thing and make sure that it
makes sense to you and represents your ideas concisely. A good rule
of thumb is that if you can't make yourself carefully read some LLM
output that you generated, nobody else wants to read it either.

Here are some concrete guidelines for using LLMs as part of your communication
workflows.

1. When writing a pull request description, **do not include anything that's
   obvious** from looking at your changes directly (e.g., files changed, functions
   updated, etc.). Instead, focus on the _why_ behind your changes. Don't ask an
   LLM to generate a PR description on your behalf based on your code changes,
   as it will simply regurgitate the information that's already there.
1. Similarly, when responding to a pull request comment, **explain _your_
   reasoning**. Don't prompt an LLM to re-describe what can already be seen from
   the code.
1. Verify that **everything you write is accurate**, whether or not an LLM
   generated any part of it. Zulip's maintainers will be unable to review your
   contributions if you misrepresent your work (e.g., misdescribing your code
   changes, their effect, or your testing process).
1. Complete all parts of the **PR description template**, including screenshots
   and the self-review checklist. Don't simply overwrite the template with LLM
   output.
1. **Clarity and succinctness** are much more important than perfect grammar, so
   you shouldn't feel obliged to pass your writing through an LLM. If you do ask
   an LLM to clean up your writing style, be sure it does _not_ make it longer
   in the process. Demand succinctness in your prompt.
1. Quoting an LLM answer is usually less helpful than linking to
   **relevant primary sources**, like source code, reference
   documentation, or web standards. If you do need to quote an LLM
   answer in a Zulip conversation, put the answer in a [Zulip quote
   block](https://zulip.com/help/format-a-quote), to distinguish LLM
   output from your own thoughts.

## Getting started

### Learning how to use Git (the Zulip way)

Zulip uses GitHub for source control and code review, and becoming familiar with
Git is essential for navigating and contributing to the Zulip codebase. [Our
guide to Git](https://zulip.readthedocs.io/en/latest/git/index.html) will help
you get started even if you've never used Git before.

If you're familiar with Git, you'll still want to take a look at [our
Zulip-specific Git
tools](https://zulip.readthedocs.io/en/latest/git/zulip-tools.html).

### Setting up your development environment and diving in

To get started contributing code to Zulip, you will need to set up the
development environment for the Zulip codebase you want to work on. You'll then
want to take some time to familiarize yourself with the code.

#### Server and web app

1. [Install the development
   environment](https://zulip.readthedocs.io/en/latest/development/overview.html).
1. Familiarize yourself with [using the development
   environment](https://zulip.readthedocs.io/en/latest/development/using.html).
1. Go through the [new application feature
   tutorial](https://zulip.readthedocs.io/en/latest/tutorials/new-feature-tutorial.html)
   to get familiar with how the Zulip codebase is organized and how to find code
   in it.

#### Flutter-based mobile app

1. Set up a development environment following the instructions in [the project
   README](https://github.com/zulip/zulip-flutter).
1. Start reading recent commits to see the code we're writing.
   Use either a [graphical Git viewer][] like `gitk`, or `git log -p`
   with [the "secret" to reading its output][git-log-secret].
1. Pick some of the code that appears in those Git commits and that looks
   interesting. Use your IDE to visit that code and to navigate to related code,
   reading to see how it works and how the codebase is organized.

[graphical Git viewer]: https://zulip.readthedocs.io/en/latest/git/setup.html#get-a-graphical-client
[git-log-secret]: https://github.com/zulip/zulip-mobile/blob/main/docs/howto/git.md#git-log-secret

#### Desktop app

Follow [this
documentation](https://github.com/zulip/zulip-desktop/blob/main/development.md)
to set up the Zulip Desktop development environment.

#### Terminal app

Follow [this
documentation](https://github.com/zulip/zulip-terminal?tab=readme-ov-file#setting-up-a-development-environment)
to set up the Zulip Terminal development environment.

## Finding an issue to work on

::: note

**Note**: Project maintainers are not able to individually recommend issues to new
contributors. Learning how to find an issue you can tackle is one of the skills
new contributors need to learn.

:::

### Where to look for an issue

Now you're ready to pick your first issue! Zulip has several repositories you
can check out, depending on your interests. There are hundreds of open issues in
the [main Zulip server and web app
repository](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
alone.

You can look through issues tagged with the "help wanted" label, which is used
to indicate the issues that are open for contributions. You'll be able to claim
unassigned issues, which you can find using the `no:assignee` filter in GitHub.
You can also pick up issues that are assigned but are no longer being worked on.

Some repositories use the "good first issue" label to tag issues that are
especially approachable for new contributors.

Here are some handy links for issues to look through:

- [Server and web app](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Mobile app](https://github.com/zulip/zulip-flutter/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Desktop app](https://github.com/zulip/zulip-desktop/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Terminal app](https://github.com/zulip/zulip-terminal/issues?q=is%3Aopen+is%3Aissue+label%3A"help+wanted")
- [Python API bindings and bots](https://github.com/zulip/python-zulip-api/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)

### Picking an issue to work on

There's a lot to learn while making your first pull request, so start small!
Many first contributions have fewer than 10 lines of changes (not counting
changes to tests).

We recommend the following process for finding an issue to work on:

1. Find an issue tagged with the "help wanted" label that is either unassigned,
   or looks to be abandoned.
1. Read the description of the issue and make sure you understand it.
1. If it seems promising, poke around the product
   (on [chat.zulip.org](https://chat.zulip.org) or in the development
   environment) until you know how the piece being
   described fits into the bigger picture. If after some exploration the
   description seems confusing or ambiguous, post a question on the GitHub
   issue, as others may benefit from the clarification as well.
1. When you find an issue you like, try to get started working on it. See if you
   can find the part of the code you'll need to modify (`git grep` is your
   friend!) and get some idea of how you'll approach the problem.
1. If you feel lost, that's OK! Go through these steps again with another issue.
   There's plenty to work on, and the exploration you do will help you learn
   more about the project.

An assigned issue can be considered abandoned if:

- There is no recent contributor activity.
- There are no open PRs, or an open PR needs work in order to be ready for
  review. For example, a PR may need to be updated to address reviewer feedback
  or to pass tests.

Note that you are _not_ claiming an issue while you are iterating through steps
1-4. _Before you claim an issue_, you should be confident that you will be able to
tackle it effectively.

Additional tips for the [main server and web app
repository](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22):

- We especially recommend browsing recently opened issues, as there are more
  likely to be easy ones for you to find.
- Take a look at issues with the ["good first issue"
  label](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22),
  as they are especially accessible to new contributors. However, you will
  likely find issues without this label that are accessible as well.
- All issues are partitioned into areas like
  admin, compose, emoji, hotkeys, i18n, onboarding, search, etc. Look
  through our [list of labels](https://github.com/zulip/zulip/labels), and
  click on some of the `area:` labels to see all the issues related to your
  areas of interest.
- Avoid issues with the "difficult" label unless you
  understand why it is difficult and are highly confident you can resolve the
  issue correctly and completely.

### Claiming an issue

#### In the main server/web app repository and Zulip Terminal repository

The Zulip server/web app repository
([`zulip/zulip`](https://github.com/zulip/zulip/)) and the Zulip Terminal
repository ([`zulip/zulip-terminal`](https://github.com/zulip/zulip-terminal/))
are set up with a GitHub workflow bot called
[Zulipbot](https://github.com/zulip/zulipbot), which manages issues and pull
requests in order to create a better workflow for Zulip contributors.

To claim an issue in these repositories, simply post a comment that says
`@zulipbot claim` to the issue thread. If the issue is [tagged with a help
wanted label and is not assigned to someone
else](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22+no%3Aassignee),
Zulipbot will immediately assign the issue to you.

Note that new contributors can only claim one issue until their first pull request is
merged. This is to encourage folks to finish ongoing work before starting
something new. If you would like to pick up a new issue while waiting for review
on an almost-ready pull request, you can post a comment to this effect on the
issue you're interested in.

#### In other Zulip repositories

In other Zulip repositories, including
[`zulip/zulip-flutter`](https://github.com/zulip/zulip-flutter/),
there is no bot. Instead:

- Use the steps above to find an issue you'd like to work on
  and to get started working on it.
- Post a comment on the issue thread saying that you've started work
  on the issue and would like to claim it.
- In your comment, **describe what you learned in steps 1–4
  [above](#picking-an-issue-to-work-on)**: what part of the code
  you're modifying and how you plan to approach the problem.
- Once you've followed these steps, you've successfully claimed the issue.
  Go ahead and continue work on the issue, and send a PR when ready.
  Someone might come along and assign the issue to you for better
  tracking, but there's no need to wait for that or for any other
  form of permission.

There is no need to @-mention the issue creator in your comment. There is
also no need to post the same information in multiple places, for example in
a chat thread in addition to the GitHub issue.

Please follow the same guidelines as described above: find an issue labeled
"help wanted", and only pick up one issue at a time to start with.

## Getting help

You may have questions as you work on your pull request. For example, you might
not be sure about some details of what's required, or have questions about your
implementation approach. Zulip's maintainers are happy to answer thoughtfully
posed questions, and discuss any difficulties that might arise as you work on
your PR.

If you haven't done so yet, now is the time to join the [Zulip development
community](https://zulip.com/development-community/). If you'd like, introduce
yourself in the [#new
members](https://chat.zulip.org/#narrow/channel/95-new-members) channel, using
your name as the [topic](https://zulip.com/help/introduction-to-topics).

You can get help in public channels in the community:

1. **Review** the [Zulip development community
   guidelines](https://zulip.com/development-community/#community-norms).

1. **Decide where to post.** If there is a discussion thread linked from the
   issue you're working on, that's usually the best place to post any
   clarification questions about the issue. Otherwise, follow [these
   guidelines](https://zulip.com/development-community/#where-do-i-send-my-message)
   to figure out where to post your question. Don’t stress too much about
   picking the right place if you’re not sure, as moderators can [move your
   question thread to a different
   channel](https://zulip.com/help/move-content-to-another-channel) if needed.

1. **Write** up your question, being sure to follow our [guide on asking great
   questions](https://zulip.readthedocs.io/en/latest/contributing/asking-great-questions.html).
   The guide explains what you need to do make sure that folks will be able to
   help you out, and that you're making good use of maintainers' limited time.

1. **Review** your message before you send it. Will your question make sense to
   someone who is familiar with Zulip, but might not have the details of what
   you are working on fresh in mind?

Well-posed questions will generally get a response within 1-2 business days.
There is no need to @-mention anyone when you ask a question, as maintainers
keep a close eye on all the ongoing discussions.

## Best practices

As you're working on your first code contribution, here are some best practices
to keep in mind.

- [Asking great questions][great-questions]. It's very hard to answer a general
  question like, "How do I do this issue?" When asking for help, explain your
  current understanding, including what you've done or tried so far and where
  you got stuck. Post tracebacks or other error messages if appropriate. For
  more advice, check out [our guide][great-questions]!
- Learning and practicing
  [Git commit discipline](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html).
- Submitting carefully tested code. See our [detailed guide on how to review
  code](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#how-to-review-code)
  (yours or someone else's).
- Posting
  [screenshots or GIFs](https://zulip.readthedocs.io/en/latest/tutorials/screenshot-and-gif-software.html)
  for frontend changes.
- Working to [make your pull requests easy to
  review](https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html).
- Clearly describing what you have implemented and why. For example, if your
  implementation differs from the issue description in some way or is a partial
  step towards the requirements described in the issue, be sure to call
  out those differences.
- Being responsive to feedback on pull requests. This means incorporating or
  responding to all suggested changes, and leaving a note if you won't be
  able to address things within a few days.
- Being helpful and friendly on the [Zulip community
  server](https://zulip.com/development-community/).

[great-questions]: https://zulip.readthedocs.io/en/latest/contributing/asking-great-questions.html

## Submitting a pull request

See the [guide on submitting a pull
request](https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html)
for detailed instructions on how to present your proposed changes to Zulip.

The [pull request review process
guide](https://zulip.readthedocs.io/en/latest/contributing/review-process.html)
explains the stages of review your PR will go through, and offers guidance on
how to help the review process move forward.

It's OK if your first issue takes you a while; that's normal! You'll be able to
work a lot faster as you build experience.

## Beyond the first issue

To find a second issue to work on, we recommend looking through issues with the same
`area:` label as the last issue you resolved. You'll be able to reuse the
work you did learning how that part of the codebase works. Also, the path to
becoming a core developer often involves taking ownership of one of these area
labels.

## Common questions

### Picking up issues

- **Can I work on an issue that's not marked as "help wanted"?** The entire
  purpose of the "help wanted" label is to indicate which issues are open for
  contribution, so the answer is generally "no". Please feel free to ask if you
  have a _merged PR_ in a closely related part of the codebase, _and_ the issue
  has a clear product spec, and no obvious blockers. Otherwise, asking to claim
  an issue without a "help wanted" label clutters up comment threads, and wastes
  maintainer time.

- **What if somebody is already working on the issue I want to claim?** There
  are lots of issues to work on (likely
  [hundreds](https://github.com/zulip/zulip/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22help%20wanted%22%20no%3Aassignee)
  in the server repository)! If somebody else is actively working on the issue,
  you can find a different one, or help with reviewing their work.

- **What if it looks like the person who's assigned an issue is no longer
  working on it?** Post a comment on the issue, e.g., "Hi @ someone! Are you
  still working on this one? I'd like to pick it up if not." You can pick up the
  issue if they say they don't plan to work on it more.

  - **What if I don't get a response?** If you don't get a reply within 2-3
    days, go ahead and post a comment that you are working on the issue, and
    submit a pull request. If the original assignee ends up submitting a pull
    request first, no worries! You can help by providing feedback on their work,
    or submit your own PR if you think a different approach is needed (as
    described above).

- **What if there is already a pull request for the issue I want to work on?**
  See our [guide on continuing unfinished
  work](https://zulip.readthedocs.io/en/latest/contributing/continuing-unfinished-work.html).

- **What if somebody else claims an issue while I'm figuring out whether or not to
  work on it?** No worries! You can contribute by providing feedback on
  their pull request. If you've made good progress in understanding part of the
  codebase, you can also find another "help wanted" issue in the same area to
  work on.

- **Can I work on an old issue?** Of course! Open issues marked as “help wanted”
  are generally eligible to be worked on. If you find that the context around
  the issue has changed (e.g., the UI looks different), do your best to apply
  the current patterns, and comment on any differences from the spec in your PR
  description.

  If picking up a bug, start by checking if you can replicate it. If it no longer
  replicates, post a comment on the issue explaining how you tested the
  behavior, and what you saw, with screenshots as appropriate. And if you _can_
  replicate it, fixing it is great!

  If you're starting a major project where the issue was filed more than a
  couple of years ago, it's a good idea to post to the development community
  discussion thread for that issue to check if the thinking around it has
  changed.

- **Can I come up with my own feature idea and work on it?** We welcome
  suggestions for ways to make Zulip better based on your experience using the
  product. Please follow the guides on how to [report bugs][reporting-bugs] or
  [suggest features][suggesting-features]. However, please _do not_ suggest
  features just because you're looking for something to work on. It wastes
  maintainer time, and distracts the community from work that will truly help
  Zulip's users.
- **I'm waiting for the next round of review on my PR. Can I pick up
  another issue in the meantime?** Someone's first Zulip PR often
  requires quite a bit of iteration, so please [make sure your pull
  request is reviewable][reviewable-pull-requests] and go through at
  least one round of feedback from others before picking up a second
  issue. After that, sure! If
  [Zulipbot](https://github.com/zulip/zulipbot) does not allow you to
  claim an issue, you can post a comment describing the status of your
  other work on the issue you're interested in (including links to all open
  PRs), and asking for the issue to be assigned to you. Note that addressing
  feedback on in-progress PRs should always take priority over starting a new
  PR.

### Review process

- **I think my PR is done, but it hasn't been merged yet. What's going on?**
  1. **Double-check that you have addressed all the feedback**, including any comments
     on [Git commit
     discipline](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html),
     and that automated tests are passing.
  2. If all the feedback has been addressed, did you [leave a
     comment](https://zulip.readthedocs.io/en/latest/contributing/review-process.html#how-to-help-move-the-review-process-forward)
     explaining that you have done so and **requesting another review**? If not,
     it may not be clear to project maintainers or reviewers that your PR is
     ready for another look.
  3. There may be a pause between initial rounds of review for your PR and final
     review by project maintainers. This is normal, and we encourage you to **work
     on other issues** while you wait.
  4. If you think the PR is ready and haven't seen any updates for a couple
     of weeks, it can be helpful to **leave another comment**. Summarize the
     overall state of the review process and your work, and indicate that you
     are waiting for a review.
  5. Finally, **Zulip project maintainers are people too**! They may be busy
     with other work, and sometimes they might even take a vacation. ;) It can
     occasionally take a few weeks for a PR in the final stages of the review
     process to be merged.

[reviewable-pull-requests]: https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html
[suggesting-features]: https://zulip.readthedocs.io/en/latest/contributing/suggesting-features.html
[reporting-bugs]: https://zulip.readthedocs.io/en/latest/contributing/reporting-bugs.html

## Outreach programs

Zulip regularly participates in [Google Summer of Code
(GSoC)](https://developers.google.com/open-source/gsoc/). We have been a GSoC
mentoring organization since 2016, and we accept 10-20 GSoC participants each
summer. In the past, we’ve also participated in [Google
Code-In](https://developers.google.com/open-source/gci/) and
[Outreachy](https://www.outreachy.org/), and hosted summer interns from Harvard,
MIT, and Stanford.

Check out our [outreach programs
overview](https://zulip.readthedocs.io/en/latest/outreach/overview.html) to learn
more about participating in an outreach program with Zulip. Most of our program
participants end up sticking around the project long-term, and many have become
core team members, maintaining important parts of the project. We hope you
apply!
