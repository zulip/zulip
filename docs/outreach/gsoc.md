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

For 2024, we are particularly interested in GSoC contributors who have
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

  Recent sweeps through the Zulip server and web app tracker have
  identified about 100 open pull requests where a previous contributor
  (sometimes via GSoC!) did significant work towards something
  valuable, and there's significant feedback from maintainers, but the
  project was never finished, and requires significant further effort
  from a new contributor in order to progress. These are tracked via
  the [completion candidate label][completion-candidate]. One of our
  goals for this summer's GSoC is to complete many of these
  issues. Start by picking something that's interesting to you, and
  you feel you have the skills required to complete. Read the code and
  the feedback, and then create your own PR for the issue. Remember to
  carefully test your work (there may be problems that the reviewers
  missed, or that were introduced by rebasing across other changes!),
  and credit the original contributor [as documented in our commit
  guidelines](../contributing/commit-discipline.md). We expect to have
  a more detailed guide on this process available this Spring.
  **Skills required**: Varies with project; a common skill will be
  good reading comprehension and organization/communication skills, to
  walk maintainers through how you resolved problems, addressed any
  pending feedback on the previous PR, and your understanding of the
  outstanding questions for a given project. Taking the time to get
  really good at resolving merge conflicts is likely to be valuable
  here as well.

  Experts: Tim Abbott and various others depending on project area

[completion-candidate]: https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22completion+candidate%22

- Help **migrate our JavaScript codebase to Typescript**. Zulip is in
  the process of porting the main web app JavaScript codebase to
  TypeScript; at present, about 40% of the project is written in
  TypeScript. We've resolved most of the roadblocks to completing this
  migration, so it's mostly a matter of carefully translating modules,
  putting in the effort with preparatory commits to make it any
  refactoring easy to verify. Our goal is to leave the resulting code
  more readable than it was before, always test the module works after
  the migration, and avoid introducing logic bugs during this large
  refactor. [This topic in the Zulip development
  community][typescript-migration] is a good place to coordinate work
  on this project. Multiple students are possible; 175 or 350 hours;
  difficult. **Skills required**: TypeScript and refactoring
  expertise; we're specifically interested in students who are a type
  theory nerd and are invested in writing types precisely (Often using
  [Zod](https://zod.dev/) to parse and verify data received from the
  server) and checking their work carefully.

  Experts: Zixuan James Li, Evy Kassirer, Anders Kaseorg

[typescript-migration]: https://chat.zulip.org/#narrow/channel/6-frontend/topic/typescript.20migration

- Contribute to Zulip's [**migration to user groups for
  permissions**][user-group-permissions]. This migration is intended to replace
  every setting in Zulip that currently allows organizations to assign
  permissions based on role (admin, moderator, etc.) with a setting based on
  arbitrary "user groups", making it much more customizable. This is very
  important for large organizations using Zulip, including businesses and
  open-source projects. Much of the basic design, API structure, and scaffolding
  is complete, but there is a lot of work that remains to complete this vision.
  The project can likely support a couple students; there is considerable work
  to be done on the settings UI, both for user groups and for channel and
  organization-level settings, dozens of existing settings to migrate, and [many
  new settings][organization-settings-label] that users have long requested that
  we've delayed adding in order to avoid having to migrate them. 175 or 350
  hours; moderate difficulty. **Skills required**: Python, JavaScript, and CSS.
  Attention to detail around code reuse/duplication, thoughtful testing, and
  splitting large migrations into reviewable chunks.

  Experts: Sahil Batra

- Improve the framework and UI in **Zulip's overlays for managing
  channels and groups**. These two components have very parallel design
  patterns and implementations (the groups one is quite new!). Coupled
  with the user groups permissions migration, the goal of this project
  is to make these important settings panels ergonomic for the large
  number of new settings that we expect to migrate or add via the
  groups migration. See the [user groups
  settings][group-settings-issues] and [channel
  settings][channel-settings-issues] area labels for starter projects.

  Experts: Purushottam Tiwari, Sahil Batra

