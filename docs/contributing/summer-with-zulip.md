# How to have an amazing summer with Zulip

The purpose of this doc is to provide advice to GSoC/ZSoC mentors and students
on how to make the summer as successful as possible. It's mandatory reading, in
addition to [Google's
materials](https://developers.google.com/open-source/gsoc/resources/manual).

- Don't focus too much on doing precisely what's in the project proposal or
  following precisely that schedule. The goals are for students to learn and to
  advance Zulip, not to do in July what we guessed would be the right plan in
  March with limited information.

  - We probably will want to create a Dropbox Paper document for each student to
    keep track of the current version of their project plan, but make sure to
    keep GitHub up to date with what issues you're working on.

  - Claim issues using zulipbot only when you actually start work on them. And
    if someone else fixes an issue you were planning to fix, don't worry about
    it! It's great for Zulip that the project was finished, and there's plenty
    of issues to work on :D. You can help review their work to build
    your expertise in the subsystem you're working on.

  - Look for, claim, and fix bugs to help keep Zulip polished. Bugs and polish
    are usually more important to users than new features.

  - Help test new features! It's fun, and one of the most valuable
    ways one can contribute to any software project is finding bugs in
    it before they reach a lot of users :).

  - Participate and be helpful in the community! Helping a new Zulip server
    administrator debug their installation problem or playing with the mobile
    app until you can get something to break are great ways to contribute.

- Mentors and students should stay in close contact, both with each other and
  the rest of the Zulip community. We recommend the following:

  - Daily checkins on #checkins on chat.zulip.org; ideally at some time of day
    you can both be online, but when not possible, async is better than nothing!

    - We prefer checkins in public streams, since it makes easier for
      other contributors to keep track of what everyone else is
      working on and share ideas (and helps organization leadership
      keep track of progress). Though, of course, feel free to have
      much more involved/detailed discussions privately as well.

    - If a mentor will be traveling or otherwise offline, mentors should make
      sure another mentor is paying attention in the meantime.

  - Video calls are great! Mentors should do 1-2 video calls with their students
    calls per week, depending on length, schedules, and what's happening.

  - Make sure to talk about not just the current project, but also meta-issues
    like your development process, where things are getting stuck, skills you
    need help learning, and time-saving tricks.

  - If you need feedback from the community / decisions made, ask in the
    appropriate public stream on [chat.zulip.org](http://chat.zulip.org). Often
    someone can provide important context that you need to succeed in your
    project.

  - Communicate clearly, especially in public places! You'll get much more
    useful feedback to a well-written Zulip message or GitHub issue comment than
    one that is unclear.

    - Be sure to mention any concerns you have with your own work!

    - Talk with your mentor about the status of your various projects and where
      they're stuck.

    - And when you update your PR having addressed a set of review feedback, be
      clear about which issues you've resolved (and how!) and
      especially any that you haven't yet (this helps code reviewers
      use their time well).

    - Post screenshots and/or brief videos of UI changes; a picture can be worth
      1000 words, especially for verifying whether a design change is
      working as intended.

    - Use #design and similar forums to get feedback on issues where we need
      community consensus on what something should look like or how it
      should work.

  - Bring up problems early, whether technical or otherwise. If you
    find you're stressed about something, mention it your mentor
    immediately, so they can help you solve the problem. If you're
    stressed about something involving your mentor, bring it up with
    an organization admin.

  - Join Zulip's GitHub teams that relate to your projects and/or interests, so
    that you see new issues and PRs coming in that are relevant to your work.
    You can browse the area teams here:
    https://github.com/orgs/zulip/teams (You need to be a member of
    the Zulip organization to see them; ask Tim for an invite if needed).

- Everyone's goal is to avoid students ending up blocked and feeling stuck.
  There are lots of things that students can do (and mentors can help them to)
  to avoid this:

  - Get really good at using `git rebase -i` to produce a really clean
    commit history that's fast to review. We occasionally do workshops
    on how to do relatively complex rebases.

  - Work on multiple parallelizable projects (or parts of projects) at a time.
    This can help avoid being stuck while waiting for something to be reviewed.

    - It can help to plan a bit in advance; if your next project requires some
      UX decisions to be made with the community, start the conversation a few
      days before you need an answer. Or do some preparatory refactoring that
      will make the feature easier to complete and can be merged without making
      all the decisions.

    - Think about how to test your changes.

  - Among your various projects, prioritize as follows:

    - (1) Fixing regressions you introduced with recently merged work (and other
      bugs you notice).

    - (2) Responding to code review feedback and fixing your in-flight branches
      over starting new work. Unmerged PRs develop painful merge conflicts
      pretty quickly, so you'll do much less total work per feature if you're
      responsive and try to make it easy for maintainers to merge your commits.

    - (3) Do any relevant follow-ups to larger projects you've completed, to
      make sure that you've left things better than how you found them.

    - (4) Starting on the next project.

  - Figure out a QA/testing process that works for you, and be sure to explain
    in your PRs how you've tested your changes. Most of the time, in a large
    open source project, is spent looking for and fixing regressions, and it
    saves everyone time when bugs can be fixed before the code is reviewed, or
    barring that, before it's merged.

  - Plan (and if when planning fails, rebase) your branches until they are easy
    to merge partially (i.e. merging just the first commit will not make Zulip
    worse or break the tests). Ideally, when reviewing a branch of yours, the
    maintainer should be able to merge the first few commits and leave comments
    on the rest. This is by far the most efficient way to do collaborative
    development, since one is constantly making progress, we keep branches
    small, and developers don't end up reviewing the easily merged parts of a PR
    repeatedly.

    - Look at Steve Howell's closed PRs to get a feel for how to do this well
      for even complex changes.

    - Or Eklavya Sharma's (from GSoC 2016) to see a fellow GSoC student doing
      this well. (`git log -p --author=Eklavya` is a fast way to skim).

  - Team up with other developers close to or in your time zone who are working
    on similar areas to trade timely initial code reviews. 75% of the feedback
    that the expert maintainers give is bugs/UI problems from clicking around,
    lack of tests, or code clarity issues that anyone else in the project should
    be able to point out. Doing this well can save a lot of round-trips.

