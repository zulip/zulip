# Continuing unfinished work

Sometimes, work on an issue is started, but not brought to completion. This may
happen for a variety of reasons — the contributor working on the project gets
busy, maintainers cannot prioritize reviewing the work, a contributor doesn't
have the skills required to complete the project, there is
an unexpected technical challenge or blocker, etc.

Completing work that someone else has started is a great way to contribute! Here
are the steps required:

1. [Find work to be completed.](#find-work-to-be-completed)
1. [Review existing work and feedback.](#review-existing-work-and-feedback)
1. [Decide how to use prior work.](#decide-how-to-use-prior-work)
1. [Present your pull request.](#present-your-pull-request)

## Find work to be completed

In Zulip's server and web app [repository](https://github.com/zulip/zulip), pull
requests that have significant work towards something valuable are often tagged
with a [completion candidate label][completion-candidate] label. You can review
this label for issues that you find interesting and have the skills to complete.

In general, it's common to see one or more pull request linked to an issue
you're interested in. The guidelines below apply regardless of whether you
intentionally set out to find work to complete.

## Review existing work and feedback

Any time there are pull requests linked to the issue you are working on, start
by reviewing the existing work. Read the code, and pay close attention to any
feedback the pull request received. This will help you avoid any pitfalls other
contributors encountered.

## Decide how to use prior work

Consider how to use prior work on the issue. In your best judgment, is the
existing PR on the right track? If there's reviewer feedback, it should help you
figure this out.

If prior work looks like a good start:

1. Pull down the existing pull request.
1. Rebase it on the current version of the `main` branch.
1. Carefully address any open feedback from reviewers.
1. Make any other changes you think are needed, including completing any parts
   of the work that had not been finished.
1. [Self-review](../contributing/code-reviewing.md), test, and revise the work,
   including potentially [splitting out](../contributing/commit-discipline.md)
   preparatory commits to make it easier to read. You should be proud of the
   resulting series of commits, and be prepared to argue that it is the best
   work you can produce to complete the issue.

Otherwise, you can:

1. Make your own changes from scratch.
1. Go through reviewer feedback on prior work. Would any of it apply to the
   changes you're proposing? Be sure to address it if so.

## Present your pull request

In addition to the usual [guidance](../contributing/reviewable-prs.md) for
putting together your pull request, there are a few key points to keep in mind.

- **Take responsibility for the work.** Any time you propose changes to the
  Zulip project, you are accountable for those changes. Do your very best to verify that they are correct.

  - Don't submit code you don't understand — dig in to figure out what it's
    doing, even if you didn't write it. This is a great way to catch bugs and
    make improvements.
  - Test the work carefully, even if others have tested it before. There may be
    problems that the reviewers missed, or that were introduced by rebasing across other changes.

- **Give credit where credit is due.** In the commit message for any commits
  that use somebody else's work, [credit][coauthor-git-guide] co-authors by
  adding a `Co-authored-by:` line after a blank line at the end of your commit
  message:

      Co-authored-by: Greg Price <greg@zulip.com>

- **Explain the relationship between your PR and prior work** in the description
  for your pull request.
  - If you started from an existing PR, explain what changes you made, and how
    you addressed each point of reviewer feedback that hadn't been addressed previously.
  - If you started from scratch, explain _why_ you decided to do so, and how
    your approach differs from prior work.

[completion-candidate]: https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22completion+candidate%22
[coauthor-git-guide]: https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors
