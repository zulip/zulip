# Format your message using Markdown

Zulip uses a variant of
[GitHub Flavored Markdown](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet#tables)
(GFM) to allow you to easily format your messages.

## Summary

To see a summary of message formatting in Zulip, click the A (<i
class="icon-vector-font"></i>) icon located in the bottom left corner of
your messaging box. You can alternatively click the cog (<i
class="icon-vector-cog"></i>) icon in the top right corner of the right
sidebar and choose **Message formatting** from the dropdown menu that
appears.

![Message formatting modal](/static/images/help/message-formatting-summary.png)

## Emphasis

You can surround your text with a combination of asterisks `*` and
tildes `~` to emphasize words or phrases in your messages.

### Italics

For italics, surround your text with `*asterisks*`.

![Italicized text](/static/images/help/italics-screenshot.png)

### Bold

For bold text, surround your text with `**two asterisks**`.

![Bold text](/static/images/help/bold-screenshot.png)

### Strikethrough

For strikethrough text, surround your text with `~~two tildes~~`.

![Strikethrough text](/static/images/help/strikethrough-screenshot.png)

### Extra emphasis

To add more variety, flavor, and emphasis to your messages, you can
combine different styles of formatting.

![Extra emphasized text](/static/images/help/extra-emphasis-screenshot.png)

## Links

To include hyperlinks in your messages, you can either enter the
link's URL address directly or surround the link's display text
with`[brackets]` and the URL address of the link in `(parentheses)`
immediately after.

![Link](/static/images/help/link-screenshot.png)

Zulip currently does not support image embedding through links.

## Stream Links

To link to another stream in one of your messages, you can either type
`#streamName` and click the stream name in the popup, or you can start
with `#` and surround your message with double asteriks `**`.

![Stream Links](/static/images/help/stream-link-screenshot.png)

## Lists

Begin each item in your list with `* an asterisk followed by a space`
to include lists in your messages.

![Lists](/static/images/help/lists-screenshot.png)

!!! tip ""
    You can add nested bullets within lists by adding two spaces before each
    nested bullet.

Numbered lists in which each item begins with the same number will
have the numbers automatically edited to increment (e.g. if every line
starts with `3.`, it'll go 3, 4, 5, ...).

![Numbered lists](/static/images/help/numbered-lists-screenshot.png)

## Emojis

Zulip features a variety of emojis provided by the
[Noto Project](https://code.google.com/p/noto/). To include emojis in
your messages, surround the emoji phrase with `:colons:`.

A dropdown will appear with suggested emojis as you enter the emoji phrase.

![Emojis](/static/images/help/emojis-screenshot.png)

A complete list of emojis can be found [here](http://www.webpagefx.com/tools/emoji-cheat-sheet/).

## Mentions

To call the attention of another member, you can alert them by typing
`@**username**`

If you type `@` and then begin typing the user's email address or the
user's name, the system will offer you auto-completion suggestions.

![Mentions](/static/images/help/mention-screenshot.png)

Typing `@**all**` will alert all users in the stream, and a
confirmation message will appear.

![Mention All](/static/images/help/all-confirm.png)

For more information on mentions, visit [here](/help/at-mention-a-team-member).

## Status Messages

You can send messages that display your name and profile before a string by
beginning a message with `/me`. You can utilize this feature to send status
messages or other messages written in a similar third-person voice.

For example, if your username is **Cordelia Lear** and you send the message
`/me is now away`, your message will be displayed as:

![Status message](/static/images/help/status-message.png).

## Code

You can surround a portion of code with `` `back-ticks` `` to display it as
inline code.

![Inline code](/static/images/help/inline-code-screenshot.png)

Multi-line blocks of code are either:

- Fenced by lines with three back-ticks (` ``` `).
- Fenced by lines with three tildes (`~~~`).
- Indented with four spaces.

![No code syntax highlighting](/static/images/help/no-syntax.png)

Zulip also supports syntax highlighting of multi-line code blocks using
[Pygments](http://pygments.org). To add syntax highlighting to a multi-line code
block, add the language's **first**
[Pygments short name](http://pygments.org/docs/lexers/) after the first set of
back-ticks; as you type out a code block's short name, a dropdown with short
name suggestions will appear.

!!! warn ""
    **Note:** You can only specify the language's short name in fenced code
    blocks. It is not possible to use the syntax highlighter in blocks
    indented with spaces.

![Python syntax highlighting](/static/images/help/python-syntax.png)

![JavaScript syntax highlighting](/static/images/help/javascript-syntax.png)

![Rust syntax highlighting](/static/images/help/rust-syntax.png)

![C# syntax highlighting](/static/images/help/csharp-syntax.png)

## Quotes

To insert quotes, you can either add a greater-than symbol ```>``` and
a space before your phrase or submit it as a quote block by following
the code syntax highlighting format.

![Quotes](/static/images/help/quotes-screenshot.png)

## TeX math

You can display mathematical symbols, expressions and equations using Zulip's
[TeX](http://www.tug.org/interest.html#doc) typesetting implementation,
based on [KaTeX](https://github.com/Khan/KaTeX).

!!! tip ""
    Visit the [KaTeX Wiki](https://github.com/Khan/KaTeX/wiki/Function-Support-in-KaTeX)
    to view a complete of compatible commands.

Surround elements in valid TeX syntax with `$$two dollar signs$$` to display it
as inline content.

![Inline TeX](/static/images/help/inline-tex-screenshot.png)

Also, you can show expressions, such as expanded integrals, in TeX
*display mode* to present them fully-sized in the center of the messages by
fencing them with three back-ticks ` ``` ` or tildes `~~~`, with **math**,
**tex** or **latex** immediately after the first set of back-ticks.

![Display mode TeX](/static/images/help/display-mode-tex-screenshot.png)
