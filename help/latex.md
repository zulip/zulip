# LaTeX

{!latex-intro.md!}

## Insert LaTeX formatting

Zulip's compose box has a smart **Math (LaTeX)** (<i class="zulip-icon
zulip-icon-math"></i>) button, which inserts contextually appropriate LaTeX
formatting:

- If no text is selected, the button inserts displayed LaTeX (````math`) formatting.
- If selected text is on one line, the button inserts inline LaTeX (`$$`)
  formatting.
- If selected text is on multiple lines, the button inserts displayed LaTeX
  (````math`) formatting.

{start_tabs}

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. _(optional)_ Select the text you want to format.

1. Click the **Math (LaTeX)** (<i class="zulip-icon zulip-icon-math"></i>) icon at the
   bottom of the compose box to insert LaTeX formatting.

!!! tip ""

    You can also use the **Math (LaTeX)** (<i class="zulip-icon zulip-icon-math"></i>)
    icon to remove existing LaTeX formatting from the selected text.

{tab|via-markdown}

{!start-composing.md!}

1. To use inline LaTeX, use double dollar signs (`$$`) around the text:
~~~
$$O(n^2)$$
~~~
   To use displayed LaTeX, use triple backticks and the word math
   (````math`) followed by some text and triple backticks at the end:
~~~
``` math
\int_a^b f(t)\, dt = F(b) - F(a)
```
~~~

{end_tabs}

## Examples

{!latex-examples.md!}

## Quoting and copy-pasting LaTeX

Zulip supports quoting or copying rendered math expressions in messages and pasting them (in the original LaTeX source format) into the Zulip compose box. This feature is powered by KaTeX's MathML annotations, which embed the original LaTeX source in the HTML for a math expression. When copying math expressions, Zulip will automatically expand the selected region as required to fully copy a partially selected math expression, whether within a math block or an inline expression.

This feature also enables copying LaTeX from third-party sites using KaTeX and pasting them into Zulip. For this to work, the math expressions must have been generated using KaTeX in the default `htmlAndMathml` [output mode](https://katex.org/docs/options.html), and for the site to allow MathML annotations to be included in HTML copied by the browser (for Zulip, this was [a couple lines of CSS](https://github.com/zulip/zulip/commit/353f57e518b88333615911f12a031177c46d7fbe)).

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Preview messages before sending](/help/preview-your-message-before-sending)
* [Resize the compose box](/help/resize-the-compose-box)