- Help with code review! Reviewing others' changes is one of the best ways to
  learn to be a better developer, since you'll both see how others solve
  problems and also practice the art of catching bugs in unfamiliar code.

  - It's best to start with areas where you know the surrounding code
    and expertise, but don't be afraid to open up the code in your
    development environment and read it rather than trying to
    understand everything from the context GitHub will give you. Even
    Tim reads surrounding code much of the time when reviewing things,
    and so should you :).

  - It's OK to review something that's already been reviewed or just post a
    comment on one thing you noticed in a quick look!

  - Even posting a comment that you tried a PR and it worked in your development
    environment is valuable; you'll save the next reviewer a bit of time
    verifying that.

  - If you're confused by some code, usually that's because the code is
    confusing, not because you're not smart enough. So speak up when you notice
    this! Very frequently, this is a sign that we need to write more
    docs/comments or (better, if possible!) to make the code more
    self-explanatory.

- Plan your approach to larger projects. Usually, when tackling something big,
  there's a few phases you want to go through:

  - Studying the subsystem, reading its docs, etc., to get a feel for how things
    work. Often a good approach is to fix some small bugs in the area to warm
    your knowledge up.

  - Figure out how you'll test your work feature, both manually and via
    automated tests. For some projects, can save a lot of hours by doing a bit
    of pre-work on test infrastructure or `populate_db` initial data
    to make it easy for both you and code reviewers to get the state
    necessary to test a feature.

  - Make a plan for how to create a series of small (<100LOC) commits that are
    each safely mergable and move you towards your goal. Often this ends up
    happening through first doing a hacky attempt to hooking together the
    feature, with reading and print statements as part of the effort, to
    identify any refactoring needed or tests you want to write to help make sure
    your changes won't break anything important as you work. Work out a fast and
    consistent test procedure for how to make sure the feature is working as
    planned.

  - Do the prerequisite test/refactoring/etc. work, and get those changes
    merged.

  - Build a mergeable version of the feature on top of those refactorings.
    Whenever possible, find chunks of complexity that you can separate from the
    rest of the project.

- Spend time every week thinking about what could make contributing to Zulip
  easier for both yourself and the next generation of Zulip developers. And then
  make those ideas reality!

- Have fun! Spending your summer coding on open source is an amazing life
  opportunity, and we hope you'll have a blast. With some luck and hard work,
  your contributions to the open source world this summer will be something you
  can be proud of for the rest of your life.


## What makes a successful summer

Success for the student means a few things, in order of importance:

- Mastery of the skills needed to be a self-sufficient and effective open source
  developer. Ideally, by the end of the summer, most of the student's PRs should
  go through only a couple rounds of code review before being merged, both in
  Zulip and in any future open source projects they choose to join.
  Our most successful students end up as the maintainer for one or
  more areas within Zulip.

- The student has become a valued member of the Zulip community, and has made
  the Zulip community a better place through their efforts. Reviewing PRs,
  helping others debug, providing feedback, and finding bugs are all essential
  ways to contribute beyond the code in your own project.

- Zulip becoming significantly better in the areas the student focused on. The
  area should feel more polished, and have several new major features the
  student has implemented. That section of code should be more readable,
  better-tested, and have clearer documentation.


## Extra notes for mentors

- You're personally accountable for your student having a successful summer. If
  you get swamped and find you don't have enough time, tell the org admins so
  that we can make sure someone is covering for you. Yes, it sucks when you
  can't do what you signed up for, but even worse is to not tell anyone and thus
  prevent the project from finding a replacement.

- Mentors are expected to provide on the mentors stream a **brief report
  weekly** on (1) how your students' projects are going, (2) what (if anything)
  you're worried about, and (3) what new things you'd like to try this week to
  help your student. A great time to do this is after a weekly scheduled call
  with your student, while your recollection of the state is fresh.

- Timely feedback is more important than complete feedback, so get a fast
  feedback cadence going with your student. It's amazing how useful just 5
  minutes of feedback can be. Pay attention to the relative timezones; if you
  plan it, you can get several round trips in per day even with big timezone
  differences like USA + India.

-  What exactly you focus on in your mentorship will vary from week to week and
   depend somewhat on what the student needs. It might be any combination of
   these things:

  - Helping the student plan, chunk, and prioritize their work.

  - Manually testing UI changes and helping find bugs.

  - Doing code review of your student's work

  - Providing early feedback on visual and technical design questions.

  - Helping the student figure out how to test their changes.

  - Helping the student break their PRs into reviewing chunks.

  - Making sure busy maintainers like Tim Abbott provide any necessary feedback
    so that the student's project doesn't get stuck.

  - Helping with the technical design of projects and making sure they're aware
    of useful and relevant reference materials.

  - Pair programming with the student to help make sure you share useful tricks.

  - Emotional support when things feel like they aren't going well.
