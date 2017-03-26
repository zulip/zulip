# Reviewing Zulip server code

This document is a brief discussion of what we look for when reviewing
contributions to Zulip. It's meant partially for developers who want
to get their code merged faster, and partially for developers who have
made successful pull requests already and would like to start
participating in code review.

## Things to look for

* *The Travis CI build.* The tests need to pass. One can investigate
  any failures and figure out what to fix by clicking on a red X next
  to the commit hash or the Detail links on a pull request. (Example:
  in [#1219](https://github.com/zulip/zulip/pull/1219), click the red
  X next to `f1f474e` to see the build jobs for that commit, at least
  one of which has failed. Click on the link for Travis continuous
  integrations details to see [the tests Travis ran on that
  commit](https://travis-ci.org/zulip/zulip/builds/144300899), at
  least one of which failed, and go to [one of the failing
  tests](https://travis-ci.org/zulip/zulip/jobs/144300901) to see the
  error.) Since Coveralls's data on changes isn't always accurate, one
  should look at the test coverage situation directly.

* *Technical design.* There are a lot of considerations here:
  security, migration paths/backwards compatibility, cost of new
  dependencies, interactions with features, speed of performance, API
  changes.  Security is especially important and worth thinking about
  carefully with any changes to security-sensitive code like views.

* *User interface and visual design.* If frontend changes are
  involved, the reviewer will check out the code, play with the new
  UI, and verify it for both quality and consistency with the rest of
  the Zulip UI.  We highly encourage posting screenshots to save
  reviewers time in getting a feel for what the feature looks like --
  you'll get a quicker response that way.

* *Error handling.* The code should always check for invalid user
  input.  User-facing error messages should be clear and when possible
  be actionable (it should be obvious to the user what they need to do
  in order to correct the problem).

* *Testing.* The tests should validate that the feature works
  correctly, and specifically test for common error conditions, bad
  user input, and potential bugs that are likely for the type of
  change being made.  Tests that exclude whole classes of potential
  bugs are preferred when possible (e.g., the common test suite
  `test_bugdown.py` between the [frontend and backend Markdown
  processors](markdown.html) or the `GetEventsTest` test for buggy
  race condition handling).

  Backend: we are trying to maintain ~100% test coverage on the
  backend, so backend changes should have negative tests for the
  various error conditions. Frontend: If the feature involves frontend
  changes, there should be frontend tests.  See the [test
  writing][test-writing] documentation for more details.

* *mypy annotations.* New functions should be annotated using [mypy]
  and existing annotations should be updated.  Use of `Any`, `ignore`,
  and unparameterized containser should be limited to cases where a
  more precise type cannot be specified.

* *Translation.* Make sure that the strings are marked for
  [translation].

* *Clear function, argument, variable, and test names.* Every new
  piece of Zulip code will be read many times by other developers, and
  future developers will grep for relevant terms when researching a
  problem, so it's important that variable names communicate clearly
  the purpose of each piece of the codebase.

* *Duplicated code.* Code duplication is a huge source of bugs in
  large projects and makes the codebase difficult to understand, so we
  avoid significant code duplication wherever possible.  Sometimes
  avoiding code duplication involves some refactoring of existing
  code; if so, that should usually be done as its own series of
  commits (not squashed into other changes or left as a thing to do
  later). That series of commits can be in the same pull request as
  the feature that they support, and we recommend ordering the history
  of commits so that the refactoring comes *before* the feature. That
  way, it's easy to merge the refactoring (and minimize risk of merge
  conflicts) if there are still user experience issues under
  discussion for the feature itself.

* *Completeness.* For refactorings, verify that the changes are
  complete.  Usually one can check that efficiently using `git grep`,
  and it's worth it, as we very frequently find issues by doing so.

* *Documentation updates.*  If this changes how something works, does it
  update the documentation in a corresponding way?  If it's a new
  feature, is it documented, and documented in the right place?

* *Good comments.* It's often worth thinking about whether explanation
  in a commit message or pull request discussion should be included in
  a comment, `/docs`, or other documentation. But it's better yet if
  verbose explanation isn't needed. We prefer writing code that is
  readable without explanation over a heavily commented codebase using
  lots of clever tricks.

* *Coding style.* See the Zulip [code-style] documentation for
  details.  Our goal is to have as much of this as possible verified
  via the linters and tests, but there's always going to be unusual
  forms of Python/JavaScript style that our tools don't check for.

* *Clear commit messages.* See the [Zulip version
  control][commit-messages] documentation for details on what we look
  for.

## Tooling

To make it easier to review pull requests, use our [git tool]
`tools/fetch-rebase-pull-request` to check out a pull request locally
and rebase it against master. If a pull request just needs a little
fixing to make it mergeable, feel free to do that in a new commit,
then push your branch to GitHub and mention the branch in a comment on
the pull request. That'll save the maintainer time and get the PR
merged quicker.

## Additional Resources

We also strongly recommend reviewers to go through the following resources.

* [The Gentle Art of Patch Review](http://sarah.thesharps.us/2014/09/01/the-gentle-art-of-patch-review/)
  article by Sarah Sharp
* [Zulip & Good Code Review](https://www.harihareswara.net/sumana/2016/05/17/0)
  article by Sumana Harihareswara
* [Code Review - A consolidation of advice and stuff from the
   sinternet](https://gist.github.com/porterjamesj/002fb27dd70df003646df46f15e898de)
  article by James J. Porter
* [Zulip Code of Conduct](https://zulip.readthedocs.io/en/latest/code-of-conduct.html)

[code-style]: code-style.html
[commit-messages]: version-control.html#commit-messages
[test-writing]: testing.html
[mypy]: mypy.html
[git tool]: git-guide.html#fetch-a-pull-request-and-rebase
[translation]: translating.html
