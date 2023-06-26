# How to have an amazing experience

If you are joining Zulip as part of an outreach program (e.g.
[GSoC](https://summerofcode.withgoogle.com/) or
[Outreachy](https://www.outreachy.org/)), welcome! Please make sure you read
this page carefully early on, and we encourage you to come back to it over the
course of the program.

## Your goals

Your experience as a Zulip outreach program participant is your
responsibility, and we strongly encourage you take full ownership. The
more care, attention, and energy you put in, the more you'll be able
to get out of the program. We're here to support you, but the journey
is yours to make!

The following are the main goals we'll be guiding you towards, as they are
shared by the great majority of program participants, and are aligned with the
objectives for our umbrella programs. If you have additional goals in mind for
your experience, please let your mentor and the community know, so that we can
help you along.

- You should gain mastery of the skills needed to be a self-sufficient and
  effective open-source developer. By the end of the program, all but the most
  complex PRs should ideally go through only a couple of rounds of code review
  before being merged. Our most successful contributors gain the expertise to
  become a maintainer for one or more areas within Zulip.

- You should become a valued member of the Zulip community, who works to make it
  better for all involved. Reviewing PRs, helping others debug, providing
  feedback, and finding bugs are wonderful ways to contribute beyond the code in
  your own project.

- You should feel proud of the significant positive impact you've made on the
  areas you focused on. Your areas should be more polished, and have several
  new major features that you have implemented. The sections of code you worked
  on should be more readable, better-tested, and have clearer documentation.

Don't forget to have fun! Spending a few months coding on open source is an
amazing opportunity, and we hope you'll have a blast. Your acceptance to the
program means that we we are confident that if you put in the effort, your
contributions to the open source world will be something you can be proud of for
the rest of your life.

## You and your mentor

Zulip operates under a **group mentorship** model. Every participant in a Zulip
mentorship program will:

- Have an assigned mentor, who will be their go-to for personal questions and
  concerns, and a consistent point of contact throughout the program.

- Receive lots of feedback and mentorship from others in the Zulip development
  community, in code reviews on pull requests, and by posting
  [questions](../contributing/asking-great-questions.md) and ideas in public
  streams.

Mentors and contributors should stay in close contact. We recommend setting up a
weekly check-in call to make sure you stay on track and have a regular
opportunity to ask your mentor questions and get their feedback. Talk with your
mentor about the status of your projects, and get their advice on how to make
progress if some project feels stuck.

Bring up problems early, whether technical or otherwise. If you're stressed
about something, mention it your mentor immediately, so they can help you solve
the problem. If you're stressed about something involving your mentor, bring it
up with an organization admin.

## Communication and check-ins

Communicating proactively with your mentor, your peers, and the rest of the
Zulip community is vital to having a successful mentorship program with Zulip.
It's how we can help you make sure you're working on a great set of impactful
issues, and not getting stuck or taking an approach that won't work out.

A key communication tool we use is posting regular public check-ins, which are
a required part of the program. We recommend reading your peers' check-ins
to get a feel for what they are working on and share ideas!

### Getting feedback and advice

We strongly encourage all Zulip contributors to post their questions and ideas
in public streams in the [Zulip development
community](https://zulip.com/development-community/). When you post in a public
stream, you give everyone the opportunity to help you out, and to learn from
reading the discussion.

Examples of topics you might ask about include:

- Making a technical decision while solving the issue.

- Making a product decision, e.g., if the issue description does not address some
  details, or you've identified a problem with the plan proposed in the issue.

- Making a design decision, e.g., if you have a couple of different ideas and
  aren't sure what looks best.

See our guide to [asking great
questions](../contributing/asking-great-questions.md) for detailed advice on how
to ask your questions effectively.

### How to post your check-ins

A check-in is a regular update that you post in the Zulip development community.
You can find many examples in the
[#checkins](https://chat.zulip.org/#narrow/stream/65-checkins) and
[#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) streams.

- **Frequency**: _Regular check-ins are a required for all program
  participants._ If you are working 20+ hours per week, post a check-in at least
  twice a week, e.g., Tuesday and Friday. If you are working less than 20 hours
  per week, post a check-in at least once a week.

- **Where to post**: Unless your mentor or program administrator requests
  otherwise, post your check-ins in the stream for your program
  (e.g., [#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) or
  [#Outreachy](https://chat.zulip.org/#narrow/stream/391-Outreachy)), using your
  name as the topic.

- **What to include** in each check-in:

  - The **status** of each ongoing project, e.g., in progress, awaiting feedback,
    addressing review feedback, stuck on something, blocked on other work, etc.
    To make your update easy to read, include brief descriptions of what you're
    working on, not just issue/PR numbers.

  - For projects where you are waiting on feedback, what **type of feedback** is
    needed (e.g. product review, next round of code review after initial
    feedback has been addressed, answer to some question, etc.). Use [silent
    mentions](https://zulip.com/help/mention-a-user-or-group#silently-mention-a-user)
    to indicate whose feedback is required, if you think you know who it should
    be.

  - Any questions or problems you **feel stuck** on. If there's an ongoing thread
    elsewhere, please link to it. Please post each question/problem in a
    separate message to make it convenient to quote-and-reply to address it.
    Note that discussions about your work will happen in all the usual places
    (#**frontend**, #**backend**, #**design**, etc.), and those are the
    streams where you should be _starting_ conversations. Your check-ins are a
    place to point out where you're feeling stuck, e.g., there was some
    discussion in a stream or on GitHub, but it seems to have petered out
    without getting to a decision, and you aren't sure what to do.

  - What you've been **actively working** on since your last check-in.

  - What you **intend to focus** on until your next check-in. Indicate if you are
    unsure and would appreciate some suggestions or feedback on your plan.

## Peer reviews

Reviewing others' changes is one of the best ways to learn to be a better
developer, since you'll both see how others solve problems and also practice the
art of catching bugs in unfamiliar code. As discussed in the [code review
guide](../contributing/code-reviewing.md):

> Doing code reviews is a valuable contribution to the Zulip project. It’s also
> an important skill to develop for participating in open-source projects and
> working in the industry in general... Anyone can do a code review – you don’t
> have to have a ton of experience.

For programs with multiple participants, we will set up a **code review buddies**
system at the start of the program:

1. Everyone will be assigned to a group of 2-3 people who will be your buddies
   for first-round code reviews. (In some cases, your buddy will be your
   mentor.)

2. Start by [self-reviewing your own code](../contributing/code-reviewing.md).

3. When ready, request a review from your code review buddies. Use [GitHub's
   review request
   feature](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/requesting-a-pull-request-review)
   to send your request. This makes the PR's status clear to project maintainers.
   You may also want to send a quick direct message to let your buddies know
   their attention is needed.

4. Please respond to code review requests promptly (within one workday), and
   follow the guidelines [in the code review
   guide](../contributing/code-reviewing.md).

Your initial reply does not have to be a full review. If you’re pressed for
time, start by quickly sharing your initial thoughts or feedback on the general
direction, and let the PR author know when you expect to provide a more detailed
review.

Make sure the GitHub comments on the PR are always clear on the status -- e.g.
buddy code review has been requested, feedback is being discussed, code buddy
has approved the PR, etc. This will help project maintainers know when it's time
to move on to the next step of the review process.

## How do I figure out what to work on?

Our goal is for contributors to improve their skills while making meaningful
contributions to Zulip. We like to be flexible, which means that you are
unlikely to work precisely on the issues described in your proposal, and that's
OK!

In practice, this means that over the course of the program, you will:

- Get frequent guidance regarding what to work on next by posting your ideas and
  questions about what to tackle next in your
  [check-ins](#how-to-post-your-check-ins).

- Like other Zulip contributors, [claim
  issues](../contributing/contributing.md#claiming-an-issue) only when you
  actually start work on them.

If someone else fixes an issue you were planning to fix, don't worry about it!
Consider [reviewing their work](../contributing/code-reviewing.md) to build your
expertise in the subsystem you're working on.

### Prioritization

Always keep the following order of priorities in mind:

1. Your top priorities should be **fixing any regressions you introduced** with
   recently merged work, and **fixing any important bugs or regressions** that
   you pick up or are assigned.

2. **Review others' pull requests** promptly. As you'll experience yourself, getting quick
   feedback on your PR helps immensely. As such, if you are asked to review a
   PR, aim to provide an initial reply within one workday.

3. If any of your PRs are actively undergoing review or are marked as
   "integration review" ready, be sure to **rebase** them whenever merge
   conflicts arise.

4. Next, prioritize **responding to code review feedback** over starting new
   work. This helps you and your reviewers maintain context, which makes it
   easier to make progress towards getting your work integrated.

5. Do any relevant **follow-ups to larger projects** you've completed, to make sure
   that you've left things better than how you found them.

6. Finally, if all of the above are in good shape, **find a new issue** to pick up!

### What about my proposal?

We have a fluid approach to planning, which means you are very unlikely to end
up working on the exact set of issues described in your proposal. Your proposal
is not a strict commitment (on either side).

In terms of managing your work:

- Regardless of whether an issue was mentioned in your proposal, make
  sure you bring it up in your check-ins when you plan to start
  working on something. Project priorities shift over time, and we
  may have suggestions for higher-priority work in your area of
  interest, or issues that will serve as good preparation for other
  work you are excited about. It's also possible that a project idea
  is not ready to be worked on, or needs to be sequenced after other projects.

- When asking for recommendations for what to work on next, it's helpful to
  include a reminder of what areas you're most excited about, especially early
  on in the program when we're still getting to know you. Do not expect program
  administrators to remember what issues were listed in your proposal.

While some program participants stick closely to the spirit of their proposal,
others find new areas they are excited about in the course of their work. You
can be highly successful in the program either way!

### Tips for finding issues to pick up

- Look for, claim, and fix bugs to help keep Zulip polished. Bugs and polish
  make a huge difference to our users' experience. If you can fix a
  [high-priority
  bug](https://github.com/zulip/zulip/issues?page=2&q=is%3Aopen+is%3Aissue+label%3Abug+label%3A%22priority%3A+high%22)
  in an area you've been working on, it is likely to have more impact than any
  new feature you might build.

- If you're working on something other than the Zulip server / web app codebase,
  follow your project on GitHub to keep track of what's happening.

- The Zulip server / web app project is too active to follow, so instead we
  recommend joining [Zulip's GitHub teams](https://github.com/orgs/zulip/teams)
  that relate to your projects and/or interests. When an area label is added to
  an issue or PR, [Zulipbot](https://github.com/zulip/zulipbot) automatically
  mentions the relevant teams for that area, subscribing all team members to the
  issue or PR thread.

### Staying productive

Here are some tips for making sure you can always be productive, even when
waiting for a question to be answered or for the next round of feedback on a PR:

- You should be working on multiple issues (or parallelizable parts of a large
  issue) at a time. That way, if you find yourself blocked on one project, you
  can always push on a different one in the meantime.

- It can help to plan a bit in advance by thinking about the issue you intend to
  pick up next. Are there decisions that will require input from others? Try to
  start the conversation a few days before you need an answer.

- If you are waiting for some decision to be finalized, consider doing
  preparatory refactoring that will make the feature easier to complete and can
  already be merged.

## How else can I contribute?

- Participate and be helpful in the community! Helping a new contributor get
  started or answering a user's question are great ways to contribute.

- Test and give feedback on new features that are deployed in the development
  community! It's fun, and it helps us find bugs before they reach our users.

- As you are doing your work, keep thinking about what could make contributing to Zulip
  easier for both yourself and the next generation of Zulip contributors. And then
  make those ideas reality!

## Timeline extensions for GSoC

Starting in 2022, it became possible to extend the timeline of a GSoC project.
This can be a great idea if you don't have a lot of time to dedicate each week,
or have an interruption during the program (e.g., getting sick, travel, family
obligations, etc.).

We're generally very flexible, so if extending your project dates would make it
less stressful to put in the required hours, please discuss this with your
mentor and Zulip's GSoC administrator. Please start this conversation
proactively as soon as you realize that you might need an extension, as this
will give us confidence that you'll be able to manage your time effectively to
successfully complete the program.

It is possible to have the midterm evaluation happen more than half-way through
the project timeline. If the balance of hours you plan to spend on GSoC is
significantly weighted towards the latter half of your GSoC contribution period,
please contact Zulip's program administrator to discuss pushing out the midterm
evaluation.
