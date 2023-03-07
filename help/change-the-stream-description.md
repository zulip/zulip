# Change the stream description

{!admin-only.md!}

Streams descriptions are displayed when viewing the stream in the
web and desktop apps, and can be used to explain the purpose of a
stream and link to usage guidelines, resources, or related streams.

Stream descriptions support Zulip's standard [Markdown
formatting][markdown-formatting], with the exception that image
previews are disabled.

{start_tabs}

{relative|stream|all}

1. Select a stream.

{!select-stream-view-general.md!}

1. Click the **pencil** (<i class="fa fa-pencil"></i>)
   to the right of the stream name. Enter a new description.

{!save-changes.md!}

!!! tip ""
    Use [Markdown formatting][markdown-formatting] to include a link to a
    website, Zulip [message][message-link], or [topic][topic-link] in the
    stream description: `[link text](URL)`.

{end_tabs}

{!automated-notice-stream-event.md!}

[markdown-formatting]: /help/format-your-message-using-markdown
[message-link]: /help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message
[topic-link]:
    /help/link-to-a-message-or-conversation#get-a-link-to-a-specific-topic
