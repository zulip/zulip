# GSoC project ideas

This page describes ideas you can use as a starting point for your project
proposal. If you have not done so yet, you should **start by reading our [guide on
how to apply](./apply.md)** to a Zulip outreach program. As noted in the guide:

> Your first priority during the contribution period should be figuring out how
> to become an effective Zulip contributor. Start developing your project proposal
> only once you have experience with iterating on your PRs to get them ready for
> integration. That way, you'll have a much better idea of what you want to work
> on and how much you can accomplish.

## Project size

We have designed all our projects to have incremental milestones that can be
completed throughout the program. Consequently, Zulip projects described below
are generally compatible with both large-sized (350 hours) and medium-sized (175
hours) projects. Of course, the amount of progress you will be expected to make
depends on whether you are doing a 175-hour or 350-hour project. Because it
takes significant time investment to learn how to contribute complex features to
Zulip's codebase, we are not planning to offer small-size projects.

Contributors who master the art of consistently packaging their work
into correct, [reviewable pull
requests](../contributing/reviewable-prs.md) are able to make major
improvements to the Zulip app. If you pay attention to the contributor
guidelines, carefully review your own work before asking anyone else
for review, take the time to clearly communicate your changes, and
apply the feedback you receive to your next contribution, you'll be
amazed at what you can accomplish.

## Focus areas

For 2025, we are particularly interested in GSoC contributors who have
strong skills at full-stack feature development, Typescript, visual design,
HTML/CSS, Flutter, or performance optimization. So if you're an applicant with
those skills and are looking for an organization to join, we'd love to
talk to you!

The Zulip project has a huge surface area, so even when we're focused
on something, a large amount of essential work goes into other parts of
the project. Every area of Zulip could benefit from the work of a
contributor with strong programming skills, so don't feel discouraged if
the areas mentioned above are not your main strength.

## Project ideas by area

