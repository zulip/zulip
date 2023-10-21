# Archive a stream

{!admin-only.md!}

Archiving a stream will immediately unsubscribe all users from the stream,
remove the stream from search and other typeaheads, and remove the stream's
messages from **All messages**.

Archiving a stream does not delete a stream's messages. Users will still be
able to find any given message by searching for it. However, links to
messages and topics in the stream may or may not continue to work.

In most cases, we recommend [renaming streams](/help/rename-a-stream) rather
than archiving them.

## Archive a stream

{start_tabs}

{tab|desktop-web}

{relative|stream|all}

1. Select a stream.

1. Click the **trash** <i class="fa fa-trash-o"></i> icon near the top right
   corner of the stream settings panel.

1. Approve by clicking **Confirm**.

!!! tip ""

    You can also hover over a stream in the left sidebar, click on the
    **ellipsis** (<i class="zulip-icon zulip-icon-more-vertical"></i>), and
    select **Stream settings** to access the **trash**
    <i class="fa fa-trash-o"></i> icon.

{end_tabs}

!!! warn ""

    Archiving a stream is currently irreversible via the UI.

## Unarchiving archived streams

If you are self-hosting, you can unarchive an archived stream using the
`unarchive_stream` [management command][management-command]. This will restore
it as a private stream with shared history, and subscribe all organization
owners to it. If you are using Zulip Cloud, you can [contact us](/help/contact-support)
for help.

[management-command]:
https://zulip.readthedocs.io/en/latest/production/management-commands.html#other-useful-manage-py-commands

## Related articles

* [Edit a message](/help/edit-a-message)
* [Delete a message](/help/delete-a-message)
* [Delete a topic](/help/delete-a-topic)
* [Message retention policy](/help/message-retention-policy)
* [Stream permissions](/help/stream-permissions)
* [Zulip Cloud or self-hosting?](/help/zulip-cloud-or-self-hosting)
