# Quick start: How Zulip uses Git and GitHub

This quick start provides a brief overview of how Zulip uses Git and GitHub.

Those who are familiar with Git and GitHub should be able to start contributing
with these details in mind:

- We use **GitHub for source control and code review.** To contribute, fork
  [zulip/zulip][github-zulip-zulip] (or the appropriate
  [repository][github-zulip], if you are working on something else besides
  Zulip server) to your own account and then create feature/issue branches.
  When you're ready to get feedback, submit a work-in-progress (WIP) pull
  request. *We encourage you to submit WIP pull requests early and often.*

- We use a **[rebase][gitbook-rebase]-oriented workflow.** We do not use merge
  commits. This means you should use `git fetch` followed by `git rebase`
  rather than `git pull` (or you can use `git pull --rebase`). Also, to prevent
  pull requests from becoming out of date with the main line of development,
  you should rebase your feature branch prior to submitting a pull request, and
  as needed thereafter. If you're unfamiliar with how to rebase a pull request,
  [read this excellent guide][github-rebase-pr].

  We use this strategy in order to avoid the extra commits that appear
  when another branch is merged, that clutter the commit history (it's
  popular with other large projects such as Django).  This makes
  Zulip's commit history more readable, but a side effect is that many
  pull requests we merge will be reported by GitHub's UI as *closed*
  instead of *merged*, since GitHub has poor support for
  rebase-oriented workflows.

- We have a **[code style guide][zulip-rtd-code-style]**, a **[commit message
  guide][zulip-rtd-commit-messages]**, and strive for each commit to be *a
  minimal coherent idea* (see **[commit
  discipline][zulip-rtd-commit-discipline]** for details).

- We provide **many tools to help you submit quality code.** These include
  [linters][zulip-rtd-lint-tools], [tests][zulip-rtd-testing], continuous
  integration with [Travis CI][travis-ci], and [mypy][zulip-rtd-mypy].

- We use [zulipbot][zulip-rtd-zulipbot-usage] to manage our issues and
  pull requests to create a better GitHub workflow for contributors.

- We provide some handy **[Zulip-specific Git scripts][zulip-rtd-zulip-tools]**
  for developers to easily do tasks like fetching and rebasing a pull
  request, cleaning unimportant branches, etc. These reduce the common
  tasks of testing other contributors' pull requests to single commands.

Finally, install the [Zulip developer environment][zulip-rtd-dev-overview], and then
[configure your fork for use with Travis CI][zulip-git-guide-travisci].

***

The following sections will help you be awesome with Zulip and Git/GitHub in a
rebased-based workflow. Read through it if you're new to git, to a rebase-based
git workflow, or if you'd like a git refresher.

[gitbook-rebase]: https://git-scm.com/book/en/v2/Git-Branching-Rebasing
[github-rebase-pr]: https://github.com/edx/edx-platform/wiki/How-to-Rebase-a-Pull-Request
[github-zulip]: https://github.com/zulip/
[github-zulip-zulip]: https://github.com/zulip/zulip/
[travis-ci]: https://travis-ci.org/
[zulip-git-guide-travisci]: ../git/cloning.html#step-3-configure-travis-ci-continuous-integration
[zulip-rtd-code-style]: ../contributing/code-style.html
[zulip-rtd-commit-discipline]: ../contributing/version-control.html#commit-discipline
[zulip-rtd-commit-messages]: ../contributing/version-control.html#commit-messages
[zulip-rtd-dev-overview]: ../development/overview.html
[zulip-rtd-lint-tools]: ../contributing/code-style.html#lint-tools
[zulip-rtd-mypy]: ../contributing/mypy.html
[zulip-rtd-testing]: ../testing/testing.html
[zulip-rtd-zulip-tools]: ../git/zulip-tools.html
[zulip-rtd-zulipbot-usage]: ../contributing/zulipbot-usage.html
