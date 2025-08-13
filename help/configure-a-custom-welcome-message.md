# Configure a custom welcome message

You can configure a custom welcome message to be sent to new users in your
organization, along with standard onboarding messages from Welcome Bot. For
example, you can describe the purpose of important channels, and link to your
organization's guidelines for using Zulip.

Administrators can also customize the message each time they [create an
invitation](/help/invite-new-users). Invitations sent by other users will always
use the default custom welcome message configured by your organization's
administrators.

!!! tip ""

    You can compose the welcome message in the compose box to benefit from
    buttons and typeahead suggestions for message formatting, and copy it over.


## Configure a default custom welcome message

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Onboarding**, enable **Send a custom Welcome Bot message to
   new users**.

1. Under **Message text**, enter a custom welcome message using Zulip's standard
   [Markdown formatting](/help/format-your-message-using-markdown).

1. *(optional)* Click **Send me a test message**, followed by **View message**,
   to see how the message will look. Follow the instructions above to return to
   the panel where this setting can be configured.

{!save-changes.md!}

{end_tabs}

## Customize the welcome message when sending an invitation

{!admin-only.md!}

{start_tabs}

{!invite-users.md!}

1. If there is no custom message configured in your organization, enable **Send
   a custom Welcome Bot message**. Otherwise, disable **Send the default Welcome
   Bot message configured for this organization**.

1. Under **Message text**, enter the welcome message to use for this
   invitation using Zulip's standard [Markdown
   formatting](/help/format-your-message-using-markdown).

1. Configure other invitation details as desired, and click **Invite** or
   **Create link**.

{end_tabs}

## Related articles

* [Invite new users](/help/invite-new-users)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Configure default new user settings](/help/configure-default-new-user-settings)
* [Joining a Zulip organization](/help/join-a-zulip-organization)
