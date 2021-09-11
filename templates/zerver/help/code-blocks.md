# Code spans and blocks

Zulip supports the standard [Markdown syntax][markdown] for inline
code spans and code blocks:

~~~
Inline code span: `let x = 5`

Code block:
```
def f(x):
   return x+1
```

Syntax highlighting:
```python
def fib(n):
    # TODO: base case
    return fib(n-1) + fib(n-2)
```
~~~

Sending the above message in Zulip will render like this:

![Markdown code](/static/images/help/markdown-code.png)

You can also use `~~~` to start code blocks, or just indent the code 4 or more
spaces.

A widget in the upper-right corner of code blocks allows you to easily
copy the code to your clipboard.

## Language tagging

Tagging a code block with a language enables syntax highlighting and
(if configured) [code playgrounds](#code-playgrounds). Zulip supports syntax highlighting
for hundreds of languages.

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

1. Under **Other settings**, edit **Default language for code blocks**.

{end_tabs}


When a default language is configured, one can use ````text` to display code
blocks without any syntax highlighting (E.g. to paste an error message).

## Code playgrounds

Code playgrounds are interactive in-browser development environments, such as
[replit](https://replit.com), that are designed to make it convenient to edit
and debug code. Code playgrounds can be configured for any programming language.
Zulip code blocks that are tagged with the language will have a button visible
on hover that allows you to open the code block in the code playground site.

### Add a custom code playground

{!admin-only.md!}

{start_tabs}

{settings_tab|playground-settings}

1. Under **Add a new code playground**, enter a **Name**, **Language** and **URL
prefix**.

1. Click **Add code playground**.

{end_tabs}

For example, to configure code playgrounds for languages like Python or
JavaScript, you could specify the language and URL prefix fields as:

* `Python` and `https://replit.com/languages/python3/?code=`
* `JavaScript` and `https://replit.com/languages/javascript/?code=`

When a code block is labeled as Python or JavaScript (either explicitly or by
organization default), users would get a on-hover option to open the code block
in the specified code playground.

### Technical details

* You can configure multiple playgrounds for a given language; if you do that,
the user will get to choose which playground to open the code in.

* The **Language** field is the human-readable Pygments language name for that
programming language. The language tag for a code block is internally mapped
to these human-readable Pygments names. E.g: `py3` and `py` are mapped to
`Python`. One can use the typeahead (which appears when you type something
or just click on the language field) to lookup the Pygments name.

* The links for opening code playgrounds are always constructed by concatenating
the provided URL prefix with the URL-encoded contents of the code block.

* Code playground sites do not always clearly document their URL format; often
you can just get the prefix from your browser's URL bar.

* You can also use a custom language name to implement simple integrations.
For example, a code block tagged with the "language" `send_tweet` could be
used with a "playground" that sends the content of the code block as a Tweet.

If you have any trouble setting in setting up a code playground, please [contact
us](/help/contact-support) with details on what you're trying to do, and we'll
be happy to help you out.

## Related articles

[Math blocks][math-block], [spoiler blocks][spoiler-block], and [quote
blocks][quote-block] use similar fenced block syntax.

[pygments-lexers]: https://pygments.org/docs/lexers/
[get_lexer_by_name]: https://pygments-doc.readthedocs.io/en/latest/lexers/lexers.html#pygments.lexers.get_lexer_by_name

[markdown]: /help/format-your-message-using-markdown
[math-block]: /help/format-your-message-using-markdown#latex
[quote-block]: /help/format-your-message-using-markdown#quotes
[spoiler-block]: /help/format-your-message-using-markdown#spoilers
