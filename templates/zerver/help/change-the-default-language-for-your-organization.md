# Configure organization notifications language

{!admin-only.md!}

Zulip has been translated or partially translated into dozens of
languages. You can see which languages Zulip supports, and help add
support for new languages on **[Transifex](https://www.transifex.com/zulip/zulip/)**.

Each user can use Zulip with [their preferred
language](/help/change-your-language). In addition, if your
organization has a primary language other than American English, you
can set the notifications language for the organization. This setting:

* Determines the language used for automated messages sent to streams
  by [Notification
  Bot](/help/configure-notification-bot). (Notifications sent to a
  single user will use that user's language).
* Determines the language used for outgoing
  [invitation emails](/help/invite-new-users).
* Is used as the default language for new user accounts when Zulip
  cannot detect their language preferences from their browser,
  including all users [created via the Zulip API][api-create-user].

### Configure the organization notifications language

{start_tabs}

{settings_tab|organization-settings}

2. Under **Notifications**, change the **Notifications language**.

{!save-changes.md!}

{end_tabs}

[api-create-user]: https://zulip.com/api/create-user