This section contains the seeds of project ideas; you will need to do research
on the Zulip codebase, read issues on GitHub, read documentation, and talk with
developers to put together a complete project proposal. It's also fine to come
up with your own project ideas. As you'll see below, you can put together a
great project around one of the [area
labels](https://github.com/zulip/zulip/labels) on GitHub; each has a cluster of
problems in one part of the Zulip project that we'd love to improve.

### Full stack and web frontend focused projects

Code: [github.com/zulip/zulip](https://github.com/zulip/zulip/) -- Python,
Django, TypeScript/JavaScript, and CSS.

- **Cluster of priority features**. Implement a cluster of new full
  stack features for Zulip. The [high priority
  label](https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22priority%3A+high%22)
  documents hundreds of issues that we've identified as important to
  the project. A great project can be 3-5 significant features around
  a theme (often, but not necessarily, an [area
  label](https://github.com/zulip/zulip/labels)); the goal will be to
  implement and get fully merged a cluster of features with a
  meaningful impact on the project. Zulip has a lot of half-finished
  PRs, so some features might be completed by reading, understanding,
  rebasing, and reviving an existing pull request. 175 or 350
  hours; difficulty will vary. **Skills required**: Depends on the
  features; Tim Abbott will help you select an appropriate cluster
  once we've gotten to know you and your strengths through your getting
  involved in the project.

  Experts: Tim Abbott and various others depending on project area

- **Complete some unfinished projects**. This is a variant of the
  previous project idea category, but focused on projects with
  significant existing work to start from and polish, rather than
  projects that have not been seriously attempted previously.

  We maintain a [completion candidate label][completion-candidate]
  for pull requests where a previous contributor
  (sometimes via GSoC!) did significant work towards something
  valuable, and there's significant feedback from maintainers, but the
  project was never finished, and requires significant further effort
  from a new contributor in order to progress. One of our
  goals for this summer's GSoC is to complete many of these
  issues. Start by picking something that's interesting to you, and
  you feel you have the skills required to complete. Read the code and
  the feedback, and then create your own PR for the issue. See the [guide on
  continuing unfinished work][continuing-work] for details.
  175 or 350 hours; difficulty will vary.
  **Skills required**: Varies with project; a common skill will be
  good reading comprehension and organization/communication skills, to
  walk maintainers through how you resolved problems, addressed any
  pending feedback on the previous PR, and your understanding of the
  outstanding questions for a given project. Taking the time to get
  really good at resolving merge conflicts is likely to be valuable
  here as well.

  Experts: Tim Abbott and various others depending on project area

[completion-candidate]: https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22completion+candidate%22
[continuing-work]: ../contributing/continuing-unfinished-work.md

- Migrate Zulip's **[direct message recipient data
  structures](https://github.com/zulip/zulip/issues/25713)** to a new
  model that enables personal settings associated with a direct
  message conversation, and add several settings (see the linked
  issues) enabled by that infrastructure work. 175 or 350
  hours; fairly difficult. **Skills required**:
  This project will be deep Python 3/PostgreSQL work. Concretely,
  challenging parts of this project include thinking about races and
  database transactions, writing database migrations intended to be
  run live at scale, complex internal refactors, and carefully
  verifying the indexes used by migrated database queries.

  Experts: Tim Abbott, Mateusz Mandera, Prakhar Pratyush

- **Implement [channel
  groups](https://github.com/zulip/zulip/issues/31972)** that simplify
  administration of collections of related channels in
  Zulip. Contributors interested in working on this should start with
  studying Zulip's existing channel and group-based permissions
  system, both UX and implementation, and doing some starter issues in
  the settings area. 175 or 350 hours; medium difficulty.
  **Skills required**: Ability to read and
  understand a lot of code, as well web frontend work in
  TypeScript/HTML/CSS, with a bit of Python server programming. We'll
  be particularly interested in the ability to explain and reason
  about complex logic and follow the existing UI patterns for group
  settings and channel settings.

  Experts: Sahil Batra, Shubham Padia

- Add the core infrastructure for **topic-based permissions and settings**
  like [pinned topics](https://github.com/zulip/zulip/issues/19483)
  and [read-only topics](https://github.com/zulip/zulip/issues/26944),
  and then build some of those settings. This project will be a
  mixture of Python 3/PostgreSQL work, including thinking about
  database transactions and races, writing database migrations
  intended to be run live at scale, and complex logic to handle moving
  messages correctly in the context of these settings, including
  significant changes to the Zulip API and API documentation.
  175 or 350 hours; fairly difficult.
  **Skills required**: A high level of fluency with writing readable
  Python 3 and thinking about corner cases.

  Experts: Tim Abbott, Prakhar Pratyush

- Zulip's [**REST API documentation**](https://zulip.com/api/), which is an
  important resource for any organization integrating with Zulip, as
  well as the developers of our API clients. Zulip has a [nice
  framework](../documentation/api.md) for writing API documentation
  built by past GSoC students based on the OpenAPI standard with
  built-in automated tests of the data both the Python and curl
  examples. However, the documentation isn't yet what we're hoping
  for: there are a few dozen endpoints that are missing, several of
  which are quite important, the visual design isn't perfect
  (especially for, e.g., `GET /events`), many templates could be deleted
  with a bit of framework effort, etc. See the [API docs area
  label][api-docs-area] for some specific projects in the area; and
  `git grep pending_endpoints` to find the list of endpoints that need
  documentation and their priorities. Our goal for the summer is for
  1-2 students to resolve all open issues related to the REST API
  documentation. 175 or 350 hours; difficulty easy or medium. **Skills
  required**: Python programming. Expertise with reading documentation
  and English writing are valuable, and product thinking about the
  experience of using third-party APIs is very helpful.

  Expert: Lauryn Menard

[api-docs-area]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+documentation+%28api+and+integrations%29%22

- **Improve the UI and visual design** of the Zulip web app. We are working on a
  major redesign for the core surfaces of the Zulip web app -- see the [redesign
  label][redesign-label] for specced out work, with more to come. We're
  particularly excited about students who are interested in making our CSS clean
  and readable as part of working on the UI. 175 or 350 hours; medium to
  difficult. **Skills required**: Design, HTML and CSS skills; most important is
  the ability to carefully verify that one's changes are correct and will not
  break other parts of the app; design changes are very rewarding since they are
  highly user-facing, but that also means there is a higher bar for correctness
  and reviewability for one's work. A great application would include PRs making
  small, clean improvements to the Zulip UI (whether logged-in or logged-out
  pages).

  Experts: Aman Agrawal, Karl Stolley, Alya Abbott

[redesign-label]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3Aredesign

- **Improve type safety of node tests**. Rework Zulip's [automated
  node tests](../testing/testing-with-node.md) to use objects that
  consistently have the correct type. Currently, many tests use fake
  message, user, or channel objects with only a handful of fields
  relevant to the test. We've been working towards
  `web/tests/lib/example_*`. A good starter project would be to try to
  convert a small test module that currently does not use the
  `make_user` type functions to do so. The [main TypeScript migration
  thread](https://chat.zulip.org/#narrow/channel/6-frontend/topic/typescript.20migration/with/2085240)
  is useful background reading, and
  [#frontend](https://chat.zulip.org/#narrow/channel/6-frontend)
  channel is a good place to start new topics while working on this
  project. 175 or 350 hours; medium difficulty. **Skills required**:
  TypeScript fluency, and the discipline
  to write easily reviewed pull requests that often will include a
  series of changes to clean up an individual test while you're
  working on it.

  Experts: Afeefuddin, Lalit

- **Replace hundreds of `dict[str, Any]` types with modern
  dataclasses**. While functionally efficient, `dataclasses` are more
  readable, safe against typos, and have nice support for optimizing
  them further using `__slots__`. A lot of Zulip server code was
  written before dataclasses existed, and while a lot has been
  converted naturally as part of other projects, we'd like to make a
  focused push to replace the remaining ones. This project will
  involve making dozens of small commits and PRs, each a clean
  refactor converting a single type. Use [this
  conversation](https://chat.zulip.org/#narrow/channel/3-backend/topic/migrating.20to.20dataclasses/near/2085283)
  for discussion and coordination. **Skills required**. Solid
  understanding of statically typed Python, and the discipline to
  learn to write refactoring commits that are easy to integrate,
  following our standard guidelines, because they convincingly don't
  change any product behavior while improving type-safety.

  Experts: Tim Abbott, Anders Kaseorg

- **Optimize performance and scalability**, either for the web
  frontend or the server. Zulip is already one of the faster web apps
  out there, but we have a number of ideas for how to make it
  substantially faster yet. This is likely a particularly challenging
  project to do well, since there are a lot of subtle interactions to
  understand. 175 or 350 hours; difficult. **Skill recommended**:
  Strong debugging, communication, and code reading skills are most
  important here. JavaScript experience; some Python/Django
  experience, some skill with CSS, ideally experience using the Chrome
  Performance profiling tools (but you can pick this up as you go) can
  be useful depending on what profiling shows. Our [backend
  scalability design doc](../subsystems/performance.md) and the
  [performance label][perf-label] may be helpful reading for the
  backend part of this.

  Experts: Tim Abbott

[perf-label]: https://github.com/zulip/zulip/labels/area%3A%20performance

- Fill in gaps, fix bugs, and improve the framework for Zulip's **library of
  native integrations**. We have about 120 native integrations, but there are a
  number of others we would like to add. Also, several extensions to the
  framework that would dramatically improve the user experience of using
  integrations, e.g., being able to do callbacks to third-party services
  like Stripe to display more user-friendly notifications. The [the integrations
  label on GitHub](https://github.com/zulip/zulip/labels/area%3A%20integrations)
  lists some of the priorities here (many of which are great preparatory
  projects). 175 or 350 hours; medium difficulty with various possible difficult
  extensions. **Skills required**: Strong Python experience, will to install and
  do careful manual testing of third-party products. Fluent English, usability
  sense and/or technical writing skills are all pluses.

  Experts: Niloth, Lauryn Menard

- **Make Zulip integrations easier for nontechnical users to set up**.
  This includes adding a backend permissions system for managing bot
  permissions (and implementing the enforcement logic), adding an
  OAuth system for presenting those controls to users, as well as
  making the `/integrations` page UI have buttons to create a bot,
  rather than sending users to the administration page. 175 or 350
  hours; easy to difficult depending on scope. **Skills recommended**:
  Strong Python/Django; JavaScript, CSS, and design sense
  helpful. Understanding of implementing OAuth providers, e.g., having
  built a prototype with [the Django OAuth
  toolkit](https://django-oauth-toolkit.readthedocs.io/en/latest/)
  would be great to demonstrate as part of an application. The [Zulip
  integration writing guide](../documentation/integrations.md) and
  [integration documentation](https://zulip.com/integrations/) are
  useful materials for learning about how things currently work, and
  [the integrations label on
  GitHub](https://github.com/zulip/zulip/labels/area%3A%20integrations)
  has a bunch of good starter issues to demonstrate your skills if
  you're interested in this area.

  Experts: Niloth, Lauryn Menard

  [all-settings-issues]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+settings+%28admin%2Forg%29%22%2C%22area%3A+settings+%28user%29%22%2C%22area%3A+stream+settings%22%2C%22area%3A+settings+UI%22

- Work on Zulip's **development and testing infrastructure**. Zulip is a
  project that takes great pride in building great tools for
  development, but there's always more to do to make the experience
  delightful. Significantly, about 10% of Zulip's open issues are
  ideas for how to improve the project's contributor experience, and
  are [in](https://github.com/zulip/zulip/labels/area%3A%20tooling)
  [these](https://github.com/zulip/zulip/labels/area%3A%20testing-coverage)
  [four](https://github.com/zulip/zulip/labels/area%3A%20testing-infrastructure)
  [labels](https://github.com/zulip/zulip/labels/area%3A%20provision)
  for tooling improvements.

  This is a somewhat unusual project, in that it would likely consist of dozens
  of small improvements to the overall codebase, but this sort of work has a
  huge impact on the experience of other Zulip developers and thus the community
  as a whole (project leader Tim Abbott spends more time on the development
  experience than any other single area). 175 or 350 hours; difficult. **Skills
  required**: Python, some DevOps, and a passion for checking your work
  carefully. A strong applicant for this will have completed several projects in
  these areas.

  Expert: Tim Abbott

### Terminal app

Code: [The official multi-platform terminal app, written in
Python](https://github.com/zulip/zulip-terminal).

Experts: Neil Pilgrim, Aman Agrawal

- **Contribute to Zulip Terminal, our terminal user interface (TUI) client**.
  Zulip Terminal is out in beta, but there's still a lot to do for it to
  approach parity with the web app - and Zulip keeps coming out with new features too!

  Previous contributors have themed their projects according to a **cluster of
  features** or **completing unfinished projects**, or some combination, much
  like the first two bullets in the Full-stack project list.
  Project complexity and potential scope can vary substantially, since the
  required changes can involve touching different parts of the application
  stack. For example, these may be purely improving multiple elements of the UI,
  platform/terminal, or client-side model of the data available to a user - or
  multiple of these in a full-stack style.

  We would be happy to accept multiple strong students to work on this project.
  175 or 350 hours; medium difficulty.
  **Skills required**: Python 3 development skills, good communication and
  project management skills. Reading and understanding complex code and tests,
  and taking the initiative to propose clean refactoring and other solutions,
  will be highly valuable.

### Desktop app

Code:
[Our cross-platform desktop app, written in JavaScript on
Electron](https://github.com/zulip/zulip-desktop).

Expert: Anders Kaseorg

- **Contribute to our [Electron-based desktop client
  application](https://github.com/zulip/zulip-desktop)**. There's plenty of
  feature/UI work to do, but focus areas for us include things to (1) improve
  the release process for the app, using automated testing, TypeScript, etc.,
  and (2) polishing the UI. Browse the open issues and get involved! 175 or 350
  hours. This is a difficult project because it is important user-facing code
  without good automated testing, so the bar for writing high quality,
  reviewable PRs that convince others your work is correct is high. **Skills
  required**: JavaScript, Electron; you can learn Electron as part of your
  application.

- **Prototype a next generation Zulip desktop app implemented using
  the Tauri Rust-based framework**. Tauri is a promising new project
  that we believe is likely a better technical direction for client
  applications than Electron for desktop apps, for security and
  resource consumption reasons. The goal of this project would be to
  build a working prototype to evaluate to what extent Tauri is a
  viable platform for us to migrate the Zulip desktop app to. 350
  hours only; difficult. **Skills required**: Ability to learn
  quickly. Experience with Rust and secure software design may be
  helpful.

### Mobile app

Code:
[The next-generation Zulip mobile app,
written with Flutter](https://github.com/zulip/zulip-flutter)
(now in beta)

Experts: Greg Price, Chris Bobbe, Zixuan James Li

- Work on the **upcoming Flutter-based Zulip client**.
  Zulip has a freshly-written [new mobile app built on
  Flutter][flutter-beta-post], which we're nearing the point of
  rolling out to replace the legacy React Native-based app.
  We'll be using this foundation to build much-anticipated features
  that the Zulip mobile apps have never had before, as well as some
  that the legacy app had but were skipped for the initial rollout.

  This project will involve building features for the Flutter app,
  including code for UI, data structures, and interacting with the
  Zulip server and the Android and/or iOS platforms.
  For a sense of the features we're working on, see our
  [project board][flutter-board] for the new app;
  the tasks we'll be working on during GSoC will come mostly from
  the ["M6: Post-launch" milestone][flutter-milestone-post-launch].
  For some features, we [may find][flutter-upstream-summary]
  ourselves [contributing changes][flutter-upstream-autocomplete]
  upstream to the Flutter project itself. 175 or 350 hours; difficult.

  **Skills required**: Ability to learn quickly, check your work
  carefully, and communicate clearly and accurately. The code for
  this project will be written primarily in Dart atop Flutter;
  previous experience may be helpful, but you can learn both during
  the contributions leading up to your application. Previous
  experience with Android or iOS may also be helpful but is not
  necessary.

[flutter-beta-post]: https://blog.zulip.com/2024/12/12/new-flutter-mobile-app-beta/
[flutter-board]: https://github.com/orgs/zulip/projects/5/views/4
[flutter-milestone-launch]: https://github.com/zulip/zulip-flutter/milestone/4
[flutter-upstream-summary]: https://chat.zulip.org/#narrow/channel/2-general/topic/Flutter/near/1524757
[flutter-upstream-autocomplete]: https://github.com/flutter/flutter/pull/129802
