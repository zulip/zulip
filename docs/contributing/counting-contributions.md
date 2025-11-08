# Counting contributions

The [Zulip team page](https://zulip.com/team/) displays commit counts for
contributors to Zulip projects. We display these statistics prominently because
they are easy to compute, and can be fun and motivating for some of our
contributors.

We do not consider commit count to be a good way to measure someone's
contributions to a software project. Many invaluable contributions may not
result in the contributor authoring any code at all, including design, feedback,
translations, bug reports, helping new contributors, and other types of
participation in our [development community][dev-community]. These non-code
contributions are essential to making the Zulip project successful.

Thus, Zulip's policy is to always express appreciation for non-code
contributions to the project whenever we discuss code contribution
statistics, especially in our highest-visibility contexts like release
blog posts.

## How the contribution stats are calculated

The data for all contributors to the Zulip project is aggregated by
querying [GitHub's API endpoint for listing a repository's
contributors][github-list-contrib-endpoint]. The numbers Zulip gets
from this endpoint differs slightly from the data GitHub displays in a
repository's [contributors page][github-contrib-page]. This
discrepancy is due to the following reasons:

- A repository's contributors page excludes commits with author email
  addresses that do not have an associated GitHub account. However,
  the GitHub API counts such emails in its contributor stats.
- A repository's contributors page does not count commits authored by
  email addresses that have been deleted from a GitHub profile by the
  user. However, the GitHub API treats these stale emails as
  contributors as well.
- Some commits have multiple authors when that is declared via
  [Co-Authored-By][co-authored-by] in a commit message.

## Old email addresses

If you remove an email address from your GitHub profile, the commits
you contributed with that email as the `GIT_AUTHOR_EMAIL` will
disappear from your GitHub profile. If you made contributions to Zulip
with an author email address that is no longer associated with your
GitHub profile, here are some important points to keep in mind:

- Zulip's team page will still display your contributions. These
  contributions will be grouped under the email that was used for the
  commits, but will not link to your GitHub profile.
- If you still have access to the email used for the contributions, you
  can link the contributions to your GitHub profile by
  [adding the email to your GitHub account][github-add-email].
- If you do not have access to the email in question, you can ask for
  help on chat.zulip.org, or submit a pull request editing the
  `.mailmap` file at the root of the repository where your
  contributed.

The comments at the top of our `.mailmap` files document how to map
your old email address to one currently associated with your GitHub
account.

## Relevant source code

To dig deeper into how the contributor stats are calculated, please check
out the following files in the [Zulip server repository][server-repo]:

- `tools/fetch-contributor-data` - The script that fetches contributor
  data from GitHub's API.
- `static/js/portico/team.js` - The JavaScript code that processes and
  renders the data received from GitHub.

## Attribution for non-code contributions

As noted above, Zulip's policy is to express appreciation for non-code
contributions to the project whenever we discuss code contribution
statistics.

We do not specifically attribute non-code contributions by name, because the
logistics of giving individual attributions in a consistent and fair way across
50+ features in a release are far more than we have the capacity to manage.

For context, a significant feature usually involves a half-dozen people or more
helping with different parts of the work (suggesting ideas, providing technical
and non-technical feedback, etc.). Contributions can range from multiple rounds
of PR reviews to a 👍 reaction on someone else's suggestion. Even if one could
review everything that happened (in itself a daunting task), it may not be clear
which contributions should "count". At the same time, seeing that your name is
missing from a list of attributions where it belongs can feel really hurtful.

So, while we cannot thank everyone by name, please know that your contributions
are deeply appreciated!

[github-list-contrib-endpoint]: https://docs.github.com/en/rest/reference/repos#list-repository-contributors
[github-contrib-page]: https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-a-projects-contributors
[dev-community]: https://zulip.com/development-community/
[server-repo]: https://github.com/zulip/zulip
[github-add-email]: https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-user-account/managing-email-preferences/adding-an-email-address-to-your-github-account
[co-authored-by]: https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors
