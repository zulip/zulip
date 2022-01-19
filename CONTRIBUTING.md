# Contributing to Zulip

Welcome to the Zulip community!

## Community

The
[Zulip community server](https://zulip.com/development-community/)
is the primary communication forum for the Zulip community. It is a good
place to start whether you have a question, are a new contributor, are a new
user, or anything else. Please review our
[community norms](https://zulip.com/development-community/#community-norms)
before posting. The Zulip community is also governed by a
[code of conduct](https://zulip.readthedocs.io/en/latest/code-of-conduct.html).

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

Any issue with the "good first issue"
label is a good candidate when you are getting started. In addition, many of the
issues with the "help wanted" label may be approachable as well.

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

1. Read the description of an issue and make sure you understand it.
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

#### In the main server and web app repository

Post a comment with `@zulipbot claim` to
the issue thread. [Zulipbot](https://github.com/zulip/zulipbot) is a GitHub
workflow bot; it will assign you to the issue and label the issue as "in
progress". You can only claim issues with the
[good first issue](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22)
or
[help wanted](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
labels. Zulipbot will give you an error if you try to claim an issue
without one of those labels.

New contributors can only claim one issue until their first pull request is
merged. This is to encourage folks to finish ongoing work before starting
something new. If you would like to pick up a new issue while waiting for review
on an almost-ready pull request, you can post a comment to this effect on the
issue you're interested in.

#### In other Zulip repositories

There is no bot for other repositories, so you can simply post a comment saying
that you'd like to work on the issue.

Please follow the same guidelines as described above: find an issue labeled
"good first issue" or "help wanted", and only pick up one issue at a time to
start with.

### Working on an issue

- You're encouraged to ask questions on how to best implement or debug your
  changes -- the Zulip maintainers are excited to answer questions to help
  you stay unblocked and working efficiently. You can ask questions in the
  [Zulip development community](https://zulip.com/development-community/),
  or on the GitHub issue or pull request.
- We encourage early pull requests for work in progress. Prefix the title of
  work in progress pull requests with `[WIP]`, and remove the prefix when
  you think it might be mergeable and want it to be reviewed.
- After updating a PR, add a comment to the GitHub thread mentioning that it
  is ready for another review. GitHub only notifies maintainers of the
  changes when you post a comment, so if you don't, your PR will likely be
  neglected by accident!

It's OK if your first issue takes you a while; that's normal! You'll be
able to work a lot faster as you build experience.

For more advice, see [What makes a great Zulip
contributor?](https://zulip.readthedocs.io/en/latest/overview/contributing.html#what-makes-a-great-zulip-contributor)
below.

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
     discipline](https://zulip.readthedocs.io/en/latest/contributing/version-control.html#commit-discipline).
  2. If all the feedback has been addressed, did you leave a comment explaining that
     you have done so and **requesting another review**? If not, it may not be a
     clear to project maintainers that your PR is ready for another look.
  3. It is common for PRs to require **multiple rounds of review**. For example,
     prior to getting code review from project maintainers, you may receive
     feedback on the UI (without regard for the implementation), and your code
     may be [reviewed by other
     contributors](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html).
     This helps us make good use of project maintainers' time, and helps you
     make progress on the PR by getting more frequent feedback.
  4. If you think the PR is ready and haven't seen any updates for a couple
     of weeks, it can be helpful to post a **comment summarizing your
     understanding of the state of the review process**. Your comment should
     make it easy to understand what has been done and what remains by:
     - Summarizing the changes made since the last review you received.
     - Highlighting remaining questions or decisions, with links to any
       relevant chat.zulip.org threads.
     - Providing updated screenshots and information on manual testing if
       appropriate.
  5. Finally, **Zulip project maintainers are people too**! They may be busy
     with other work, and sometimes they might even take a vacation. ;) It can
     occasionally take a few weeks for a PR in the final stages of the review
     process to be merged.

## What makes a great Zulip contributor?

Zulip has a lot of experience working with new contributors. In our
experience, these are the best predictors of success:

- Posting good questions. It's very hard to answer a general question like, "How
  do I do this issue?" When asking for help, explain
  your current understanding, including what you've done or tried so far and where
  you got stuck. Post tracebacks or other error messages if appropriate. For
  more information, check out the ["Getting help" section of our community
  guidelines](https://zulip.com/development-community/#getting-help) and
  [this essay][good-questions-blog] for some good advice.
- Learning and practicing
  [Git commit discipline](https://zulip.readthedocs.io/en/latest/contributing/version-control.html#commit-discipline).
- Submitting carefully tested code. This generally means checking your work
  through a combination of automated tests and manually clicking around the
  UI trying to find bugs in your work. See
  [things to look for](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#things-to-look-for)
  for additional ideas.
- Posting
  [screenshots or GIFs](https://zulip.readthedocs.io/en/latest/tutorials/screenshot-and-gif-software.html)
  for frontend changes.
- Clearly describing what you have implemented and why. For example, if your
  implementation differs from the issue description in some way or is a partial
  step towards the requirements described in the issue, be sure to call
  out those differences.
- Being responsive to feedback on pull requests. This means incorporating or
  responding to all suggested changes, and leaving a note if you won't be
  able to address things within a few days.
- Being helpful and friendly on chat.zulip.org.

[good-questions-blog]: https://jvns.ca/blog/good-questions/

These are also the main criteria we use to select candidates for all
of our outreach programs.

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

Zulip participates in [Google Summer of Code
(GSoC)](https://developers.google.com/open-source/gsoc/) every year.
In the past, we've also participated in
[Outreachy](https://www.outreachy.org/), [Google
Code-In](https://developers.google.com/open-source/gci/), and hosted
summer interns from Harvard, MIT, and Stanford.

While each third-party program has its own rules and requirements, the
Zulip community's approaches all of these programs with these ideas in
mind:

- We try to make the application process as valuable for the applicant as
  possible. Expect high-quality code reviews, a supportive community, and
  publicly viewable patches you can link to from your resume, regardless of
  whether you are selected.
- To apply, you'll have to submit at least one pull request to a Zulip
  repository. Most students accepted to one of our programs have
  several merged pull requests (including at least one larger PR) by
  the time of the application deadline.
- The main criteria we use is quality of your best contributions, and
  the bullets listed at
  [What makes a great Zulip contributor](#what-makes-a-great-zulip-contributor).
  Because we focus on evaluating your best work, it doesn't hurt your
  application to makes mistakes in your first few PRs as long as your
  work improves.

Most of our outreach program participants end up sticking around the
project long-term, and many have become core team members, maintaining
important parts of the project. We hope you apply!

### Google Summer of Code

The largest outreach program Zulip participates in is GSoC (14
students in 2017; 11 in 2018; 17 in 2019; 18 in 2020; 18 in 2021). While we
don't control how
many slots Google allocates to Zulip, we hope to mentor a similar
number of students in future summers. Check out our [blog
post](https://blog.zulip.com/2021/09/30/google-summer-of-code-2021/) to learn
about the GSoC 2021 experience and our participants' accomplishments.

If you're reading this well before the application deadline and want
to make your application strong, we recommend getting involved in the
community and fixing issues in Zulip now. Having good contributions
and building a reputation for doing good work is the best way to have
a strong application.

Our [GSoC program page][gsoc-guide] has lots more details on how
Zulip does GSoC, as well as project ideas. Note, however, that the project idea
list is maintained only during the GSoC application period, so if
you're looking at some other time of year, the project list is likely
out-of-date.

In some years, we have also run a Zulip Summer of Code (ZSoC)
program for students who we wanted to accept into GSoC but did not have an
official slot for. Student expectations are the
same as with GSoC, and ZSoC has no separate application process; your
GSoC application is your ZSoC application. If we'd like to select you
for ZSoC, we'll contact you when the GSoC results are announced.

[gsoc-guide]: https://zulip.readthedocs.io/en/latest/contributing/gsoc.html
[gsoc-faq]: https://developers.google.com/open-source/gsoc/faq

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
