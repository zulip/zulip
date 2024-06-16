# Organization language for automated messages and invitation emails

{!admin-only.md!}

{!translation-project-info.md!}

Each user can use Zulip with [their preferred language][user-lang].
Additionally, if your organization has a primary language other than
American English, you can set the language used for the organization's
automated messages and invitation emails. This setting:

* Determines the language used for [automated
  notices](/help/configure-automated-notices) that are sent to channels, including
  both the topic name and message content. (Automated messages sent to a single
  user will use that user's preferred language).

* Determines the language used for outgoing
  [invitation emails](/help/invite-new-users).

* Is used as the default language for new user accounts when Zulip
  cannot detect their language preferences from their browser,
  including all users [created via the Zulip API][api-create-user].

## Configure the organization language

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, change the **Language for
   automated messages and invitation emails**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Change your language][user-lang]
* [Configure multi-language search](/help/configure-multi-language-search)
* [Configure default settings for new users](/help/configure-default-new-user-settings)
* [Configure automated notices](/help/configure-automated-notices)

[api-create-user]: https://zulip.com/api/create-user
[user-lang]: /help/change-your-language
