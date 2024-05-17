# How to apply

This page should help you get started with applying for an outreach program
with Zulip.

We try to make the application process as valuable for the applicant as
possible. Expect high-quality code reviews, a supportive community, and
publicly viewable patches you can link to from your resume, regardless of
whether you are selected.

## Application criteria

We expect applicants to have experience with the technologies relevant
to their project, or else have strong general programming
experience. If you are just getting started learning how to program,
we recommend taking time to learn the basics (there are many great
online materials available for free!), and applying in the next
program cycle.

In addition to the requirements of the specific outreach program
you're applying to, successful applicants are expected to demonstrate
the following:

1. **Ability to contribute to a large codebase.** Accepted applicants
   generally have five or more merged (or nearly merged) pull
   requests, including at least a couple involving significant
   complexity. The quality of your best work is more important than
   the quantity, so be sure to [follow our coding
   guidelines](../contributing/code-style.md) and [self-review your
   work](../contributing/code-reviewing.md#reviewing-your-own-code)
   before submitting it for review.

2. **Clear communication.** Building open-source software is a collaborative
   venture, and effective communication is key to making it successful. Learn
   how to [ask great questions](../contributing/asking-great-questions.md), and
   explain your decisions clearly [in your commit
   messages](../contributing/commit-discipline.md#commit-messages) and [on your
   pull requests](../contributing/reviewable-prs.md).

3. **Improvement in response to feedback.** Don't worry if you make
   mistakes in your first few contributions! Everyone makes mistakes
   getting started — just make sure you learn from them!

We are especially excited about applicants who:

- Help out other applicants

- Try to solve their own obstacles, and then [ask well-formed
  questions](/contributing/asking-great-questions)

- Develop well thought out project proposals

Starting in 2022, being a student is not required in order to apply to
GSoC. We are happy to accept both student and non-student GSoC
participants.

## Getting started

If you are new to Zulip, our [contributor
guide](../contributing/contributing.md) is the place to start. It
offers a detailed walkthrough for submitting your first pull request,
with many pointers to additional documentation, and tips on how to get
help if you need it.

We recommend taking the following steps before diving into the issue tracker:

- Join the [Zulip development
  community](https://zulip.com/development-community/), and introduce yourself
  in the stream for the program you are participating in
  ([#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) or
  [#Outreachy](https://chat.zulip.org/#narrow/stream/391-Outreachy)). Before you
  jump in, be sure to review the [Zulip community
  norms](https://zulip.com/development-community/).

- Follow our instructions to [install the development
  environment](../development/overview.md), getting help in [#provision
  help](https://chat.zulip.org/#narrow/stream/21-provision-help) if needed.

- Familiarize yourself with [using the development
  environment](../development/using.md).

- Go through the [new application feature
  tutorial](../tutorials/new-feature-tutorial.md) to get familiar with how the
  Zulip codebase is organized, and how to find code in it.

As you are getting started on your first pull request:

- Read the [Zulip guide to Git](../git/overview.md). It's especially important
  to master using `git rebase`, so that you can restructure your commits. You can
  get help in [#git help](https://chat.zulip.org/#narrow/stream/44-git-help) if
  you get stuck.

- To make it easier to structure your PRs well, we recommend installing a
  [graphical Git client](../git/setup.md#get-a-graphical-client).

- Construct [coherent, mergeable
  commits](../contributing/commit-discipline.md), with clear
  commit messages that follow the [Zulip commit style
  guide](../contributing/commit-discipline.md). More broadly, clear
  communication on your pull request will make your work stand out.

- Carefully follow our [guide to reviewing your own
  code](../contributing/code-reviewing.md) before asking anyone else for a
  review. Catching mistakes yourself will help your PRs be merged faster, and
  folks will appreciate the quality and professionalism of your work.

Our documentation on [what makes a great Zulip
contributor](../contributing/contributing.md#what-makes-a-great-zulip-contributor)
offers some additional advice.

## Putting together your application

### What to include

In addition to following all the instructions for the program you are applying
to, your application should describe the following:

- Why you are applying:
  - Why you're excited about working on Zulip.
  - What you are hoping to get out of your participation in the program.
  - How you selected your project.
- Relevant experience:
  - Summary of your **prior experience with the technologies** used by Zulip.
  - Your **prior contributions to open-source projects** (including pull requests, bug
    reports, etc.), with links.
  - Any other **materials which will help us evaluate how you work**, such as
    links to personal or school projects, along with brief descriptions.
- Your **contributions to Zulip**, including pull requests, bug reports, and helping
  others in the development community (with links to all materials).
- A **project proposal** (see below).

**A note for Outreachy applicants**: It is not practical for us to individually
help you develop a specific timeline for your application. We expect you to
submit a project proposal as described below, and will help you manage the
timeline for your project if your application is selected.

### Project proposals

Your first priority during the contribution period should be figuring out how to
become an effective Zulip contributor. Start developing your project proposal
only once you have experience with iterating on your PRs to get them ready for
integration. That way, you'll have a much better idea of what you want to work
on and how much you can accomplish.

As [discussed in the guide to having an amazing experience during the
program](./experience.md#what-about-my-proposal):

> We have a fluid approach to planning, which means you are very unlikely to end
> up working on the exact set of issues described in your proposal. Your proposal
> is not a strict commitment (on either side).

Your proposal should demonstrate your thoughtfulness about what you want to work
on, and consideration of project complexity. We will evaluate it based on the
following criteria:

- Does it give us a good idea of what areas of Zulip you are most excited to
  work on?
- Does it demonstrate some familiarity with the Zulip codebase, and reflection
  on what makes for a coherent project that is well-aligned with your interests
  and skill set?
- Does it demonstrate your ability to put together a reasonable plan? Have you
  thought carefully about the scope of various pieces of your project and their
  dependencies? Are you taking into account the fact that there can be a lot of
  time in software development between having an initial prototype and merging
  the final, fully reviewed and tested, version of your code?
- Are you proposing a project that would make a significant positive impact on the
  areas you plan to focus on?

Regardless of which program you are applying to, you can use the [GSoC project
ideas list](./gsoc.md#project-ideas-by-area) as a source of inspiration for
putting together your proposal.

### Circulating your application for feedback

We highly recommend posting a rough draft of your application at least one week
before the deadline. That way, the whole development community has a chance to
give you feedback and help you improve your proposal.

- If you do not have a complete draft ready, at a minimum, we recommend posting
  your **project proposal**, along with **your contributions to Zulip** for
  context.

- Please post a link to your draft in the Zulip development community
  stream dedicated to your program (e.g.,
  [#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) or
  [#Outreachy](https://chat.zulip.org/#narrow/stream/391-Outreachy)). Use
  `Your name - project proposal` as the topic.

- We recommend linking to a draft in an app that works in the browser and allows
  commenting, such as Dropbox Paper or Google Docs.
