# Contributing guide

Welcome to the Zulip community!

## Zulip development community

The primary communication forum for the Zulip community is the Zulip
server hosted at [chat.zulip.org](https://chat.zulip.org/):

- **Users** and **administrators** of Zulip organizations stop by to
  ask questions, offer feedback, and participate in product design
  discussions.
- **Contributors to the project**, including the **core Zulip
  development team**, discuss ongoing and future projects, brainstorm
  ideas, and generally help each other out.

Everyone is welcome to [sign up](https://chat.zulip.org/) and
participate — we love hearing from our users! Public streams in the
community receive thousands of messages a week. We recommend signing
up using the special invite links for
[users](https://chat.zulip.org/join/t5crtoe62bpcxyisiyglmtvb/),
[self-hosters](https://chat.zulip.org/join/wnhv3jzm6afa4raenedanfno/)
and
[contributors](https://chat.zulip.org/join/npzwak7vpmaknrhxthna3c7p/)
to get a curated list of initial stream subscriptions.

To learn how to get started participating in the community, including [community
norms](https://zulip.com/development-community/#community-norms) and [where to
post](https://zulip.com/development-community/#where-do-i-send-my-message),
check out our [Zulip development community
guide](https://zulip.com/development-community/). The Zulip community is
governed by a [code of
conduct](https://zulip.readthedocs.io/en/latest/code-of-conduct.html).

## Ways to contribute

To make a code or documentation contribution, read our
[step-by-step guide](#your-first-codebase-contribution) to getting
started with the Zulip codebase. A small sample of the type of work that
needs doing:

- Bug squashing and feature development on our Python/Django
  [backend](https://github.com/zulip/zulip), web
  [frontend](https://github.com/zulip/zulip), React Native
  [mobile app](https://github.com/zulip/zulip-mobile), or Electron
  [desktop app](https://github.com/zulip/zulip-desktop).
- Building out our
  [Python API and bots](https://github.com/zulip/python-zulip-api) framework.
- [Writing an integration](https://zulip.com/api/integrations-overview).
- Improving our [user](https://zulip.com/help/) or
  [developer](https://zulip.readthedocs.io/en/latest/) documentation.
- [Reviewing code](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html)
  and manually testing pull requests.

**Non-code contributions**: Some of the most valuable ways to contribute
don't require touching the codebase at all. For example, you can:

- [Report issues](#reporting-issues), including both feature requests and
  bug reports.
- [Give feedback](#user-feedback) if you are evaluating or using Zulip.
- [Participate
  thoughtfully](https://zulip.readthedocs.io/en/latest/contributing/design-discussions.html)
  in design discussions.
- [Sponsor Zulip](https://github.com/sponsors/zulip) through the GitHub sponsors program.
- [Translate](https://zulip.readthedocs.io/en/latest/translating/translating.html)
  Zulip into your language.
- [Stay connected](#stay-connected) with Zulip, and [help others
  find us](#help-others-find-zulip).

## Your first codebase contribution

This section has a step by step guide to starting as a Zulip codebase
contributor. It's long, but don't worry about doing all the steps perfectly;
no one gets it right the first time, and there are a lot of people available
to help.

- First, make an account on the
  [Zulip community server](https://zulip.com/development-community/),
  paying special attention to the community norms. If you'd like, introduce
  yourself in
  [#new members](https://chat.zulip.org/#narrow/stream/95-new-members), using
  your name as the topic. Bonus: tell us about your first impressions of
  Zulip, and anything that felt confusing/broken as you started using the
  product.
- Read [What makes a great Zulip contributor](#what-makes-a-great-zulip-contributor).
- [Install the development environment](https://zulip.readthedocs.io/en/latest/development/overview.html),
  getting help in
  [#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
  if you run into any troubles.
- Familiarize yourself with [using the development environment](https://zulip.readthedocs.io/en/latest/development/using.html).
- Go through the [new application feature
  tutorial](https://zulip.readthedocs.io/en/latest/tutorials/new-feature-tutorial.html) to get familiar with
  how the Zulip codebase is organized and how to find code in it.
- Read the [Zulip guide to
  Git](https://zulip.readthedocs.io/en/latest/git/index.html) if you
  are unfamiliar with Git or Zulip's rebase-based Git workflow,
  getting help in [#git
  help](https://chat.zulip.org/#narrow/stream/44-git-help) if you run
  into any troubles. Even Git experts should read the [Zulip-specific
  Git tools
  page](https://zulip.readthedocs.io/en/latest/git/zulip-tools.html).

### Where to look for an issue

Now you're ready to pick your first issue! Zulip has several repositories you
can check out, depending on your interests. There are hundreds of open issues in
the [main Zulip server and web app
repository](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
alone.

You can look through issues tagged with the "help wanted" label, which is used
to indicate the issues that are ready for contributions. Some repositories also
use the "good first issue" label to tag issues that are especially approachable
for new contributors.

- [Server and web app](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Mobile apps](https://github.com/zulip/zulip-mobile/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Desktop app](https://github.com/zulip/zulip-desktop/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
- [Terminal app](https://github.com/zulip/zulip-terminal/issues?q=is%3Aopen+is%3Aissue+label%3A"help+wanted")
- [Python API bindings and bots](https://github.com/zulip/python-zulip-api/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)

### Picking an issue to work on

There's a lot to learn while making your first pull request, so start small!
Many first contributions have fewer than 10 lines of changes (not counting
changes to tests).

We recommend the following process for finding an issue to work on:

1. Read the description of an issue tagged with the "help wanted" label and make
   sure you understand it.
2. If it seems promising, poke around the product
   (on [chat.zulip.org](https://chat.zulip.org) or in the development
   environment) until you know how the piece being
   described fits into the bigger picture. If after some exploration the
   description seems confusing or ambiguous, post a question on the GitHub
   issue, as others may benefit from the clarification as well.
3. When you find an issue you like, try to get started working on it. See if you
   can find the part of the code you'll need to modify (`git grep` is your
   friend!) and get some idea of how you'll approach the problem.
4. If you feel lost, that's OK! Go through these steps again with another issue.
   There's plenty to work on, and the exploration you do will help you learn
   more about the project.

Note that you are _not_ claiming an issue while you are iterating through steps
1-4. _Before you claim an issue_, you should be confident that you will be able to
tackle it effectively.

If the lists of issues are overwhelming, you can post in
[#new members](https://chat.zulip.org/#narrow/stream/95-new-members) with a
bit about your background and interests, and we'll help you out. The most
important thing to say is whether you're looking for a backend (Python),
frontend (JavaScript and TypeScript), mobile (React Native), desktop (Electron),
documentation (English) or visual design (JavaScript/TypeScript + CSS) issue, and a
bit about your programming experience and available time.

Additional tips for the [main server and web app
repository](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22):

- We especially recommend browsing recently opened issues, as there are more
  likely to be easy ones for you to find.
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
`@zulipbot claim` to the issue thread. If the issue is tagged with a [help
wanted](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
label, Zulipbot will immediately assign the issue to you.

Note that new contributors can only claim one issue until their first pull request is
merged. This is to encourage folks to finish ongoing work before starting
something new. If you would like to pick up a new issue while waiting for review
on an almost-ready pull request, you can post a comment to this effect on the
issue you're interested in.

#### In other Zulip repositories

There is no bot for other Zulip repositories
([`zulip/zulip-mobile`](https://github.com/zulip/zulip-mobile/), etc.). If
you are interested in claiming an issue in one of these repositories, simply
post a comment on the issue thread saying that you'd like to work on it. There
is no need to @-mention the issue creator in your comment.

Please follow the same guidelines as described above: find an issue labeled
"help wanted", and only pick up one issue at a time to start with.

### Working on an issue

You're encouraged to ask questions on how to best implement or debug your
changes -- the Zulip maintainers are excited to answer questions to help you
stay unblocked and working efficiently. You can ask questions in the [Zulip
development community](https://zulip.com/development-community/), or on the
GitHub issue or pull request.

To get early feedback on any UI changes, we encourage you to post screenshots of
your work in the [#design
stream](https://chat.zulip.org/#narrow/stream/101-design) in the [Zulip
development community](https://zulip.com/development-community/)

For more advice, see [What makes a great Zulip
contributor?](#what-makes-a-great-zulip-contributor)
below.

### Submitting a pull request

When you believe your code is ready, follow the [guide on how to review
code](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#how-to-review-code)
to review your own work. You can often find things you missed by taking a step
back to look over your work before asking others to do so. Catching mistakes
yourself will help your PRs be merged faster, and folks will appreciate the
quality and professionalism of your work.

Then, submit your changes. Carefully reading our [Git guide][git-guide], and in
particular the section on [making a pull request][git-guide-make-pr], will help
avoid many common mistakes. If any part of your contribution is from someone
else (code snippets, images, sounds, or any other copyrightable work, modified
or unmodified), be sure to review the instructions on how to [properly
attribute][licensing] the work.

[licensing]: https://zulip.readthedocs.io/en/latest/contributing/licensing.html#contributing-someone-else-s-work

Once you are satisfied with the quality of your PR, follow the
[guidelines on asking for a code
review](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#asking-for-a-code-review)
to request a review. If you are not sure what's best, simply post a
comment on the main GitHub thread for your PR clearly indicating that
it is ready for review, and the project maintainers will take a look
and follow up with next steps.

It's OK if your first issue takes you a while; that's normal! You'll be
able to work a lot faster as you build experience.

If it helps your workflow, you can submit your pull request marked as
a [draft][github-help-draft-pr] while you're still working on it, and
then mark it ready when you think it's time for someone else to review
your work.

[git-guide]: https://zulip.readthedocs.io/en/latest/git/
[git-guide-make-pr]: https://zulip.readthedocs.io/en/latest/git/pull-requests.html
[github-help-draft-pr]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests

### Stages of a pull request

Your pull request will likely go through several stages of review.

1. If your PR makes user-facing changes, the UI and user experience may be
   reviewed early on, without reference to the code. You will get feedback on
   any user-facing bugs in the implementation. To minimize the number of review
   round-trips, make sure to [thoroughly
   test](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#manual-testing)
   your own PR prior to asking for review.
2. There may be choices made in the implementation that the reviewer
   will ask you to revisit. This process will go more smoothly if you
   specifically call attention to the decisions you made while
   drafting the PR and any points about which you are uncertain. The
   PR description and comments on your own PR are good ways to do this.
3. Oftentimes, seeing an initial implementation will make it clear that the
   product design for a feature needs to be revised, or that additional changes
   are needed. The reviewer may therefore ask you to amend or change the
   implementation. Some changes may be blockers for getting the PR merged, while
   others may be improvements that can happen afterwards. Feel free to ask if
   it's unclear which type of feedback you're getting. (Follow-ups can be a
   great next issue to work on!)
4. In addition to any UI/user experience review, all PRs will go through one or
   more rounds of code review. Your code may initially be [reviewed by other
   contributors](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html).
   This helps us make good use of project maintainers' time, and helps you make
   progress on the PR by getting more frequent feedback. A project maintainer
   may leave a comment asking someone with expertise in the area you're working
   on to review your work.
5. Final code review and integration for server and web app PRs is generally done
   by `@timabbott`.

#### How to help move the review process forward

The key to keeping your review moving through the review process is to:

- Address _all_ the feedback to the best of your ability.
- Make it clear when the requested changes have been made
  and you believe it's time for another look.
- Make it as easy as possible to review the changes you made.

In order to do this, when you believe you have addressed the previous round of
feedback on your PR as best you can, post a comment asking reviewers to take
another look. Your comment should make it easy to understand what has been done
and what remains by:

- Summarizing the changes made since the last review you received.
- Highlighting remaining questions or decisions, with links to any relevant
  chat.zulip.org threads.
- Providing updated screenshots and information on manual testing if
  appropriate.

The easier it is to review your work, the more likely you are to receive quick
feedback.

### Beyond the first issue

To find a second issue to work on, we recommend looking through issues with the same
`area:` label as the last issue you resolved. You'll be able to reuse the
work you did learning how that part of the codebase works. Also, the path to
becoming a core developer often involves taking ownership of one of these area
labels.

### Common questions

- **What if somebody is already working on the issue I want do claim?** There
  are lots of issue to work on! If somebody else is actively working on the
  issue, you can find a different one, or help with
  reviewing their work.
- **What if somebody else claims an issue while I'm figuring out whether or not to
  work on it?** No worries! You can contribute by providing feedback on
  their pull request. If you've made good progress in understanding part of the
  codebase, you can also find another "help wanted" issue in the same area to
  work on.
- **What if there is already a pull request for the issue I want to work on?**
  Start by reviewing the existing work. If you agree with the approach, you can
  use the existing pull request (PR) as a starting point for your contribution. If
  you think a different approach is needed, you can post a new PR, with a comment that clearly
  explains _why_ you decided to start from scratch.
- **Can I come up with my own feature idea and work on it?** We welcome
  suggestions of features or other improvements that you feel would be valuable. If you
  have a new feature you'd like to add, you can start a conversation [in our
  development community](https://zulip.com/development-community/#where-do-i-send-my-message)
  explaining the feature idea and the problem that you're hoping to solve.
- **I think my PR is done, but it hasn't been merged yet. What's going on?**
  1. **Double-check that you have addressed all the feedback**, including any comments
     on [Git commit
     discipline](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html).
  2. If all the feedback has been addressed, did you [leave a
     comment](#how-to-help-move-the-review-process-forward)
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

## What makes a great Zulip contributor?

Zulip has a lot of experience working with new contributors. In our
experience, these are the best predictors of success:

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

## Reporting issues

If you find an easily reproducible bug and/or are experienced in reporting
bugs, feel free to just open an issue on the relevant project on GitHub.

If you have a feature request or are not yet sure what the underlying bug
is, the best place to post issues is
[#issues](https://chat.zulip.org/#narrow/stream/9-issues) (or
[#mobile](https://chat.zulip.org/#narrow/stream/48-mobile) or
[#desktop](https://chat.zulip.org/#narrow/stream/16-desktop)) on the
[Zulip community server](https://zulip.com/development-community/).
This allows us to interactively figure out what is going on, let you know if
a similar issue has already been opened, and collect any other information
we need. Choose a 2-4 word topic that describes the issue, explain the issue
and how to reproduce it if known, your browser/OS if relevant, and a
[screenshot or screenGIF](https://zulip.readthedocs.io/en/latest/tutorials/screenshot-and-gif-software.html)
if appropriate.

**Reporting security issues**. Please do not report security issues
publicly, including on public streams on chat.zulip.org. You can
email [security@zulip.com](mailto:security@zulip.com). We create a CVE for every
security issue in our released software.

## User feedback

Nearly every feature we develop starts with a user request. If you are part
of a group that is either using or considering using Zulip, we would love to
hear about your experience with the product. If you're not sure what to
write, here are some questions we're always very curious to know the answer
to:

- Evaluation: What is the process by which your organization chose or will
  choose a group chat product?
- Pros and cons: What are the pros and cons of Zulip for your organization,
  and the pros and cons of other products you are evaluating?
- Features: What are the features that are most important for your
  organization? In the best-case scenario, what would your chat solution do
  for you?
- Onboarding: If you remember it, what was your impression during your first
  few minutes of using Zulip? What did you notice, and how did you feel? Was
  there anything that stood out to you as confusing, or broken, or great?
- Organization: What does your organization do? How big is the organization?
  A link to your organization's website?

You can contact us in the [#feedback stream of the Zulip development
community](https://chat.zulip.org/#narrow/stream/137-feedback) or
by emailing [support@zulip.com](mailto:support@zulip.com).

## Outreach programs

Zulip regularly participates in [Google Summer of Code
(GSoC)](https://developers.google.com/open-source/gsoc/) and
[Outreachy](https://www.outreachy.org/). We have been a GSoC mentoring
organization since 2016, and we accept 15-20 GSoC participants each summer. In
the past, we’ve also participated in [Google
Code-In](https://developers.google.com/open-source/gci/), and hosted summer
interns from Harvard, MIT, and Stanford.

Check out our [outreach programs
overview](https://zulip.readthedocs.io/en/latest/outreach/overview.html) to learn
more about participating in an outreach program with Zulip. Most of our program
participants end up sticking around the project long-term, and many have become
core team members, maintaining important parts of the project. We hope you
apply!

## Stay connected

Even if you are not logging into the development community on a regular basis,
you can still stay connected with the project.

- Follow us [on Twitter](https://twitter.com/zulip).
- Subscribe to [our blog](https://blog.zulip.org/).
- Join or follow the project [on LinkedIn](https://www.linkedin.com/company/zulip-project/).

## Help others find Zulip

Here are some ways you can help others find Zulip:

- Star us on GitHub. There are four main repositories:
  [server/web](https://github.com/zulip/zulip),
  [mobile](https://github.com/zulip/zulip-mobile),
  [desktop](https://github.com/zulip/zulip-desktop), and
  [Python API](https://github.com/zulip/python-zulip-api).

- "Like" and retweet [our tweets](https://twitter.com/zulip).

- Upvote and post feedback on Zulip on comparison websites. A couple specific
  ones to highlight:

  - [AlternativeTo](https://alternativeto.net/software/zulip-chat-server/). You can also
    [upvote Zulip](https://alternativeto.net/software/slack/) on their page
    for Slack.
  - [Add Zulip to your stack](https://stackshare.io/zulip) on StackShare, star
    it, and upvote the reasons why people like Zulip that you find most
    compelling.
