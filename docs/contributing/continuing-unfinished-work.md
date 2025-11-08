# Continuing unfinished work

Sometimes, work is started on an issue or PR, but not brought to completion.
This may happen for a variety of reasons — the contributor working on the
project gets busy, maintainers cannot prioritize reviewing the work, a
contributor doesn't have the skills required to complete the project, there is
an unexpected technical challenge or blocker, etc.

Completing work that someone else has started is a great way to contribute! Here
are the steps required:

1. [Find work to be completed.](#find-work-to-be-completed)
1. [Review existing work and feedback.](#review-existing-work-and-feedback)
1. [Decide how to use prior work.](#decide-how-to-use-prior-work)
1. [Credit prior work in your commit history.](#credit-prior-work-in-your-commit-history)
1. [Present your pull request.](#present-your-pull-request)

## Find work to be completed

In Zulip's server and web app [repository](https://github.com/zulip/zulip), pull
requests that have significant work towards something valuable are often tagged
with a [completion candidate][completion-candidate] label. You can review
this label for unfinished work that you find interesting and have the skills to
complete.

Note that it's common to see one or more pull requests linked to an issue
you're interested in. The guidelines below apply regardless of whether you
intentionally set out to find work to complete or simply find yourself
building on someone else's work.

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
1. Make sure the work of others is [properly credited](#credit-prior-work-in-your-commit-history).
1. [Self-review](../contributing/code-reviewing.md), test, and revise the work,
   including potentially [splitting out](../contributing/commit-discipline.md)
   preparatory commits to make it easier to read. You should be proud of the
   resulting series of commits, and be prepared to argue that it is the best
   work you can produce to complete the issue.

Otherwise, you can:

1. Make your own changes from scratch.
1. Go through reviewer feedback on prior work. Would any of it apply to the
   changes you're proposing? Be sure to address it if so.

## Credit prior work in your commit history

When you use or build upon someone else's unmerged work, it is both
professionally and ethically necessary to [properly
credit][coauthor-git-guide] their contributions in the commit history
of work that you submit. Git, used properly, does a good job of
preserving the original authorship of commits.

However, it's normal to find yourself making changes to commits
originally authored by other contributors, whether resolving merge
conflicts when doing `git rebase` or fixing bugs to create an
atomically correct commit compliant with Zulip's [commit
guidelines](../contributing/commit-discipline.md).

When you do that, it's your responsibility to ensure the resulting
commit series correctly credits the work of everyone who materially
contributed to it. The most direct way to credit the work of someone
beyond the commit's author maintained in the Git metadata is
`Co-authored-by:` line after a blank line at the end of your commit
message:

    Co-authored-by: Greg Price <greg@zulip.com>

Be careful to type it precisely, because software parses these commit
message records in generating statistics. You should add such a line
in two scenarios:

- If your own work was squashed into a commit originally authored by
  another contributor, add such a line crediting yourself.
- If you used another contributor's work in generating your own
  commit, add such a line crediting the other contributor(s).

Sometimes, you make a mistake when rebasing and accidentally squash
commits in a way that messes up Git's authorship records. Often,
undoing the rebase change via `git reflog` is the best way to correct
such mistakes, but there are two other Git commands that can be used
to correct Git's primary authorship information after the fact:

- `git commit --amend --reset-author` will replace the Git commit
  metadata (date, author, etc.) of the currently checked out commit
  with yourself. This is useful to correct a commit that incorrectly
  shows someone else as the author of your work.
- `git commit --amend -C <commit_id>` will replace the commit metadata
  (date, author, etc.) on a commit with that of the provided commit
  ID. This is useful if you accidentally made someone else's commit
  show yourself as the author, or lost a useful commit message via
  accidental squashing. (You can usually find the right commit ID to
  use with `git reflog` or from GitHub).

As an aside, maintainers who modify commits before merging them are
credited via Git's "Committer" records (visible with `git show
--pretty=fuller`, for example). As a result, they may not bother with
adding a separate `Co-authored-by` record on commits that they revise
as part of merging a pull request.

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

- **Give credit where credit is due.** Reviewers should be able to examine your
  commit history and see that you have [properly credited](#credit-prior-work-in-your-commit-history)
  the work of others.

- **Explain the relationship between your PR and prior work** in the description
  for your pull request. This is required for your PR to be reviewed, as
  reviewing a new PR when there is an existing one is a good use of time only if
  the motivation for doing so is clear.
  - If you started from an existing PR, explain what changes you made, and how
    you addressed each point of reviewer feedback that hadn't been addressed previously.
  - If you started from scratch, explain _why_ you decided to do so, and how
    your approach differs from prior work. For example:
    - "I didn't use the work in PR #12345, because the surrounding code has
      changed too much since it was written."
    - "I didn't use the work in PR #23154, because [this reviewer
      comment](#present-your-pull-request) asked to solve this issue using CSS,
      rather than the JavaScript changes made in #23154."
    - "I didn't use the work in PRs #12345 and #23154, because both didn't work
      properly when a user opened their own profile."

[completion-candidate]: https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22completion+candidate%22
[coauthor-git-guide]: https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors
