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
  [frontend](https://github.com/zulip/zulip),
  Flutter [mobile app](https://github.com/zulip/zulip-flutter) in beta,
  or Electron [desktop app](https://github.com/zulip/zulip-desktop).
- Building out our
  [Python API and bots](https://github.com/zulip/python-zulip-api) framework.
- [Writing an integration](https://zulip.com/api/integrations-overview).
- Improving our [user](https://zulip.com/help/) or
  [developer](https://zulip.readthedocs.io/en/latest/) documentation.
- [Reviewing code](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html)
  and manually testing pull requests.

**Non-code contributions**: Some of the most valuable ways to contribute
don't require touching the codebase at all. For example, you can:

- Report issues, including both [feature
  requests](https://zulip.readthedocs.io/en/latest/contributing/suggesting-features.html)
  and [bug
  reports](https://zulip.readthedocs.io/en/latest/contributing/reporting-bugs.html).
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
  paying special attention to the
  [community norms](https://zulip.com/development-community/#community-norms).
  If you'd like, introduce yourself in
  [#new members](https://chat.zulip.org/#narrow/stream/95-new-members), using
  your name as the topic. Bonus: tell us about your first impressions of
  Zulip, and anything that felt confusing/broken or interesting/helpful as you
  started using the product.

- Read [What makes a great Zulip contributor](#what-makes-a-great-zulip-contributor).

- Set up the development environment for the Zulip codebase you want
  to work on, and start getting familiar with the code.

  - For the server and web app:

    - [Install the development environment](https://zulip.readthedocs.io/en/latest/development/overview.html),
      getting help in
      [#provision help](https://chat.zulip.org/#narrow/stream/21-provision-help)
      if you run into any troubles.
    - Familiarize yourself with [using the development environment](https://zulip.readthedocs.io/en/latest/development/using.html).
    - Go through the [new application feature
      tutorial](https://zulip.readthedocs.io/en/latest/tutorials/new-feature-tutorial.html) to get familiar with
      how the Zulip codebase is organized and how to find code in it.

  - For the upcoming Flutter-based mobile app:
    - Set up a development environment following the instructions in
      [the project README](https://github.com/zulip/zulip-flutter).
    - Start reading recent commits to see the code we're writing.
      Use either a [graphical Git viewer][] like `gitk`, or `git log -p`
      with [the "secret" to reading its output][git-log-secret].
    - Pick some of the code that appears in those Git commits and
      that looks interesting. Use your IDE to visit that code
      and to navigate to related code, reading to see how it works
      and how the codebase is organized.

- Read the [Zulip guide to
  Git](https://zulip.readthedocs.io/en/latest/git/index.html) if you
  are unfamiliar with Git or Zulip's rebase-based Git workflow,
  getting help in [#git
  help](https://chat.zulip.org/#narrow/stream/44-git-help) if you run
  into any troubles. Even Git experts should read the [Zulip-specific
  Git tools
  page](https://zulip.readthedocs.io/en/latest/git/zulip-tools.html).

[graphical Git viewer]: https://zulip.readthedocs.io/en/latest/git/setup.html#get-a-graphical-client
[git-log-secret]: https://github.com/zulip/zulip-mobile/blob/main/docs/howto/git.md#git-log-secret

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
- Mobile apps: no "help wanted" label, but see the
  [project board](https://github.com/orgs/zulip/projects/5/views/4)
  for the upcoming Flutter-based app. Look for issues up through the
  "Launch" milestone, and that aren't already assigned.
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
([`zulip/zulip-flutter`](https://github.com/zulip/zulip-flutter/), etc.). If
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
contributor?](#what-makes-a-great-zulip-contributor) below. It's OK if your
first issue takes you a while; that's normal! You'll be able to work a lot
faster as you build experience.

### Submitting a pull request

See the [guide on submitting a pull
request](https://zulip.readthedocs.io/en/latest/contributing/reviewable-prs.html)
for detailed instructions on how to present your proposed changes to Zulip.

The [pull request review process
guide](https://zulip.readthedocs.io/en/latest/contributing/review-process.html)
explains the stages of review your PR will go through, and offers guidance on
how to help the review process move forward.

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
- **What if I ask if someone is still working on an issue, and they don't
  respond?** If you don't get a reply within 2-3 days, go ahead and post a comment
  that you are working on the issue, and submit a pull request. If the original
  assignee ends up submitting a pull request first, no worries! You can help by
  providing feedback on their work, or submit your own PR if you think a
  different approach is needed (as described above).
- **Can I come up with my own feature idea and work on it?** We welcome
  suggestions of features or other improvements that you feel would be valuable. If you
  have a new feature you'd like to add, you can start a conversation [in our
  development community](https://zulip.com/development-community/#where-do-i-send-my-message)
  explaining the feature idea and the problem that you're hoping to solve.
- **I'm waiting for the next round of review on my PR. Can I pick up
  another issue in the meantime?** Someone's first Zulip PR often
  requires quite a bit of iteration, so please [make sure your pull
  request is reviewable][reviewable-pull-requests] and go through at
  least one round of feedback from others before picking up a second
  issue. After that, sure! If
  [Zulipbot](https://github.com/zulip/zulipbot) does not allow you to
  claim an issue, you can post a comment describing the status of your
  other work on the issue you're interested in, and asking for the
  issue to be assigned to you. Note that addressing feedback on
  in-progress PRs should always take priority over starting a new PR.
- **I think my PR is done, but it hasn't been merged yet. What's going on?**
  1. **Double-check that you have addressed all the feedback**, including any comments
     on [Git commit
     discipline](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html).
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
  [Flutter mobile](https://github.com/zulip/zulip-flutter),
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
