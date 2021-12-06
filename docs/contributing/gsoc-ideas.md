# Google Summer of Code

## About us

[Zulip](https://zulip.com) is a powerful, open source team chat
application. Zulip has a web app, a cross-platform mobile app for iOS
and Android, a cross-platform desktop app, and over 100 native
integrations, all open source.

Zulip has gained a considerable amount of traction since it was
[released as open source software][oss-release] in late 2015, with
code contributions from [over 700 people](https://zulip.com/team)
from all around the world. Thousands of people use Zulip every single
day, and your work on Zulip will have impact on the daily experiences
of a large and rapidly growing number of people.

[oss-release]: https://blogs.dropbox.com/tech/2015/09/open-sourcing-zulip-a-dropbox-hack-week-project/

As an organization, we value high-quality, responsive mentorship and
making sure our product quality is extremely high -- you can expect to
experience disciplined code reviews by highly experienced
engineers. Since Zulip is a team chat product, your GSoC experience
with the Zulip project will be highly interactive.

As part of that commitment, Zulip has over 160,000 words of
[documentation for
developers](../index.html#welcome-to-the-zulip-documentation), much of
it designed to explain not just how Zulip works, but why Zulip works
the way that it does.

### Our history with Google Open Source Programs

Zulip has been a GSoC mentoring organization since 2016, and we aim
for 15-20 GSoC students each summer. We have some of the highest
standards of any GSoC organization; successful applications generally
have dozens of commits integrated into Zulip or other open source
projects by the time we review their application. See [our
contributing guide](../overview/contributing.md) for details on
getting involved with GSoC.

Zulip participated in GSoC 2016 and mentored three successful students
officially (plus 4 more who did their proposed projects unofficially).
We had 14 (+3) students in 2017, 10 (+3) students in 2018, 17 (+1) in
2019, and 18 in 2020. We've also mentored five Outreachy interns and
hundreds of Google Code-In participants (several of who are major
contributors to the project today).

While GSoC switched to a shorter coding period in 2021, we expect to
run a program that's very similar to past years in terms of how we
select and mentor students during the Spring (though with an
appropriately reduced expectation for students' time commitment during
the summer).

### Expectations for GSoC students

[Our guide for having a great summer with Zulip](../contributing/summer-with-zulip.md)
is focused on what one should know once doing a summer project with
Zulip. But it has a lot of useful advice on how we expect students to
interact, above and beyond what is discussed in Google's materials.

[What makes a great Zulip contributor](../overview/contributing.html#what-makes-a-great-zulip-contributor)
also has some helpful information on what we look for during the application
process.

We also recommend reviewing
[the official GSoC resources](https://developers.google.com/open-source/gsoc/resources/)
-- especially
[the student manual](https://developers.google.com/open-source/gsoc/resources/manual).

Finally, keep your eye on
[the GSoC timeline](https://developers.google.com/open-source/gsoc/timeline). The
student application deadline is April 13, 2021. However, as is
discussed in detail later in this document, we recommend against
working on a proposal until 2 weeks before the deadline.

## Getting started

We have an easy-to-set-up development environment, and a library of
tasks that are great for first-time contributors. Use
[our first-time Zulip developer guide](../overview/contributing.html#your-first-codebase-contribution)
to get your Zulip development environment set up and to find your first issue. If you have any
trouble, please speak up in
[#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) on
[the Zulip development community server](https://zulip.com/developer-community/)
(use your name as the topic).

## Application tips, and how to be a strong candidate

You'll be following [GSoC's application process
instructions](https://developers.google.com/open-source/gsoc/), and
making at least one successful pull request before the application
deadline, to help us assess you as a developer. Students who we accept
generally have five or more merged, or nearly merged, pull requests
(usually including at least a couple which are significant,
e.g. having 100+ lines of changes or show you have done significant
debugging).

Getting started earlier is better, so you have more time to learn,
make contributions, and make a good proposal.

Your application should include the following:

- Details on any experience you have related to the technologies used
  by Zulip, or related to our product approach.
- Links to materials which help us evaluate your level of experience and
  how you work, such as personal projects of yours, including any
  existing open source or open culture contributions you've made and
  any bug reports you've submitted to open source projects.
- Some notes on what you are hoping to get out of your project.
- A description of the project you'd like to do, and why you're
  excited about it.
- Some notes on why you're excited about working on Zulip.
- A link to your initial contribution(s).

We expect applicants to either have experience with the technologies
relevant to their project or have strong general programming
experience. We also expect applicants to be excited about learning
how to do disciplined, professional software engineering, where they
can demonstrate through reasoning and automated tests that their code
is correct.

While only one contribution is required to be considered for the
program, we find that the strongest applicants make multiple
contributions throughout the application process, including after the
application deadline.

We are more interested in candidates if we see them submitting good
contributions to Zulip projects, helping other applicants on [GitHub](https://github.com/zulip/zulip)
and on [chat.zulip.org](https://zulip.com/developer-community),
learning from our suggestions, [trying to solve their own obstacles and
then asking well-formed questions](https://www.mattringel.com/2013/09/30/you-must-try-and-then-you-must-ask/),
and developing and sharing project ideas and project proposals which
are plausible and useful.

## Questions are Important

A successful GSoC revolves around asking well-formed questions.
A well-formed question helps you learn, respects the person answering,
and reduces the time commitment and frustration level of everyone
involved. Asking the right question, to the right person, in the right
way, at the right time, is a skill which requires a lifetime of
fine-tuning, but Zulip makes this a little bit easier by providing a
general structure for asking questions in the Zulip community.

This structure saves time answering common questions while still
providing everyone the personal help they need, and maintains balance
between stream discussion and documentation. Becoming familiar and
comfortable with this rhythm will be helpful to you as you interact
with other developers on
[chat.zulip.org](https://zulip.com/developer-community). It is always
better (and Zulip’s strong preference) to ask questions and have
conversation through a public stream rather than a private message or
an email. This benefits you by giving you faster response times and
the benefit of many minds, as well as benefiting the community as
other contributors learn from reading the conversation.

- Stick to the [community norms](https://zulip.com/developer-community/).
- Read these three blog posts
  - [Try, Then Ask](https://www.mattringel.com/2013/09/30/you-must-try-and-then-you-must-ask/)
  - [We Aren’t Just Making Code, We’re Making History](https://www.harihareswara.net/sumana/2016/10/12/0)
  - [How to Ask Good Questions](https://jvns.ca/blog/good-questions/)
- Understand [what makes a great Zulip contributor](../overview/contributing.html#what-makes-a-great-zulip-contributor)

This is a typical question/response sequence:

1. You [try to solve your problem until you get stuck, including
   looking through our code and our documentation, then start
   formulating your request for
   help](https://www.mattringel.com/2013/09/30/you-must-try-and-then-you-must-ask/).
1. You ask your question.
1. Someone directs you to a document.
1. You go read the document to find the answer to your question.
1. You find you are confused about a new thing.
1. You ask another question.
1. Having demonstrated your the ability to read,
   think, and learn new things, someone will have a longer talk with
   you to answer your new, specific question.
1. You and the other person collaborate to improve the document you
   read in step 3. :-)

As a final note on asking for help, please make use of [Zulip's
Markdown](https://zulip.com/help/format-your-message-using-markdown)
when posting questions; code blocks are nicer for reading terminal
output than screenshots. And be sure to read the traceback before
posting it; often the error message explains the problem or hints that
you need more scrollback than just the last 20 lines.

## Mentors

Zulip has dozens of longtime contributors who sign up to mentoring
projects. We usually decide who will mentor which projects based in
part on who is a good fit for the needs of each student as well as
technical expertise as well as who has available time during the
summer. You can reach us via
[#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC) on [the Zulip
development community server](https://zulip.com/developer-community/),
(compose a new stream message with your name as the topic).

Zulip operates under group mentorship. That means you should generally
post in Zulip public streams, not send private messages, for
assistance. Our preferred approach is to just post in an appropriate
Zulip public stream .org and someone will help you. We list the Zulip
contributors who are experts for various projects by name below; they
will likely be able to provide you with the best feedback on your
proposal (feel free to @-mention them in your Zulip post). In
practice, this allows project leadership to be involved in mentoring
all students.

However, the first and most important thing to do for building a
strong application is to show your skills by contributing to a large
open source project like Zulip, to show that you can work effectively
in a large codebase (it doesn't matter what part of Zulip, and we're
happy to consider work in other open source projects). The quality of
your best work is more important to us than the quantity; so be sure
to test your work before submitting it for review and follow our
coding guidelines (and don't worry if you make mistakes in your first
few contributions! Everyone makes mistakes getting started. Just
make sure you don't make the same mistakes next time).

Once you have several PRs merged (or at least one significant PR
merged), you can start discussing with the Zulip development community
the project you'd like to do, and developing a specific project plan.
We recommend discussing what you're thinking in Zulip public streams,
so it's easy to get quick feedback from whoever is online.

## Project ideas

These are the seeds of ideas; you will need to do research on the
Zulip codebase, read issues on GitHub, and talk with developers to put
together a complete project proposal. It's also fine for you to come
up with your own project ideas. As you'll see below, you can put
together a great project around one of the
[area labels](https://github.com/zulip/zulip/labels) on GitHub; each
has a cluster of problems in one part of the Zulip project that we'd
love to improve.

We don't believe in labeling projects by difficulty (e.g. a project
that involves writing a lot of documentation will be hard for some
great programmers, and a UI design project might be hard for a great
backend programmer, while a great writer might have trouble doing
performance work). To help you find a great project, we list the
skills needed, and try to emphasize where strong skills with
particular tools are likely to be important for a given project.

For all of our projects, an important skill to develop is a good
command of Git; read [our Git guide](../git/overview.md) in full to
learn how to use it well. Of particular importance is mastering using
Git rebase so that you can construct commits that are clearly correct
and explain why they are correct. We highly recommend investing in
learning a [graphical Git client](../git/setup.md) and learning to
write good commit structures and messages; this is more important than
any other single skill for contributing to a large open source
project like Zulip.

We will never reject a strong student because their project idea was
not a top priority, whereas we often reject students proposing
projects important to the project where we haven't seen compelling
work from the student.

More important to us than specific deliverables in a project proposal
is a clear body of work to focus on; E.g. if we see a proposal with 8
Markdown processor issues, we'll interpret this as a student excited
to work on the Markdown processor for the summer, even if the specific
set of 8 issues may not be the right ones to invest in.

### Focus areas

For 2021, we are particularly interested in GSoC students who have
strong skills at visual design, HTML/CSS, mobile development,
performance optimization, or Electron. So if you're a student with
those skills and are looking for an organization to join, we'd love to
talk to you!

The Zulip project has a huge surface area, so even when we're focused
on something, a huge amount of essential work goes into other parts of
the project. Every area of Zulip could benefit from the work of a
student with strong programming skills; so don't feel discouraged if
the areas mentioned above are not your main strength.

As a data point, in Summer 2017, we had 4 students working on the
React Native mobile app (1 focused primarily on visual design), 1 on
the Electron desktop app, 2 on bots/integrations, 1 on web app visual
design, 2 on our development tooling and automated testing
infrastructure, and the remaining 4 on various other parts of the
backend and core web app.

### Full stack and web frontend focused projects

Code: [github.com/zulip/zulip -- Python, Django, JavaScript, and
CSS](https://github.com/zulip/zulip/).

- Zulip's [REST API documentation](https://zulip.com/api), which is an
  important resource for any organization integrating with Zulip.
  Zulip has a [nice framework](../documentation/api.md) for writing
  API documentation built by past GSoC students based on the OpenAPI
  standard with built-in automated tests of the data both the Python
  and curl examples. However, the documentation isn't yet what we're
  hoping for: there are a few dozen endpoints that are missing,
  several of which are quite important, the visual design isn't
  perfect (especially for e.g. `GET /events`), many template could be
  deleted with a bit of framework effort, etc. See the [API docs area
  label][api-docs-area] for many specific projects in the area. Our
  goal for the summer is for 1-2 students to resolve all open issues
  related to the REST API documentation.

[api-docs-area]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+documentation+%28api+and+integrations%29%22

- Finish important full-stack features for open source projects using
  Zulip, including [default stream
  groups](https://github.com/zulip/zulip/issues/13670), [Mute
  User](https://github.com/zulip/zulip/issues/168), and [public
  access](https://github.com/zulip/zulip/issues/13172). Expert: Tim
  Abbott. Many of these issues have open PRs with substantial work
  towards the goal, but each of them is likely to have dozens of
  adjacent or follow-up tasks.

- Fill in gaps, fix bugs, and improve the framework for Zulip's
  library of native integrations. We have about 100 integrations, but
  there are a handful of important integrations that are missing. The
  [the integrations label on
  GitHub](https://github.com/zulip/zulip/labels/area%3A%20integrations)
  lists some of the priorities here (many of which are great
  preparatory projects); once those are cleared, we'll likely have
  many more. **Skills required**: Strong Python experience, will to
  do careful manual testing of third-party products. Fluent English,
  usability sense and/or technical writing skills are all pluses.
  Expert: Eeshan Garg.

- Optimize performance and scalability, either for the web frontend or
  the server. Zulip is already one of the faster web apps out there,
  but there are a bunch of ideas for how to make it substantially
  faster. This is likely a particularly challenging project to do
  well, since there are a lot of subtle interactions to understand.
  **Skill recommended**: Strong debugging, communication, and code
  reading skills are most important here. JavaScript experience; some
  Python/Django experience, some skill with CSS, ideally experience
  using the Chrome Timeline profiling tools (but you can pick this up
  as you go) can be useful depending on what profiling shows. Our
  [backend scalability design doc](../subsystems/performance.md) and
  the [production issue label][prod-label] (where
  performance/scalability issues tend to be filed) may be helpful
  reading for the backend part of this. Expert: Steve Howell.

[prod-label]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+production%22

- Extract JavaScript logic modules from the Zulip web app that we'd
  like to be able to share with the Zulip web app. This work can have
  big benefits it terms of avoiding code duplication for complex
  logic. We have prototyped for a few modules by migrating them to
  `static/shared/`; this project will involve closely collaborating
  with the mobile team to prioritize the modules to migrate. **Skills
  recommended**: JavaScript experience, careful refactoring, API
  design, React.

  Experts: Greg Price, Steve Howell.

- Make Zulip integrations easier for nontechnical users to set up.
  This includes adding a backend permissions system for managing bot
  permissions (and implementing the enforcement logic), adding an
  OAuth system for presenting those controls to users, as well as
  making the /integrations page UI have buttons to create a bot,
  rather than sending users to the administration page. **Skills
  recommended**: Strong Python/Django; JavaScript, CSS, and design
  sense helpful. Understanding of implementing OAuth providers,
  e.g. having built a prototype with
  [the Django OAuth toolkit](https://django-oauth-toolkit.readthedocs.io/en/latest/)
  would be great to demonstrate as part of an application. The
  [Zulip integration writing guide](../documentation/integrations.md)
  and
  [integration documentation](https://zulip.com/integrations/)
  are useful materials for learning about how things currently work,
  and
  [the integrations label on GitHub](https://github.com/zulip/zulip/labels/area%3A%20integrations)
  has a bunch of good starter issues to demonstrate your skills if
  you're interested in this area. Expert: Eeshan Garg.

- Extend Zulip's meta-integration that converts the Slack incoming webhook
  API to post messages into Zulip. Zulip has several dozen native
  integrations (https://zulip.com/integrations/), but Slack has a
  ton more. We should build an interface to make all of Slack’s
  numerous third-party integrations work with Zulip as well, by
  basically building a Zulip incoming webhook interface that accepts
  the Slack API (if you just put in a Zulip server URL as your "Slack
  server"). **Skills required**: Strong Python experience; experience
  with the Slack API a plus. Work should include documenting the
  system and advertising it. Expert: Tim Abbott.

- Visual and user experience design work on the core Zulip web UI.
  We're particularly excited about students who are interested in
  making our CSS clean and readable as part of working on the UI.
  **Skills required**: Design, HTML and CSS skills; JavaScript and
  illustration experience are helpful. A great application would
  include PRs making small, clean improvements to the Zulip UI
  (whether logged-in or logged-out pages). Expert: Aman Agrawal.

- Build support for outgoing webhooks and slash commands into Zulip to
  improve its chat-ops capabilities. There's an existing
  [pull request](https://github.com/zulip/zulip/pull/1393) with a lot
  of work on the outgoing webhooks piece of this feature that would
  need to be cleaned up and finished, and then we need to build support for slash
  commands, some example integrations, and a full set of
  documentation and tests. Recommended reading includes Slack's
  documentation for these features, the Zulip message sending code
  path, and the linked pull request. **Skills required**: Strong
  Python/Django skills. Expert: Steve Howell.

- Build a system for managing Zulip bots entirely on the web.
  Right now, there's a somewhat cumbersome process where you download
  the API bindings, create a bot with an API key, put it in
  configuration files, etc. We'd like to move to a model where a bot
  could easily progress from being a quick prototype to being a third-party extension to
  being built into Zulip. And then for built-in bots, one should be able to click a few
  buttons of configuration on the web to set them up and include them in
  your organization. We've developed a number of example bots
  in the [`zulip_bots`](https://github.com/zulip/python-zulip-api/tree/main/zulip_bots)
  PyPI package.
  **Skills recommended**: Python and JavaScript/CSS, plus devops
  skills (Linux deployment, Docker, Puppet etc.) are all useful here.
  Experience writing tools using various popular APIs is helpful for
  being able to make good choices. Expert: Steve Howell.

- Improve the UI and visual design of the existing Zulip settings and
  administration pages while fixing bugs and adding new settings. The
  pages have improved a great deal during recent GSoCs, but because
  they have a ton of surface area, there's a lot to do. You can get a
  great sense of what needs to be done by playing with the
  settings/administration/streams overlays in a development
  environment. You can get experience working on the subsystem by
  working on some of [our open settings/admin
  issues](https://github.com/zulip/zulip/labels/area%3A%20admin).
  **Skills recommended**: JavaScript, HTML, CSS, and an eye for visual
  design. Expert: Shubham Dhama.

- Build out the administration pages for Zulip to add new permissions
  and other settings more features that will make Zulip better for
  larger organizations. We get constant requests for these kinds of
  features from Zulip users. The Zulip bug tracker has plentiful open
  issues( [settings
  (admin/org)](https://github.com/zulip/zulip/labels/area%3A%20settings%20%28admin%2Forg%29),
  [settings
  UI](https://github.com/zulip/zulip/labels/area%3A%20settings%20UI),
  [settings
  (user)](https://github.com/zulip/zulip/labels/area%3A%20settings%20%28user%29),
  [stream
  settings](https://github.com/zulip/zulip/labels/area%3A%20stream%20settings)
  ) in the space of improving the Zulip administrative UI. Many are
  little bite-size fixes in those pages, which are great for getting a
  feel for things, but a solid project here would be implementing 5-10
  of the major missing features as full-stack development projects.
  The first part of this project will be refactoring the admin UI
  interfaces to require writing less semi-duplicate code for each
  feature. **Skills recommended**: A good mix of Python/Django and
  HTML/CSS/JavaScript skill is ideal. The system for adding new
  features is [well documented](../tutorials/new-feature-tutorial.md).
  Expert: Shubham Dhama.

- Write cool new features for Zulip. Play around with the software,
  browse Zulip's issues for things that seem important, and suggest
  something you’d like to build! A great project can combine 3-5
  significant features. Experts: Depends on the features!

- Work on Zulip's development and testing infrastructure. Zulip is a
  project that takes great pride in building great tools for
  development, but there's always more to do to make the experience
  delightful. Significantly, a full 10% of Zulip's open issues are
  ideas for how to improve the project, and are
  [in](https://github.com/zulip/zulip/labels/area%3A%20tooling)
  [these](https://github.com/zulip/zulip/labels/area%3A%20testing-coverage)
  [four](https://github.com/zulip/zulip/labels/area%3A%20testing-infrastructure)
  [labels](https://github.com/zulip/zulip/labels/area%3A%20provision)
  for tooling improvements. A good place to start is
  [backend test coverage](https://github.com/zulip/zulip/issues/7089).

  This is a somewhat unusual project, in that it would likely consist
  of dozens of small improvements to the overall codebase, but this
  sort of work has a huge impact on the experience of other Zulip
  developers and thus the community as a whole (project leader Tim
  Abbott spends more time on the development experience than any other
  single area).

  A possible specific larger project in this space is working on
  adding [mypy](../testing/mypy.md) stubs
  for Django in mypy to make our type checking more powerful. Read
  [our mypy blog post](https://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/)
  for details on how mypy works and is integrated into Zulip. This
  specific project is ideal for a strong contributor interested in
  type systems.

  **Skills required**: Python, some DevOps, and a passion for checking
  your work carefully. A strong applicant for this will have
  completed several projects in these areas.

  Experts: Anders Kaseorg (provision, testing), Steve Howell (tooling, testing).

- Write more API client libraries in more languages, or improve the
  ones that already exist (in
  [python](https://github.com/zulip/python-zulip-api),
  [JavaScript](https://github.com/zulip/zulip-js),
  [PHP](https://packagist.org/packages/mrferos/zulip-php), and
  [Haskell](https://hackage.haskell.org/package/hzulip)). The
  JavaScript bindings are a particularly high priority, since they are
  a project that hasn't gotten a lot of attention since being adopted
  from its original author, and we'd like to convert them to
  Typescript. **Skills required**: Experience with the target
  language and API design. Expert: Depends on language.

- Develop [**@zulipbot**](https://github.com/zulip/zulipbot), the GitHub
  workflow bot for the Zulip organization and its repositories. By utilizing the
  [GitHub API](https://developer.github.com/v3/),
  [**@zulipbot**](https://github.com/zulipbot) improves the experience of Zulip
  contributors by managing the issues and pull requests in the Zulip repositories,
  such as assigning issues to contributors and appropriately labeling issues with
  their current status to help contributors gain a better understanding of which
  issues are being worked on. Since the project is in its early stages of
  development, there are a variety of possible tasks that can be done, including
  adding new features, writing unit tests and creating a testing framework, and
  writing documentation. **Skills required**: Node.js, ECMAScript 6, and API
  experience. Experts: Cynthia Lin, Joshua Pan.

### React Native mobile app

Code:
[React Native mobile app](https://github.com/zulip/zulip-mobile).
Experts: Greg Price, Chris Bobbe.

The highest priority for the Zulip project overall is improving the
Zulip React Native mobile app.

- Work on issues and polish for the app. You can see the open issues
  [here](https://github.com/zulip/zulip-mobile/issues). There are a
  few hundred open issues across the project, and likely many more
  problems that nobody has found yet; in the short term, it needs
  polish, bug finding/squashing, and debugging. So browse the open
  issues, play with the app, and get involved! Goals include parity
  with the web app (in terms of what you can do), parity with Slack (in
  terms of the visuals), world-class scrolling and narrowing
  performance, and a great codebase.

A good project proposal here will bundle together a few focus areas
that you want to make really great (e.g. the message composing,
editing, and reacting experience), that you can work on over the
summer. We'd love to have multiple students working on this area if
we have enough strong applicants.

**Skills required**: Strong programming experience, especially in
reading the documentation of unfamiliar projects and communicating
what you learned. JavaScript and React experience are great pluses,
as are iOS or Android development/design experience is useful as
well. You'll need to learn React Native as part of getting
involved. There's tons of good online tutorials, courses, etc.

### Electron desktop app

Code:
[Our cross-platform desktop app written in JavaScript on Electron](https://github.com/zulip/zulip-desktop).
Experts: Anders Kaseorg, Akash Nimare, Abhighyan Khaund.

- Contribute to our [Electron-based desktop client
  application](https://github.com/zulip/zulip-desktop). There's
  plenty of feature/UI work to do, but focus areas for us include
  things to (1) improve the release process for the app, using
  automated testing, TypeScript, etc. and (2) polish the UI. Browse
  the open issues and get involved!

**Skills required**: JavaScript experience, Electron experience. You
can learn electron as part of your application!

Good preparation for desktop app projects is to (1) try out the app
and see if you can find bugs or polish problems lacking open issues
and report them and (2) fix some polish issues in either the Electron
app or the Zulip web frontend (which is used by the electron app).

### Terminal app

Code: [Zulip Terminal](https://github.com/zulip/zulip-terminal)
Experts: Aman Agrawal, Neil Pilgrim.

- Work on Zulip Terminal, the official terminal client for Zulip.
  zulip-terminal is already a basic usable client, but it needs a lot
  of work to approach the web app's quality level. We would be happy
  to accept multiple strong students to work on this project. Our
  goal for this summer is to improve its quality enough that we can
  upgrade it from an alpha to an advertised feature. **Skills
  required**: Python 3 development skills, good communication and
  project management skills, good at reading code and testing.

### Archive tool

Code: [zulip-archive](https://github.com/zulip/zulip-archive)
Experts: Rein Zustand, Steve Howell

- Work on zulip-archive, which provides a Google-indexable read-only
  archive of Zulip conversations. The issue tracker for the project
  has a great set of introductory/small projects; the overall goal is
  to make the project super convenient to use for our OSS communities.
  **Skills useful**: Python 3, reading feedback from users, CSS,
  GitHub Actions.

## Circulating proposals (March to April)

If you're applying to GSoC, we'd like for you to publicly post a few
sections of your proposal -- the project summary, list of
deliverables, and timeline -- some place public on the Web, a week or
two before the application deadline. That way, the whole developer
community -- not just the mentors and administrators -- have a chance
to give you feedback and help you improve your proposal.

Where should you publish your draft? We prefer Dropbox Paper or Google
Docs, since those platforms allow people to look at the text without
having to log in or download a particular app, and you can update the
draft as you improve your idea. In either case, you should post the
draft for feedback in
[#GSoC](https://chat.zulip.org/#narrow/stream/14-GSoC).

Rough is fine! The ideal first draft to get feedback from the
community on should include primarily (1) links to your contributions
to Zulip (or other projects) and (2) a paragraph or two explaining
what you plan to work on. Your friends are likely better able to help
you improve the sections of your application explaining who you are,
and this helps the community focus feedback on the areas you can most
improve (e.g. either doing more contributions or adjusting the project
plan).

We hope to hear from you! And thanks for being interested in
Zulip. We're always happy to help volunteers get started contributing
to our open source project, whether or not they go through GSoC.
