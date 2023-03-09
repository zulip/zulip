# Commit discipline

We follow the Git project's own commit discipline practice of "Each
commit is a minimal coherent idea". This discipline takes a bit of work,
but it makes it much easier for code reviewers to spot bugs, and
makes the commit history a much more useful resource for developers
trying to understand why the code works the way it does, which also
helps a lot in preventing bugs.

Commits must be coherent:

- It should pass tests (so test updates needed by a change should be
  in the same commit as the original change, not a separate "fix the
  tests that were broken by the last commit" commit).
- It should be safe to deploy individually, or explain in detail in
  the commit message as to why it isn't (maybe with a [manual] tag).
  So implementing a new API endpoint in one commit and then adding the
  security checks in a future commit should be avoided -- the security
  checks should be there from the beginning.
- Error handling should generally be included along with the code that
  might trigger the error.
- TODO comments should be in the commit that introduces the issue or
  the functionality with further work required.

Commits should generally be minimal:

- Significant refactorings should be done in a separate commit from
  functional changes.
- Moving code from one file to another should be done in a separate
  commits from functional changes or even refactoring within a file.
- 2 different refactorings should be done in different commits.
- 2 different features should be done in different commits.
- If you find yourself writing a commit message that reads like a list
  of somewhat dissimilar things that you did, you probably should have
  just done multiple commits.

When not to be overly minimal:

- For completely new features, you don't necessarily need to split out
  new commits for each little subfeature of the new feature. E.g., if
  you're writing a new tool from scratch, it's fine to have the
  initial tool have plenty of options/features without doing separate
  commits for each one. That said, reviewing a 2000-line giant blob of
  new code isn't fun, so please be thoughtful about submitting things
  in reviewable units.
- Don't bother to split backend commits from frontend commits, even
  though the backend can often be coherent on its own.

Other considerations:

- Overly fine commits are easy to squash later, but not vice versa.
  So err toward small commits, and the code reviewer can advise on
  squashing.
- If a commit you write doesn't pass tests, you should usually fix
  that by amending the commit to fix the bug, not writing a new "fix
  tests" commit on top of it.

Zulip expects you to structure the commits in your pull requests to form
a clean history before we will merge them. It's best to write your
commits following these guidelines in the first place, but if you don't,
you can always fix your history using `git rebase -i` (more on that
[here](../git/fixing-commits.md)).

Never mix multiple changes together in a single commit, but it's great
to include several related changes, each in their own commit, in a
single pull request. If you notice an issue that is only somewhat
related to what you were working on, but you feel that it's too minor
to create a dedicated pull request, feel free to append it as an
additional commit in the pull request for your main project (that
commit should have a clear explanation of the bug in its commit
message). This way, the bug gets fixed, but this independent change
is highlighted for reviewers. Or just create a dedicated pull request
for it. Whatever you do, don't squash unrelated changes together in a
single commit; the reviewer will ask you to split the changes out into
their own commits.

It can take some practice to get used to writing your commits with a
clean history so that you don't spend much time doing interactive
rebases. For example, often you'll start adding a feature, and discover
you need to do a refactoring partway through writing the feature. When that
happens, we recommend you stash your partial feature, do the refactoring,
commit it, and then unstash and finish implementing your feature.

For additional guidance on how to structure your commits (and why it matters!),
check out GitHub's excellent [blog post](https://github.blog/2022-06-30-write-better-commits-build-better-projects).

## Commit messages

Commit messages have two parts:

1. A **summary**, which is a one-line overview of the changes made.
2. A **description**, which provides further details on the changes made, and the
   motivation behind them.

The commit summary itself has a two-part structure:

1. A one or two word description of the part of the code base changed by the
   commit.
2. A short sentence summarizing your changes.

Here is an
[example](https://github.com/zulip/zulip/commit/084dd216f017c32e15c1b13469bcbc928cd0bce9)
of a good commit message:

> tests: Remove ignored realm_str parameter from message send test.
>
> In commit
> [8181ec4](https://github.com/zulip/zulip/commit/8181ec4b56abf598223112e7bc65ce20f3a6236b),
> we removed the `realm_str` as a parameter for `send_message_backed`. This
> removes a missed test that included this as a parameter for that
> endpoint/function.

The commit message is a key piece of how you communicate with reviewers and
future contributors, and is no less important than the code you write. This
section provides detailed guidance on how to write an excellent commit message.

**Tip:** You can set up [Zulip's Git pre-commit hook][commit-hook] to
automatically catch common mistakes in the commit message.

[commit-hook]: ../git/zulip-tools.md#set-up-git-repo-script

### Commit summary, part 1

The first part of the commit summary should only be 1-2 words, followed by a
`:`. In most cases, it will describe the part of the product you are changing.

Common examples include: settings, message feed, compose, left sidebar, right
sidebar, recent (for **Recent conversations**), search, markdown, tooltips,
popovers, drafts, integrations, email, docs, help, and api docs. In some cases,
it's helpful to be a little more specific, e.g., emoji, spoilers, polls. If your
commit doesn't cleanly map to a part of the product, you might use something
like "css" for CSS-only changes, or the name of the file you refactored (not the
full path).

There is no need to be creative here! If one of the examples above fits your
commit, use it. Consistency makes it easier for others to scan commit messages
to find what they need.

Additional tips:

- Use lowercase (e.g., "settings", not "Settings").
- If it's hard to find a 1-2 word description of the part of the code base
  affected by your commit, consider again whether you have structured your
  commits well.
- Never use a generic term like "bug", "fix", or "refactor".

### Commit summary, part 2

This is a **complete sentence** that briefly summarizes your changes. There are
a few rules to keep in mind:

- Start the sentence with an
  [imperative](https://en.wikipedia.org/wiki/Imperative_mood) verb, e.g.
  "fix", "add", "change", etc.
- Use proper capitalization and punctuation.
- Avoid acronyms.
- Use no more than 76 characters for the entire commit summary (parts 1 and 2).

### Examples of good commit summaries

- provision: Improve performance of installing npm.

- channel: Discard all HTTP responses while reloading.

- integrations: Add GitLab integration.

- typeahead: Convert to ES6 module.

- tests: Compile Handlebars templates with source maps.

- blueslip: Add feature to time common operations.

- gather_subscriptions: Fix exception handling bad input.

#### Detailed example

- **Good summary**: "gather_subscriptions: Fix exception handling bad input."
- **Not so good alternatives**:
  - "gather_subscriptions was broken": This doesn't explain how it was broken, and
    doesn't follow the format guidelines for commit summaries.
  - "Fix exception when given bad input": It's impossible to tell what part of the
    codebase was changed.
  - Not using the imperative:
    - "gather_subscriptions: Fixing exception when given bad input."
    - "gather_subscriptions: Fixed exception when given bad input."

### Commit description

The body of the commit message should explain why and how the change was made.
Like a good code comment, it should provide context and motivation that will
help a developer looking at your changes a year later understand the motivation
behind your decisions.

Many decisions should be documented in both the commit message and the
description for your pull request. The general rule of thumb is:

- If the information is helpful for reviewing your work, include it in the PR
  description.
- If the information will be helpful long-term for someone trying to
  understand the code base, include it in the commit message.

For example, if you have a question that you expect to be resolved during the
review process, put it in the PR description. Later, update the commit
description to document the reasoning behind the decision.

When you fix a GitHub issue, [mark that you have fixed the issue in your commit
message](https://help.github.com/en/articles/closing-issues-via-commit-messages)
so that the issue is automatically closed when your code is merged. Zulip's
preferred style for this is to have the final paragraph of the commit message
read, e.g., "Fixes: \#123."

**Note:** Avoid using a phrase like `Partially fixes #1234`, as GitHub's regular
expressions ignore the "partially" and close the issue. `Fixes part of #1234` is
a good alternative.

There are a few specific formatting guidelines to keep in mind:

- The commit description should be separated from the summary by a blank line.
- Use full sentences and paragraphs, with proper punctuation and capitalization.
  Paragraphs should be separated with a single blank line.
- Be sure to review your description for typos, spelling, and grammar mistakes.
- Your commit message should be line-wrapped to about 68 characters per line,
  but no more than 70, so that your commit message will be easy to read in `git
log` in a normal terminal.

**Tip:** You may find it helpful to configure Git to use your preferred editor
using the `EDITOR` environment variable or `git config --global core.editor`,
and configure the editor to automatically wrap text to 70 or fewer columns per
line (all text editors support this).

### Examples of good commit messages

- [A backend testing
  commit](https://github.com/zulip/zulip/commit/4869e1b0b2bc6d56fcf44b7d0e36ca20f45d0521)
- [A development environment provisioning
  commit](https://github.com/zulip/zulip/commit/cd5b38f5d8bdcc1771ad794f37262a61843c56c0)
