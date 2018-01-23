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
