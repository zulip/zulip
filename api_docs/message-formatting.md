# Message formatting

Zulip supports an extended version of Markdown for messages, as well as
some HTML level special behavior. The Zulip help center article on [message
formatting](/help/format-your-message-using-markdown) is the primary
documentation for Zulip's markup features. This article is currently a
changelog for updates to these features.

The [render a message](/api/render-message) endpoint can be used to get
the current HTML version of any Markdown syntax for message content.

## Code blocks

**Changes**: As of Zulip 4.0 (feature level 33), [code blocks][help-code]
can have a `data-code-language` attribute attached to the outer HTML
`div` element, which records the programming language that was selected
for syntax highlighting. This field is used in the
[playgrounds][help-playgrounds] feature for code blocks.

## Global times

**Changes**: In Zulip 3.0 (feature level 8), added [global time
mentions][help-global-time] to supported Markdown message formatting
features.

## Mentions

**Changes**: In Zulip 9.0 (feature level 247), `channel` was added
to the supported [wildcard][help-mention-all] options used in the
[mentions][help-mentions] Markdown message formatting feature.

## Spoilers

**Changes**: In Zulip 3.0 (feature level 15), added
[spoilers][help-spoilers] to supported Markdown message formatting
features.

## Removed features

**Changes**: In Zulip 4.0 (feature level 24), the rarely used `!avatar()`
and `!gravatar()` markup syntax, which was never documented and had an
inconsistent syntax, were removed.

## Related articles

* [Markdown formatting](/help/format-your-message-using-markdown)
* [Send a message](/api/send-message)
* [Render a message](/api/render-message)

[help-code]: /help/code-blocks
[help-playgrounds]: /help/code-blocks#code-playgrounds
[help-spoilers]: /help/spoilers
[help-global-time]: /help/global-times
[help-mentions]: /help/mention-a-user-or-group
[help-mention-all]: /help/mention-a-user-or-group#mention-everyone-on-a-stream
