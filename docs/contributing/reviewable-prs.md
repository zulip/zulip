# Submitting a pull request

A pull request (PR) is a presentation of your proposed changes to Zulip. Your aim
should be to explain your changes as clearly as possible. This will help
reviewers evaluate whether the proposed changes are correct, and address any
open questions. Clear communication helps the whole Zulip project move more
quickly by saving maintainers time when they review your code. It will also make
a big difference for getting your work integrated without delay.

You will go through the following steps to prepare your work for review. Each
step is described in detail below, with links to additional resources:

1. Write your code [with clarity in mind](#write-clear-code).
1. [Organize your proposed changes](#organize-your-proposed-changes) into a
   series of commits that tell the story of how the codebase will change.
1. [Explain your changes](#explain-your-changes) in the description for your
   pull request, including [screenshots](#demonstrating-visual-changes) for
   visual changes.
1. Carefully [review your own work](#review-your-own-work).
1. [Submit your pull request](#submit-your-pull-request-for-review) for review.

See the [pull request review process](../contributing/review-process.md) guide
for a detailed overview of what happens once your pull request is submitted.

## Write clear code

When you write code, you should make sure that you understand _why it works_ as
intended. This is the foundation for being able to explain your proposed changes
to others.

Zulip’s coding philosophy is to focus relentlessly on making the codebase easy
to understand and difficult to make dangerous mistakes. Our linters, tests, code
style guidelines, [testing philosophy](../testing/philosophy.md), [commit
discipline](../contributing/commit-discipline.md), this documentation, and our
attention to detail in [code review](../contributing/review-process.md) are all
important elements of this strategy. Following these guidelines is essential if
you'd like your work to be merged into the project.

If any part of your contribution is from someone else (code snippets, images,
sounds, or any other copyrightable work, modified or unmodified), be sure to
review the instructions on how to [properly attribute](./licensing.md) the work.

## Organize your proposed changes

The changes you submit will be organized into a series of commits. A PR might
contain a single commit, or a dozen or more, depending on the changes being
made.

Commits help you tell the story of how each change you are proposing is
necessary or helpful. If you were presenting your changes, a commit might be a
slide in your presentation. As a rough guideline, a good commit usually has less
than 100 lines of code changes. If you can see a way to split a commit into
different pieces of meaning, you should split it.

Keep in mind that you are presenting your final work product, _not_ the path you
took to get there. You should never have a commit that can be described as
fixing a mistake in an earlier commit in the same PR; use `git rebase -i` to fix
the mistake in the original commit.

See the [commit discipline guide](../contributing/commit-discipline.md) for more
details on how to structure your commits, and guidelines on how to write good
commit messages. Your pull request can only be reviewed once you've followed
these guidelines to the best of your ability. This makes it much easier for
reviewers to understand your work and identify any problems.

Ideally, when reviewing a pull request for a complex project, Zulip's
maintainers should be able to verify and merge the first few commits, and leave
comments on the rest. It is by far the most efficient way to do collaborative
development, since one is constantly making progress, we keep branches small,
and reviewers don't end up repeatedly going over the earlier parts of a pull
request.

## Explain your changes

By the time you are submitting your pull request, you should already have put a
lot of thought into how to organize and present your proposed changes. In the
description for your pull request, you will:

- Provide an overview of your changes.
- Note any differences from prior plans (e.g., from the description of the issue you
  are solving).
- Call out any open questions, concerns, or decisions you are uncertain about.
  The review process will go a lot more smoothly if points of uncertainty are
  explicitly laid out.
- Include screenshots for all visual changes, so that they can be reviewed
  without running your code. See [below](#demonstrating-visual-changes) for
  detailed instructions.

If you have a question about a specific part of your code that you expect to be
resolved during the review process, put it in a PR comment attached to a
relevant part of the changes.

Take advantage of [GitHub's formatting][github-syntax] to make your pull request
description and comments easy to read.

### Discussions in the development community

Any questions for which broader feedback or visibility is helpful are discussed
in the [Zulip development community](https://zulip.com/development-community/).

If there has been a conversation in the [Zulip development
community][zulip-dev-community] about the changes you've made or the issue your
pull request addresses, please cross-link between your pull request and those
conversations in both directions. This provides helpful context for maintainers
and reviewers. Specifically, it's best to link from your pull request [to a
specific message][link-to-message], as these links will still work even if the
topic of the conversation is renamed, moved or resolved.

Once you've created a pull request on GitHub, you can use one of the [custom
linkifiers][dev-community-linkifiers] in the development community to easily
link to your pull request from the relevant conversation.

## Review your own work

Before requesting a review for your pull request, follow our [review
guide](./code-reviewing.md#reviewing-your-own-code) to carefully review and test
your own work. You can often find things you missed by taking a step back to
look over your work before asking others to do so. Catching mistakes yourself
will help your PRs be merged faster, and reviewers will appreciate the quality
and professionalism of your work.

The pull request template in the `zulip/zulip` repository has a checklist of
reminders for points you need to cover in your review. Make sure that all the
relevant items on the self-review checklist have been addressed.

## Submit your pull request for review

If you are new to Git, see our guide on [making a pull
request](../git/pull-requests.md) for detailed technical instructions on how to
submit a pull request.

When submitting your PR, you will need to make sure that the pull request passes
all CI tests. You can sometimes request initial feedback if there are open
questions that will impact how you update the tests. But in general,
maintainers will wait for your PR to pass tests before reviewing your work.

If your PR was not ready for review when you first posted it (e.g., because it
was failing tests, or you weren't done working through the self-review
checklist), notify maintainers when you'd like them to take a look by posting a
clear comment on the main GitHub thread for your PR with details on any changes
from the original version; this is very helpful for any maintainers who already
read the draft PR.

## Draft pull requests

If it helps your workflow, you can submit your pull request marked as
a [draft][github-help-draft-pr] while you're still working on it. When ready for
review:

1. Make sure your PR is no longer marked as a [draft][github-help-draft-pr], and
   doesn't have "WIP" in the title.

1. Post a quick "Ready for review!" comment on the main GitHub thread for your
   PR.

[github-help-draft-pr]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests

## Demonstrating visual changes

- For [screenshots or screencasts][screenshots-gifs] of changes,
  putting them in details/summary tags reduces visual clutter
  and scroll length of pull request comments. This is especially
  useful when you have several screenshots and/or screencasts to
  include in your comment as you can put each image, or group of
  images, in separate details/summary tags.

  ```
  <details>
  <summary>Descriptive summary of image</summary>

  ![uploaded-image](uploaded-file-information)
  </details>
  ```

- Screencasts are difficult to review, so use them only when necessary to
  demonstrate an interaction. Keep videos as short as possible. If your changes
  can be seen on a screenshot, be sure to include screenshots in addition to any
  videos.

- For before and after images or videos of changes, using GithHub's table
  syntax renders them side-by-side for quick and clear comparison.
  While this works well for narrow or small images, it can be hard to
  see details in large, full screen images and videos in this format.

  Note that you can put the table syntax inside the details/summary
  tags described above as well.

  ```
  ### Descriptive header for images:
  | Before | After |
  | --- | --- |
  | ![image-before](uploaded-file-information) | ![image-after](uploaded-file-information)
  ```

- If you've updated existing documentation in your pull request,
  include a link to the current documentation above the screenshot
  of the updates. That way a reviewer can quickly access the current
  documentation while reviewing your changes.

  ```
  [Current documentation](link-to-current-documentation-page)
  ![image-after](uploaded-file-information)
  ```

- For updates or changes to CSS class rules, it's a good practice
  to include the results of a [git-grep][git-grep] search for
  the class name(s) to confirm that you've tested all the impacted
  areas of the UI and/or documentation.

  ```console
  $ git grep '.example-class-name' web/templates/ templates/
  templates/corporate/...
  templates/zerver/...
  web/templates/...
  ```

[github-syntax]: https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax
[git-grep]: https://git-scm.com/docs/git-grep
[screenshots-gifs]: ../tutorials/screenshot-and-gif-software.md
[zulip-dev-community]: https://chat.zulip.org
[link-to-message]: https://zulip.com/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message
[dev-community-linkifiers]: https://zulip.com/development-community/#linking-to-github-issues-and-pull-requests
