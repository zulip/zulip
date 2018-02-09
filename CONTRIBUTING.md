# Contributing to Zulip

Welcome to the Zulip community!

## Community

The
[Zulip community server](https://zulip.readthedocs.io/en/latest/contributing/chat-zulip-org.html)
is the primary communication forum for the Zulip community. It is a good
place to start whether you have a question, are a new contributor, are a new
user, or anything else. Make sure to read the
[community norms](https://zulip.readthedocs.io/en/latest/contributing/chat-zulip-org.html#community-norms)
before posting. The Zulip community is also governed by a
[code of conduct](https://zulip.readthedocs.io/en/latest/code-of-conduct.html).

You can subscribe to zulip-devel@googlegroups.com for a lower traffic (~1
email/month) way to hear about things like mentorship opportunities with Google
Code-in, in-person sprints at conferences, and other opportunities to
contribute.

## Ways to contribute

To make a code or documentation contribution, read our
[step-by-step guide](#your-first-codebase-contribution) to getting
started with the Zulip codebase. A small sample of the type of work that
needs doing:
* Bug squashing and feature development on our Python/Django
  [backend](https://github.com/zulip/zulip), web
  [frontend](https://github.com/zulip/zulip), React Native
  [mobile app](https://github.com/zulip/zulip-mobile), or Electron
  [desktop app](https://github.com/zulip/zulip-electron).
* Building out our
  [Python API and bots](https://github.com/zulip/python-zulip-api) framework.
* [Writing an integration](https://zulipchat.com/api/integration-guide).
* Improving our [user](https://zulipchat.com/help/) or
  [developer](https://zulip.readthedocs.io/en/latest/) documentation.
* [Reviewing code](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html)
  and manually testing pull requests.

**Non-code contributions**: Some of the most valuable ways to contribute
don't require touching the codebase at all. We list a few of them below:

* [Reporting issues](#reporting-issues), including both feature requests and
  bug reports.
* [Giving feedback](#user-feedback) if you are evaluating or using Zulip.
* [Translating](https://zulip.readthedocs.io/en/latest/translating/translating.html)
  Zulip.
* [Outreach](#zulip-outreach): Star us on GitHub, upvote us
  on product comparison sites, or write for [the Zulip blog](http://blog.zulip.org/).

## Your first (codebase) contribution

This section has a step by step guide to starting as a Zulip codebase
contributor. It's long, but don't worry about doing all the steps perfectly;
no one gets it right the first time, and there are a lot of people available
to help.
* First, make an account on the
  [Zulip community server](https://zulip.readthedocs.io/en/latest/contributing/chat-zulip-org.html),
  paying special attention to the community norms. If you'd like, introduce
  yourself in
  [#new members](https://chat.zulip.org/#narrow/stream/new.20members), using
  your name as the topic. Bonus: tell us about your first impressions of
  Zulip, and anything that felt confusing/broken as you started using the
  product.
* Read [What makes a great Zulip contributor](#what-makes-a-great-zulip-contributor).
* [Install the development environment](https://zulip.readthedocs.io/en/latest/development/overview.html),
  getting help in
  [#development help](https://chat.zulip.org/#narrow/stream/development.20help)
  if you run into any troubles.
* Read the
  [Zulip guide to Git](https://zulip.readthedocs.io/en/latest/git/index.html)
  and do the Git tutorial (coming soon) if you are unfamiliar with Git,
  getting help in
  [#git help](https://chat.zulip.org/#narrow/stream/git.20help) if you run
  into any troubles.
* Sign the
  [Dropbox Contributor License Agreement](https://opensource.dropbox.com/cla/).

### Picking an issue

Now, you're ready to pick your first issue! There are hundreds of open issues
in the main codebase alone. This section will help you find an issue to work
on.

* If you're interested in
  [mobile](https://github.com/zulip/zulip-mobile/issues?q=is%3Aopen+is%3Aissue),
  [desktop](https://github.com/zulip/zulip-electron/issues?q=is%3Aopen+is%3Aissue),
  or
  [bots](https://github.com/zulip/python-zulip-api/issues?q=is%3Aopen+is%3Aissue)
  development, check the respective links for open issues, or post in
  [#mobile](https://chat.zulip.org/#narrow/stream/mobile),
  [#electron](https://chat.zulip.org/#narrow/stream/electron), or
  [#bots](https://chat.zulip.org/#narrow/stream/bots).
* For the main server and web repository, start by looking through issues
  with the label
  [good first issue](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A"good+first+issue").
  These are smaller projects particularly suitable for a first contribution.
* We also partition all of our issues in the main repo into areas like
  admin, compose, emoji, hotkeys, i18n, onboarding, search, etc. Look
  through our [list of labels](https://github.com/zulip/zulip/labels), and
  click on some of the `area:` labels to see all the issues related to your
  areas of interest.
* If the lists of issues are overwhelming, post in
  [#new members](https://chat.zulip.org/#narrow/stream/new.20members) with a
  bit about your background and interests, and we'll help you out. The most
  important thing to say is whether you're looking for a backend (Python),
  frontend (JavaScript), mobile (React Native), desktop (Electron),
  documentation (English) or visual design (JavaScript + CSS) issue, and a
  bit about your programming experience and available time.

We also welcome suggestions of features that you feel would be valuable or
changes that you feel would make Zulip a better open source project. If you
have a new feature you'd like to add, we recommend you start by posting in
[#new members](https://chat.zulip.org/#narrow/stream/new.20members) with the
feature idea and the problem that you're hoping to solve.

Other notes:
* For a first pull request, it's better to aim for a smaller contribution
  than a bigger one. Many first contributions have fewer than 10 lines of
  changes (not counting changes to tests).
* The full list of issues looking for a contributor can be found with the
  [help wanted](https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22)
  label.
* For most new contributors, there's a lot to learn while making your first
  pull request. It's OK if it takes you a while; that's normal! You'll be
  able to work a lot faster as you build experience.

### Working on an issue

To work on an issue, claim it by adding a comment with `@zulipbot claim` to
the issue thread. [Zulipbot](https://github.com/zulip/zulipbot) is a GitHub
workflow bot; it will assign you to the issue and label the issue as "in
progress". Some additional notes:

* You're encouraged to ask questions on how to best implement or debug your
  changes -- the Zulip maintainers are excited to answer questions to help
  you stay unblocked and working efficiently. You can ask questions on
  chat.zulip.org, or on the GitHub issue or pull request.
* We encourage early pull requests for work in progress. Prefix the title of
  work in progress pull requests with `[WIP]`, and remove the prefix when
  you think it might be mergeable and want it to be reviewed.
* After updating a PR, add a comment to the GitHub thread mentioning that it
  is ready for another review. GitHub only notifies maintainers of the
  changes when you post a comment, so if you don't, your PR will likely be
  neglected by accident!

### And beyond

A great place to look for a second issue is to look for issues with the same
`area:` label as the last issue you resolved. You'll be able to reuse the
work you did learning how that part of the codebase works. Also, the path to
becoming a core developer often involves taking ownership of one of these area
labels.

## What makes a great Zulip contributor?

Zulip runs a lot of [internship programs](#internship-programs), so we have
a lot of experience with new contributors. In our experience, these are the
best predictors of success:

* Posting good questions. This generally means explaining your current
  understanding, saying what you've done or tried so far, and including
  tracebacks or other error messages if appropriate.
* Learning and practicing
  [Git commit discipline](https://zulip.readthedocs.io/en/latest/contributing/version-control.html#commit-discipline).
* Submitting carefully tested code. This generally means checking your work
  through a combination of automated tests and manually clicking around the
  UI trying to find bugs in your work. See
  [things to look for](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#things-to-look-for)
  for additional ideas.
* Posting
  [screenshots or GIFs](https://zulip.readthedocs.io/en/latest/tutorials/screenshot-and-gif-software.html)
  for frontend changes.
* Being responsive to feedback on pull requests. This means incorporating or
  responding to all suggested changes, and leaving a note if you won't be
  able to address things within a few days.
* Being helpful and friendly on chat.zulip.org.

These are also the main criteria we use to select interns for all of our
internship programs.

## Reporting issues

If you find an easily reproducible bug and/or are experienced in reporting
bugs, feel free to just open an issue on the relevant project on GitHub.

If you have a feature request or are not yet sure what the underlying bug
is, the best place to post issues is
[#issues](https://chat.zulip.org/#narrow/stream/issues) (or
[#mobile](https://chat.zulip.org/#narrow/stream/mobile) or
[#electron](https://chat.zulip.org/#narrow/stream/electron)) on the
[Zulip community server](https://zulip.readthedocs.io/en/latest/contributing/chat-zulip-org.html).
This allows us to interactively figure out what is going on, let you know if
a similar issue has already been opened, and collect any other information
we need. Choose a 2-4 word topic that describes the issue, explain the issue
and how to reproduce it if known, your browser/OS if relevant, and a
[screenshot or screenGIF](https://zulip.readthedocs.io/en/latest/tutorials/screenshot-and-gif-software.html)
if appropriate.

**Reporting security issues**. Please do not report security issues
  publicly, including on public streams on chat.zulip.org. You can email
  zulip-security@googlegroups.com. We create a CVE for every security issue.

## User feedback

Nearly every feature we develop starts with a user request. If you are part
of a group that is either using or considering using Zulip, we would love to
hear about your experience with the product. If you're not sure what to
write, here are some questions we're always very curious to know the answer
to:

* Evaluation: What is the process by which your organization chose or will
  choose a group chat product?
* Pros and cons: What are the pros and cons of Zulip for your organization,
  and the pros and cons of other products you are evaluating?
* Features: What are the features that are most important for your
  organization? In the best case scenario, what would your chat solution do
  for you?
* Onboarding: If you remember it, what was your impression during your first
  few minutes of using Zulip? What did you notice, and how did you feel? Was
  there anything that stood out to you as confusing, or broken, or great?
* Organization: What does your organization do? How big is the organization?
  A link to your organization's website?

## Internship programs

Zulip runs internship programs with
[Outreachy](https://www.outreachy.org/),
[Google Summer of Code (GSoC)](https://developers.google.com/open-source/gsoc/)
[1], and the
[MIT Externship program](https://alum.mit.edu/students/NetworkwithAlumni/ExternshipProgram),
and has in the past taken summer interns from Harvard, MIT, and
Stanford.

While each third-party program has its own rules and requirements, the
Zulip community's approaches all of these programs with these ideas in
mind:
* We try to make the application process as valuable for the applicant as
  possible. Expect high quality code reviews, a supportive community, and
  publicly viewable patches you can link to from your resume, regardless of
  whether you are selected.
* To apply, you'll have to submit at least one pull request to a Zulip
  repository.  Most students accepted to one of our programs have
  several merged pull requests (including at least one larger PR) by
  the time of the application deadline.
* The main criteria we use is quality of your best contributions, and
  the bullets listed at
  [What makes a great Zulip contributor](#what-makes-a-great-zulip-contributor).
  Because we focus on evaluating your best work, it doesn't hurt your
  application to makes mistakes in your first few PRs as long as your
  work improves.

Zulip also participates in
[Google Code-In](https://developers.google.com/open-source/gci/). Our
selection criteria for Finalists and Grand Prize Winners is the same as our
selection criteria for interns above.

Most of our interns end up sticking around the project long-term, and many
quickly become core team members. We hope you apply!

### Google Summer of Code

GSoC is by far the largest of our internship programs (we had 14 GSoC
students in summer 2017).  While we don't control how many slots
Google allocates to Zulip, we hope to mentor a similar number of
students in 2018.

If you're reading this well before the application deadline and want
to make your application strong, we recommend getting involved in the
community and fixing issues in Zulip now. Having good contributions
and building a reputation for doing good work is best way to have a
strong application.  About half of Zulip's GSoC students for Summer
2017 had made significant contributions to the project by February
2017, and about half had not.  Our
[GSoC project ideas page][gsoc-guide] has lots more details on how
Zulip does GSoC, as well as project ideas (though the project idea
list is maintained only during the GSoC application period, so if
you're looking at some other time of year, the project list is likely
out-of-date).

We also have in some past years run a Zulip Summer of Code (ZSoC)
program for students who we didn't have enough slots to accept for
GSoC but were able to find funding for.  Student expectations are the
same as with GSoC, and it has no separate application process; your
GSoC application is your ZSoC application.  If we'd like to select you
for ZSoC, we'll contact you when the GSoC results are announced.

[gsoc-guide]: https://zulip.readthedocs.io/en/latest/overview/gsoc-ideas.html
[gsoc-faq]: https://developers.google.com/open-source/gsoc/faq

[1] Formally, [GSoC isn't an internship][gsoc-faq], but it is similar
enough that we're treating it as such for the purposes of this
documentation.

## Zulip Outreach

**Upvoting Zulip**. Upvotes and reviews make a big difference in the public
perception of projects like Zulip. We've collected a few sites below
where we know Zulip has been discussed. Doing everything in the following
list typically takes about 15 minutes.
* Star us on GitHub. There are four main repositories:
  [server/web](https://github.com/zulip/zulip),
  [mobile](https://github.com/zulip/zulip-mobile),
  [desktop](https://github.com/zulip/zulip-electron), and
  [Python API](https://github.com/zulip/python-zulip-api).
* [Follow us](https://twitter.com/zulip) on Twitter.

For both of the following, you'll need to make an account on the site if you
don't already have one.

* [Like Zulip](https://alternativeto.net/software/zulip-chat-server/) on
  AlternativeTo. We recommend upvoting a couple of other products you like
  as well, both to give back to their community, and since single-upvote
  accounts are generally given less weight. You can also
  [upvote Zulip](https://alternativeto.net/software/slack/) on their page
  for Slack.
* [Add Zulip to your stack](https://stackshare.io/zulip) on StackShare, star
  it, and upvote the reasons why people like Zulip that you find most
  compelling. Again, we recommend adding a few other products that you like
  as well.

We have a doc with more detailed instructions and a few other sites, if you
have been using Zulip for a while and want to contribute more.

**Blog posts**. Writing a blog post about your experiences with Zulip, or
about a technical aspect of Zulip can be a great way to spread the word
about Zulip.

We also occasionally [publish](http://blog.zulip.org/) longer form
articles related to Zulip. Our posts typically get tens of thousands
of views, and we always have good ideas for blog posts that we can
outline but don't have time to write. If you are an experienced writer
or copyeditor, send us a portfolio; we'd love to talk!
