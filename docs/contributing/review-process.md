# Pull request review process

Pull requests submitted to Zulip go through a rigorous review process, which is
designed to ensure that we are building a high-quality product with a
maintainable codebase. This page describes the stages of review your pull
request may go through, and offers guidance on how you can help keep your pull
request moving along.

## Labels for managing the stages of pull request review

In the Zulip server/web app repository
([`zulip/zulip`](https://github.com/zulip/zulip/)), we use GitHub labels to help
everyone understand where a pull request is in the review process. These labels
are noted below, alongside their corresponding pull-request stage. Each label is
removed by the reviewer for that stage when they have no more feedback on the PR
and consider it ready for the next stage of review.

Sometimes, a label may also be removed because significant changes by
the contributor are required before the PR ready to be reviewed again. In that
case, the contributor should post a comment mentioning the reviewer when the
changes have been completed, unless the reviewer requested some other action.

## Stages of a pull request review

This section describes the stages of the pull request review process. Each stage
may require several rounds of iteration. Don't feel daunted! Not every PR will
require all the stages described, and the process often goes quite quickly for
smaller changes that are clearly explained.

1. **Product review.** Oftentimes, seeing an initial implementation will make it
   clear that the product design for a feature needs to be revised, or that
   additional changes are needed. The reviewer may therefore ask you to amend or
   change the implementation. Some changes may be blockers for getting the PR
   merged, while others may be improvements that can happen afterwards. Feel
   free to ask if it's unclear which type of feedback you're getting.
   (Follow-ups can be a great next issue to work on!)

   Your PR might be assigned the [product
   review](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22product+review%22)
   label at this stage, or later in the review process as questions come up. You
   can also add this label yourself if appropriate. If doing so, be sure to
   clearly outline the product questions that need to be addressed.

2. **QA.** If your PR makes user-facing changes, it may get a round of testing
   without reference to the code. You will get feedback on any user-facing bugs
   in the implementation. To minimize the number of review round-trips, make
   sure to [thoroughly test](../contributing/code-reviewing.md#manual-testing)
   your own PR prior to asking for review.

   Your PR might be assigned the [QA
   needed](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22QA+needed%22)
   label at this stage, or later on if re-testing is required.

3. **Initial code review.** All PRs will go through one or more rounds of code
   review. Your code may initially be [reviewed by other
   contributors](../contributing/code-reviewing.md). This helps us make good use
   of project maintainers' time, and helps you make progress on the PR by
   getting quick feedback. A project maintainer may leave a comment asking
   someone with expertise in the area you're working on to review your work.

4. **Maintainer code review.** In this phase, a Zulip maintainer will do a
   thorough review of your proposed code changes. Your PR may be assigned the
   [maintainer
   review](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22maintainer+review%22)
   label at this stage.

5. **Documentation review.** If your PR includes documentation changes, those
   changes will require review. This generally happens fairly late in the review
   process, once the UI and the code are unlikely to undergo major changes.
   Maintainers may indicate that a PR is ready for documentation review by
   adding a [help center
   review](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22help+center+review%22)
   and/or [api docs
   review](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22api+docs+review%22)
   label, and mentioning a documentation maintainer in the comments.

6. **Integration review**. This is the final round of the review process,
   generally done by `@timabbott` for server and web app PRs. A maintainer will
   usually assign the [integration
   review](https://github.com/zulip/zulip/pulls?q=is%3Aopen+is%3Apr+label%3A%22integration+review%22)
   label when the PR is ready for this phase.

## How to help move the review process forward

If there are no comments on your PR for a week after you submit it, you can
check again to make sure that it's ready for review, and then post a quick
comment to remind Zulip's maintainers to take a look at your work. Consider also
[asking for a
review](../contributing/code-reviewing.md#asking-for-a-code-review) in the Zulip
development community.

After that, the key to keeping your review moving through the review process is to:

- Address _all_ the feedback to the best of your ability.
- Make it clear when the requested changes have been made
  and you believe it's time for another look.
- Make it as easy as possible to review the changes you made.

In order to do this, when you believe you have addressed the previous round of
feedback on your PR as best you can, post a comment asking reviewers to take
another look. Your comment should make it easy to understand what has been done
and what remains by:

- Summarizing the changes made since the last review you received. Be clear
  about which issues you've resolved (and how!).
- Highlighting remaining questions or decisions, with links to any relevant
  threads in the [Zulip development
  community](https://zulip.com/development-community/). It should be clear which
  feedback you _haven't_ addressed yet.
- Providing updated screenshots and information on manual testing if
  appropriate.

The easier it is to review your work, the more likely you are to receive quick
feedback.
