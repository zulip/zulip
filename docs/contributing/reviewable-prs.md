# Reviewable pull requests

This page offers some tips for making your pull requests easy to review.
Following this advice will help the whole Zulip project move more quickly by
saving maintainers time when they review your code. It will also make a big
difference for getting your work integrated without delay.

## Posting a pull request

- Before requesting a review for your pull request, follow our guide to
  carefully [review and test your own
  code](./code-reviewing.md#reviewing-your-own-code). Doing so can save many
  review round-trips.

- Make sure the pull request template is filled out correctly, and that all the
  relevant points on the self-review checklist (if the repository has one) have
  been addressed.

- Be sure to explicitly call out any open questions, concerns, or decisions you
  are uncertain about.

## Addressing feedback

- When you update your PR after addressing a round of review feedback, be clear
  about which issues you've resolved (and how!).

- Even more importantly, save time for your reviewers by indicating any feedback
  you _haven't_ addressed yet.

## Working on larger projects

For a larger project, aim to create a series of small (less than 100 lines of
code) commits that are each safely mergeable and move you towards your goal. A
mergeable commit:

- Is well-tested and passes all the tests. That is, changes to tests should be in
  the same commit as changes to the code that they are testing.

- Does not make Zulip worse. For example, it is fine to add backend capabilities
  without adding a frontend to access them. It's not fine to add a frontend
  component with no backend to make it work.

Ideally, when reviewing a branch you are working on, the maintainer
should be able to verify and merge the first few commits and leave
comments on the rest. It is by far the most efficient way to do
collaborative development, since one is constantly making progress, we
keep branches small, and developers don't end up repeatedly reviewing
the earlier parts of a PR.

Here is some advice on how to proceed:

- Use `git rebase -i` as much as you need to shape your commit
  structure. See the [Git guide](../git/overview.md) for useful
  resources on mastering Git.

- If you need to refactor code, add tests, rename variables, or make
  other changes that do not change the functionality of the product, make those
  changes into a series of preparatory commits that can be merged independently
  of building the feature itself.

- To figure out what refactoring needs to happen, you might first make a hacky
  attempt at hooking together the feature, with reading and print statements as
  part of the effort, to identify any refactoring needed or tests you want to
  write to help make sure your changes won't break anything important as you work.
  Work out a fast and consistent test procedure for how to make sure the
  feature is working as planned.

- Build a mergeable version of the feature on top of those refactorings.
  Whenever possible, find chunks of complexity that you can separate from the
  rest of the project.

See our [commit discipline guide](../contributing/commit-discipline.md) for
more details on writing reviewable commits.