[group-settings-issues]: https://github.com/zulip/zulip/issues?q=is%3Aissue+is%3Aopen+label%3A%22area%3A+settings+%28user+groups%29%22
[channel-settings-issues]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+stream+settings%22
[user-group-permissions]: https://github.com/zulip/zulip/issues/19525
[organization-settings-label]: https://github.com/zulip/zulip/issues?q=is%3Aopen+is%3Aissue+label%3A%22area%3A+settings+%28admin%2Forg%29%22

- Migrate Zulip's **[direct message recipient data
  structures](https://github.com/zulip/zulip/issues/25713)** to a new
  model that enables personal settings associated with a direct
  message conversation, and add several settings (see the linked
  issues) enabled by that infrastructure work. **Skills required**:
  This project will be deep Python 3/PostgreSQL work. Concretely,
  challenging parts of this project include thinking about races and
  database transactions, writing database migrations intended to be
  run live at scale, complex internal refactors, and carefully
  verifying the indexes used by migrated database queries.

  Experts: Tim Abbott, Mateusz Mandera, Prakhar Pratyush

- Add the core infrastructure for **topic-based permissions and settings**
  like [pinned topics](https://github.com/zulip/zulip/issues/19483)
  and [read-only topics](https://github.com/zulip/zulip/issues/26944),
  and then build some of those settings. This project will be a
  mixture of Python 3/PostgreSQL work, including thinking about
  database transactions and races, writing database migrations
  intended to be run live at scale, and complex logic to handle moving
  messages correctly in the context of these settings, including
  significant changes to the Zulip API and API documentation.

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

- **Optimize performance and scalability**, either for the web frontend or
  the server. Zulip is already one of the faster web apps out there,
  but we have a number of ideas for how to make it substantially
  faster yet. This is likely a particularly challenging project to do
  well, since there are a lot of subtle interactions to
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

  Experts: Zixuan James Li, Lauryn Menard

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

  Experts: Zixuan James Li, Lauryn Menard

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

Code: [Zulip Terminal](https://github.com/zulip/zulip-terminal)

Experts: Neil Pilgrim, Aman Agrawal

- Work on Zulip Terminal, the official terminal client for Zulip. zulip-terminal
  is out in beta, but there's still a lot to do for it to approach parity with
  the web app. We would be happy to accept multiple strong students to work on
  this project. 175 or 350 hours; medium difficulty. **Skills required**: Python
  3 development skills, good communication and project management skills, good
  at reading code and testing.

### Desktop app

Code:
[Our cross-platform desktop app written in JavaScript on
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

Experts: Greg Price, Chris Bobbe

- Work on the **upcoming Flutter-based Zulip client**.
  We're in the midst of [rewriting Zulip's mobile app][flutter-why]
  from scratch using Flutter, to replace the legacy React Native-based
  app. The Flutter app [reached beta][flutter-beta] in
  December 2023, we're working now toward a wider beta, and during the
  GSoC 2024 period we expect to be working toward turning the beta
  into a version we can roll out for all Zulip's mobile users.

  This project will involve building features for the Flutter app,
  including code for UI, data structures, and interacting with the
  Zulip server and the Android and/or iOS platforms.
  For a sense of the features we're working on, see our
  [project board][flutter-board] for the new app;
  the ["Launch" milestone][flutter-milestone-launch]
  corresponds roughly to what we expect to be working on during GSoC.
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

[flutter-why]: https://chat.zulip.org/#narrow/channel/2-general/topic/Flutter/near/1582367
[flutter-beta]: https://chat.zulip.org/#narrow/channel/2-general/topic/Flutter/near/1708728
[flutter-board]: https://github.com/orgs/zulip/projects/5/views/4
[flutter-milestone-launch]: https://github.com/zulip/zulip-flutter/milestone/3
[flutter-upstream-summary]: https://chat.zulip.org/#narrow/channel/2-general/topic/Flutter/near/1524757
[flutter-upstream-autocomplete]: https://github.com/flutter/flutter/pull/129802
