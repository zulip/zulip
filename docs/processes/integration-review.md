# Integration review

This page details the process of integration review for pull requests.
Integration review serves several purposes:

- A second opinion to the maintainer review.
- An end-to-end check that a PR's changes have the necessary approvals as
  part of our process of getting the attention of subject-matter experts on
  changes that could result in expensive mistakes.
- An end-to-end check that potential risks have been suitably managed.
- An opportunity to kick off follow-up work.

Key resources that you should understand well before doing integration
review on general changes:

- Our general maintainer review resources, including the [review
  process](../contributing/review-process.md)
- The process for [design
  discussions](../contributing/design-discussions.md), and how to
  determine whether the design/UI component of a project has
  consensus/approval. It is very common for eager contributors to
  ask you to merge something that would seriously regress the UI and
  has not been suitably discussed.
- How [API design](../processes/api-design.md) decisions are made. It is
  the responsibility of the integration reviewer to confirm that an API
  change has been approved before integrating a change. It is common
  for an integration review result to be "This looks great, except I can't
  tell if we have API design approval for this field name."
- Zulip's [testing philosophy](../testing/philosophy.md).
- [Database migrations](../subsystems/schema-migrations.md), including the
  additional considerations related to Cloud (online migrations due to
  large data size) and self-hosting (migrations need to Just Work or they
  will generate ~infinite unpleasant support work as installations upgrade).
- Our [tools](../git/zulip-tools.md) for working with contributor PRs.
- What failure modes you can expect existing [automated
  tests](../testing/testing.md) to reliably catch, so that you can
  focus your attention on failure modes that they cannot. If you
  ever see a bug in a PR that you thought the testing system should
  have caught, report that as a tooling bug.
- How to tell whether a change to the Zulip data model is a good one.
- Familiarity with the full set of pages in this ReadTheDocs site
  is extremely helpful. You don't need to have read every page, but
  you should know what exists, or have habits of searching/grepping
  that ensure you are making decisions with full access to
  relevant project context and history.

(Obviously, use your judgement. If you're only merging CSS changes,
it's not critical that you understand how to check if a database
schema change is risky, just to know that's a category of change that
you should hand off to a different reviewer.)

## Risks to manage

### General

- Is this a user experience checkpoint that we'd be OK with going out
  to production by accident, or reaching self-hosters who upgrade to
  `main`? Would a UX change expose users to risk or breakage that we'd
  find embarrassing?

### Readability

- Function reuse land mines, where a function does not do exactly what
  its name suggests it will do.
- Cross-linking of documentation to help understanding. E.g., if we
  have a nice document explaining an algorithm we just wrote, is it
  linked to from all the places that should? (Code comments in that
  code path, related docs, etc.)
- Code that is hard to read. If you notice yourself spending a bit
  trying to figure out what some code does, and succeed, always ask:
  "How could this code be improved or commented so that the next
  person doesn't find it hard to follow?"

### Code quality

- Excessive testing costs, either for humans to read or requiring
  excessive runtime.
- Logic that violates the product's security model.
- Security land mines, where security depends on each caller of a
  function checking separately the properties central to the
  correctness of a code path.
- Caching and performance mistakes. E.g., it is far easier to catch
  accidentally quadratic code before you've merged it.

### Server

- Transaction model issues, either work that should be atomic
  but needlessly isn't, or multi-minute transactions.
- Audit logs and information destruction risks.

### Web app

- Cross-site scripting bugs. Pay special attention to `{{{` in
  Handlebars templates and manual HTML encoding/decoding.
- New Puppeteer tests should have a convincing case for why they are
  worth their runtime.
- Any changes involving browser local storage can have major
  compatibility issues that break the app.
- UI churn risk if we're still iterating on something in core
  workflows (not just settings).
- Error handling that could make a future error/mistake worse. E.g.,
  anything touching the logic that reloads the web app.

## Checklist

Here are some mental tests to consider applying when merging a pull
request:

- Could this PR fail CI after being rebased onto `upstream/main`? When
  in doubt, manually rebase and configure to merge once CI passes,
  instead of using an immediate "Rebase and merge".
- Are there any follow-ups to this work that we'd be sad to discover
  in 4 months hadn't been done? If so, what is the concrete
  plan for ensuring those are integrated soon? Are follow-ups tracked on the
  release board, or assigned to an owner who can be counted on to do
  it?
- Did you remember to express appreciation for the work, including
  making sure the project has thanked the original reporter?
- If we discover a serious problem tomorrow that requires reverting
  this, what will happen?
- Do commit messages correctly and helpfully explain the commits we're
  actually merging? (Sometimes contributors redo the change a lot
  without editing these).
- Are there any risks with sending this to Cloud or self-hosted
  systems that the review process this far may not have validated?

## Mistakes

We are all human, and you will definitely at some point integrate
something you didn't intend to or later discover was a mistake. It's
important to avoid disrupting others' work, and a broken `main` branch
is a good reason to push changes to `main` without waiting for CI to
run, if you are confident your fix is correct.

You have a few options:

- **Fix forward**. This is best when the mistake is a simple CI
  failure, like a lint issue: just fix the linter and push a fix
  promptly. It is also a good choice for less urgent mistakes that
  can happily be a follow-up improvement.
- **Revert the change** in a new commit. This is recommended in any
  case where you cannot resolve an issue that will impact others' work
  via a fix forward quickly. Note that `git revert` accepts a range of
  commits. It may feel ugly, but it's fine.

The following option also exists:

- **Force-push**. This is necessary if the incorrectly merged changes
  are problematic to have in the project's history. (Say, you checked
  in a 2GB video or your Driver's License). Note that Weblate will
  require manual fixing if you force-push in `zulip/zulip`, so be sure
  to check the translation channel to manage this.

Some common mistakes to watch out for:

- Pushing revisions to the wrong PR. If you run
  `tools/push-to-pull-request <ID>` and paste in the wrong pull
  request ID, you'll have overwritten code was on that other PR. The
  console output will contain the old commit ID for the overwritten
  PR, which can sometimes let you recover if you have a copy of
  that. But typically, you have to just ask the PR's author to
  re-upload the correct code to their pull request.

  (If you did `--merge`, GitHub offers no undo for a merged PR, so the
  only option is to post comments cross-linking and explaining what
  happened).

- Merging a pull request with API changes without running
  `tools/merge-api-changelogs` to allocate a feature level number. CI
  should complain, and you can then run the merge command in a
  follow-up commit. If the commit history has many separate feature-level
  commits when merging a PR that stacked several API changes from
  different commits in a feature level, it's not a big deal. (But
  typically, we squash the `merge-api-changelogs` commit when there's
  only one commit in a PR touching the API, to keep the history clean).

- Merging a pull request with migrations without rebasing the the work
  and running `tools/renumber-migrations`. PRs older than a couple
  weeks are very likely to have duplicate migration numbers.
