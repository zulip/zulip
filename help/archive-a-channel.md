# Archive a channel

{!admin-only.md!}

You can archive channels you no longer plan to use. Archiving a channel:

- Removes it from the left sidebar for all users.
- Prevents new messages from being sent to the channel.
- Prevents messages in the channel from being edited, deleted, or moved.

Archiving a channel does not remove subscribers, or change who can access it.
Messages in archived channels still appear in [search
results](/help/search-for-messages), the [combined feed](/help/combined-feed),
and [recent conversations](/help/recent-conversations).

To hide the content in a channel, you can make it
[private](/help/change-the-privacy-of-a-channel) and [unsubscribe
users](/help/manage-user-channel-subscriptions) from it prior to archiving.

## Archive a channel

!!! warn ""

    Channels can be [unarchived](#unarchiving-archived-channels) only by
    [contacting support](/help/contact-support) for organizations hosted
    on Zulip Cloud, or by your self-hosted server's administrator.

{start_tabs}

{tab|desktop-web}

{relative|channel|all}

1. Select a channel.

1. Click the **archive** (<i class="zulip-icon zulip-icon-archive"></i>) icon
   in the upper right corner of the channel settings panel.

1. Approve by clicking **Confirm**.

!!! tip ""

    You can also hover over a channel in the left sidebar, click on the
    **ellipsis** (<i class="zulip-icon zulip-icon-more-vertical"></i>), and
    select **Channel settings** to access settings for the channel.

{end_tabs}

## Unarchiving archived channels

Zulip Cloud organizations that need to unarchive a channel can [contact Zulip
support](/help/contact-support).

If you are self-hosting, you can unarchive an archived channel using the
`unarchive_channel` [management command][management-command]. This will restore
it as a private channel with shared history, and subscribe all organization
owners to it.

[management-command]:
https://zulip.readthedocs.io/en/latest/production/management-commands.html#other-useful-manage-py-commands

## Related articles

* [Edit a message](/help/edit-a-message)
* [Delete a message](/help/delete-a-message)
* [Delete a topic](/help/delete-a-topic)
* [Message retention policy](/help/message-retention-policy)
* [Channel permissions](/help/channel-permissions)
