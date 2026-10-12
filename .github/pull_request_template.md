<!--
  Describe your pull request here.
  Do not copy and paste from your LLM. Use your own words.
  Pro tip: If you didn't feel like writing it, no one else
  will feel like reading it.
-->

<!--
  These two elements, Fixes and CZO Discussion, are required.

  Do not open a pull request if you have not been involved in
  a discussion of the work it represents on CZO first.
-->

Fixes: <!-- Issue number, e.g., #4321-->
CZO Discussion: <!-- Link to chat.zulip.org discussion. -->

**How changes were manually tested:**
<!--
  You must do manual testing of your work beyond the suite
  of automated tests. Describe your testing environment and
  the exact steps you took to manually test your work:
-->

- Browsers/platforms tested on: <!-- E.g., Firefox on Windows 11 -->
- Steps for reviewers to reproduce your manual tests:

**Screenshots and screen captures:**

<!--
  If your PR in any way affects the user interface, you must
  include screenshots. Even if there are no changes as a result
  of your code, you must demonstrate there *are* no changes in
  the areas your code affects.
  Detailed guide: https://zulip.readthedocs.io/en/latest/contributing/presenting-visual-changes.html
-->

<details>
<summary>Self-review checklist</summary>

<!-- Prior to submitting a PR, follow our step-by-step guide to review your own code:
https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#how-to-review-code -->

<!-- Once you create the PR, check off all the steps below that you have completed.
If any of these steps are not relevant or not completed, leave them unchecked.-->

- [ ] [Self-reviewed](https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html#how-to-review-code) the changes for clarity and maintainability
      (variable names, code reuse, readability, etc.).
- [ ] Followed the [AI use policy](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#ai-use-policy-and-guidelines).

Communicate decisions, questions, and potential concerns.

- [ ] Points to a recent discussion on chat.zulip.org in which you participated.
- [ ] Explains differences from previous plans (e.g., issue description).
- [ ] Highlights technical choices and bugs encountered.
- [ ] Calls out remaining decisions and concerns.
- [ ] Automated tests verify logic where appropriate.

Individual commits are ready for review (see [commit discipline](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html)).

- [ ] Each commit is a coherent idea.
- [ ] Commit message(s) explain reasoning and motivation for changes.
- [ ] Each commit message follows [Zulip's style](https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html#commit-messages)

Completed manual review and testing of the following:

- [ ] Visual appearance of the changes.
- [ ] Responsiveness and internationalization.
- [ ] Strings and tooltips.
- [ ] End-to-end functionality of buttons, interactions and flows.
- [ ] Corner cases, error conditions, and easily imagined bugs.

Completed necessary follow-ups:

- [ ] Updated chat.zulip.org discussion with your PR number

</details>
