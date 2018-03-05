# Using zulipbot

Zulip uses [@zulipbot](https://github.com/zulipbot), a GitHub workflow bot
deployed on all Zulip repositories, to handle issues and pull requests in our
repositories in order to create a better workflow for Zulip contributors.

Its purpose is to work around various limitations in GitHub's
permissions and notifications systems to make it possible to have a
much more democractic workflow for our contributors.  It allows anyone
to self-assign or label an issue, not just the core contributors
trusted with full write access to the repository (which is the only
model GitHub supports).

## Usage

* **Claim an issue** — Comment `@zulipbot claim` on the issue you want
to claim; **@zulipbot** will assign you to the issue and label the issue as
**in progress**.

    * If you're a new contributor, **@zulipbot** will give you read-only
    collaborator access to the repository and leave a welcome message on the
    issue you claimed.

    * You can also claim an issue that you've opened by including
    `@zulipbot claim` in the body of your issue.

    * If you accidentally claim an issue you didn't want to claim, comment
    `@zulipbot abandon` to abandon an issue.

* **Label your issues** — Add appropriate labels to issues that you opened by
including `@zulipbot label` in an issue comment or the body of your issue
followed by the desired labels enclosed within double quotes (`""`).

    * For example, to add the **bug** and **help wanted** labels to your
    issue, comment or include `@zulipbot label "bug" "help wanted"` in the
    issue body.

    * You'll receive an error message if you try to add any labels to your issue
    that don't exist in your repository.

    * If you accidentally added the wrong labels, you can remove them by commenting
    `@zulipbot remove` followed by the desired labels enclosed with double quotes
    (`""`).

* **Find unclaimed issues** — Use the [GitHub search
feature](https://help.github.com/articles/using-search-to-filter-issues-and-pull-requests/)
to find unclaimed issues by adding one of the following filters to your search:

    * `-label: "in progress"` (excludes issues labeled with the **in progress** label)

    * `no:assignee` (shows issues without assignees)

    Issues labeled with the **in progress** label and/or assigned to other users have
    already been claimed.

* **Collaborate in area label teams** — Receive notifications on
issues and pull requests within your fields of expertise on the
[Zulip server repository](https://github.com/zulip/zulip) by joining
the Zulip server
[area label teams](https://github.com/orgs/zulip/teams?utf8=✓&query=Server)
(Note: this link only works for members of the Zulip organization;
we'll happily add you if you're interested).  These teams correspond
to the repository's
[area labels](https://github.com/zulip/zulip/labels), although some
teams are associated with multiple labels; for example, the **area:
message-editing** and **area: message view** labels are both related
to the
[Server message view](https://github.com/orgs/zulip/teams/server-message-view)
team.  Feel free to join as many area label teams as as you'd like!

    After your request to join an area label team is approved, you'll receive
    notifications for any issues labeled with the team's corresponding area
    label as well as any pull requests that reference issues labeled with your
    team's area label.

* **Track inactive claimed issues** — If a claimed issue has not been updated
for a week, **@zulipbot** will post a comment on the inactive issue to ask the
assignee(s) if they are still working on the issue.

    If you see this comment on an issue you claimed, you should post a comment
    on the issue to notify **@zulipbot** that you're still working on it.

    If **@zulipbot** does not receive a response from the assignee within 3 days
    of an inactive issue prompt, **@zulipbot** will automatically remove the
    issue's current assignee(s) and the "in progress" label to allow others to
    work on an inactive issue.

* **Receive Travis build status notifications** — If you would like to receive
a notification whenever the build status of your pull request is updated, label
your pull request with the "travis updates" label using the command `@zulipbot
label "travis updates"`, and **@zulipbot** will let you know the build status
(e.g. passed, failed, errored) of your pull request once all tests finish.

### Contributing

If you wish to help develop and contribute to **@zulipbot**, check out the
[zulip/zulipbot](https://github.com/zulip/zulipbot) repository on GitHub and read
the project's [contributing
guidelines](https://github.com/zulip/zulipbot/blob/master/.github/CONTRIBUTING.md) for
more information.
