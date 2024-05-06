# Configure default settings for new users

{!admin-only.md!}

Organization administrators can configure the default values of
personal preference settings for new users joining the
organization. This can help seamlessly customize the Zulip experience
to match how the organization in question is using Zulip.

Existing users' preferences cannot be modified by administrators, and
users will be able to customize their own settings once they
join. Administrators can customize defaults for all personal
preference settings, including the following:

* Privacy settings:
    * Displaying [availability](/help/status-and-availability) to other users
    * Allowing others to see when the user has [read
      messages](/help/read-receipts)
    * Allowing others to see when the user is [typing a
      message](/help/typing-notifications)

* Preferences:
    * [Language](/help/change-your-language)
    * [Time format](/help/change-the-time-format)
    * [Light theme vs. dark theme](/help/dark-theme)
    * [Emoji theme](/help/emoji-and-emoticons#change-your-emoji-set)
    * [Home view](/help/configure-home-view)
      ([Inbox](/help/inbox) vs.
      [Recent conversations](/help/recent-conversations) vs.
      [Combined feed](/help/reading-strategies#combined-feed))

* Notification settings:
    * What types of messages [trigger notifications][default-notifications]
    * Which topics users will [automatically follow](/help/follow-a-topic). This
      minimizes the need to [mention](/help/mention-a-user-or-group) other users
      to get their attention.

[default-notifications]: /help/channel-notifications#configure-default-notifications-for-all-channels

## Configure default settings for new users

{start_tabs}

{settings_tab|default-user-settings}

1. Review all settings and adjust as needed.

{end_tabs}

## Configure default language for new users

Your organization's [language](/help/configure-organization-language) will be
the default language for new users when Zulip cannot detect their language
preferences from their browser, including all users [created via the Zulip
API](/api/create-user).

{start_tabs}

{settings_tab|organization-settings}

1. Under **Automated messages and emails**, change the **Language for
   automated messages and invitation emails**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Setting up your organization](/help/getting-your-organization-started-with-zulip)
* [Customize settings for new users](/help/customize-settings-for-new-users)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Invite users to join](/help/invite-users-to-join)
