# Reviewable pull requests

This page offers some tips for making your pull requests easy to review.
Following this advice will help the whole Zulip project move more quickly by
saving maintainers time when they review your code. It will also make a big
difference for getting your work integrated without delay. For a detailed
overview of Zulip's PR review process, see the [pull request review
process](../contributing/review-process.md) guide.

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

- When you update your pull request after addressing a round of review feedback,
  be clear about which issues you've resolved (and how!).

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
the earlier parts of a pull request.

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

## Tips and best practices

When writing comments for pull requests, it's good to be familiar with
[GitHub's basic formatting syntax][github-syntax]. Here are some additional
tips and best practices that Zulip contributors and maintainers have found
helpful for writing clear and thorough pull request comments:

- If there has been a conversation in the [Zulip development
  community][zulip-dev-community] about the changes you've made or the issue
  your pull request addresses, please cross-link between your pull request and
  those conversations. This provides helpful context for maintainers and
  reviewers. Specifically, it's best to link from your pull request [to a
  specific message][link-to-message], as these links will still work even if the
  topic of the conversation is renamed, moved or resolved.

  Once you've created a pull request on GitHub, you can use one of the [custom
  linkifiers][dev-community-linkifiers] in the development community to easily
  link to your pull request from the relevant conversation.

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
