# Code blocks

{!code-blocks-intro.md!}

## Insert code formatting

Zulip's compose box has a smart **Code** (<i class="zulip-icon
zulip-icon-code"></i>) button, which inserts contextually appropriate code
formatting:

- If no text is selected, the button inserts code block (` ``` `) formatting.
- If selected text is on one line, the button inserts code span (`` ` ``)
  formatting.
- If selected text is on multiple lines, the button inserts code block (` ``` `)
  formatting.

{start_tabs}

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. _(optional)_ Select the text you want to format.

1. Click the **Code** (<i class="zulip-icon zulip-icon-code"></i>) icon at the
   bottom of the compose box to insert code formatting.

1. _(optional)_ To enable syntax highlighting in a code bock, start typing the
   name of the desired programming language directly after the initial ` ``` `.
   Select the language from the auto-complete suggestions.

!!! tip ""

    You can also use the **Code** (<i class="zulip-icon zulip-icon-code"></i>)
    icon to remove existing code formatting from the selected text.

{tab|via-markdown}

{!start-composing.md!}

1.  To create an inline code span, use single backticks around the text:

        `text`

    To create a code block, use triple backticks around the text:

        ```
        def f(x):
            return x+1
        ```

    To enable syntax highlighting, use triple backticks followed by one or more
    letters, and select the desired programming language from the auto-complete
    suggestions.

        ```python
        def fib(n):
            # TODO: base case
            return fib(n-1) + fib(n-2)
        ```

!!! tip ""

    You can also use `~~~` to start code blocks, or just indent the code 4 or more
    spaces.

{end_tabs}

## Examples

{!code-blocks-examples.md!}

## Language tagging

Tagging a code block with a language enables syntax highlighting and
(if configured) [code playgrounds](#code-playgrounds). Zulip supports syntax
highlighting for hundreds of languages.

A code block can be tagged by typing the language name after the fence
(` ``` `) that begins a code block, as shown here.  Typeahead will
help you enter the name for the language.  The **Short names** values
from the [Pygments lexer documentation][pygments-lexers] are the
complete set of values that support syntax highlighting.

~~~
``` python
print("Hello world!")
```
~~~

### Default code block language

Organization administrators can also configure a default language for code
blocks, which will be used whenever the code block has no tag.

{!admin-only.md!}

{start_tabs}

{settings_tab|organization-settings}

1. Under **Message feed settings**, edit **Default language for code blocks**.

{end_tabs}


When a default language is configured, one can use ````text` to display code
blocks without any syntax highlighting (e.g., to paste an error message).

## Code playgrounds

Code playgrounds are interactive in-browser development environments
that are designed to make it convenient to edit
and debug code. Code playgrounds can be configured for any programming language.
Zulip code blocks that are tagged with the language will have a button visible
on hover that allows you to open the code block in the code playground site.

### Add a custom code playground

{!admin-only.md!}

{start_tabs}

{settings_tab|playground-settings}

1. Under **Add a new code playground**, enter a **Language**, **Name**, and
   **URL template**.

1. Click **Add code playground**.

{end_tabs}

For example, to configure code a playground for Rust, you could specify the
language and URL template as `Rust` and `https://play.rust-lang.org/?code={code}`.

When a code block is labeled as `rust` (either explicitly or by organization
default), users would get an on-hover option to open the code block in the
specified code playground.

!!! tip ""

    Code playgrounds use [RFC 6570](https://www.rfc-editor.org/rfc/rfc6570.html)
    compliant URL templates to describe how links should be generated. Zulip's
    rendering engine will pass the URL-encoded code from the code block as the
    `code` parameter, denoted as `{code}` in this URL template, in order to
    generate the URL. You can refer to parts of the documentation on URL
    templates from [adding a custom linkifier](/help/add-a-custom-linkifier).

### Examples of playground URL templates

Here is a list of playground URL templates you can use for some popular
languages:

* For Java: `https://pythontutor.com/java.html#code={code}` or
  `https://cscircles.cemc.uwaterloo.ca/java_visualize/#code={code}`
* For JavaScript: `https://pythontutor.com/javascript.html#code={code}`
* For Python: `https://pythontutor.com/python-compiler.html#code={code}`
* For C: `https://pythontutor.com/c.html#code={code}`
* For C++: `https://pythontutor.com/cpp.html#code={code}`
* For Rust: `https://play.rust-lang.org/?code={code}`

### Technical details

* You can configure multiple playgrounds for a given language; if you do that,
the user will get to choose which playground to open the code in.

* The **Language** field is the human-readable Pygments language name for that
programming language. The language tag for a code block is internally mapped
to these human-readable Pygments names; e.g., `py3` and `py` are mapped to
`Python`. One can use the typeahead (which appears when you type something
or just click on the language field) to look up the Pygments name.

* The links for opening code playgrounds are always constructed by substituting
the URL-encoded contents of the code block into `code` variable in the URL template.
The URL template is required to contain exactly one variable named `code`.

* Code playground sites do not always clearly document their URL format; often
you can just get the prefix from your browser's URL bar.

* You can also use a custom language name to implement simple integrations.
For example, a code block tagged with the "language" `send_tweet` could be
used with a "playground" that sends the content of the code block as a Tweet.

If you have any trouble setting up a code playground, please [contact
us](/help/contact-support) with details on what you're trying to do, and we'll
be happy to help you out.

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [LaTeX](/help/latex)
* [Spoilers](/help/spoilers)
* [Quote message](/help/quote-or-forward-a-message)

[pygments-lexers]: https://pygments.org/docs/lexers/
[get_lexer_by_name]: https://pygments-doc.readthedocs.io/en/latest/lexers/lexers.html#pygments.lexers.get_lexer_by_name
