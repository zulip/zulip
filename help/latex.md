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

1.  To use inline LaTeX, use double dollar signs (`$$`) around the text:

        $$O(n^2)$$

    To use displayed LaTeX, use triple backticks and the word math
    (````math`) followed by some text and triple backticks at the end:

        ``` math
        \int_a^b f(t)\, dt = F(b) - F(a)
        ```

{end_tabs}

## Examples

{!latex-examples.md!}

## Copy and paste formatted LaTeX

### Copy LateX from a message in Zulip

Zulip supports [quoting](/help/quote-or-forward-a-message#quote-a-message),
[forwarding](/help/quote-or-forward-a-message#forward-a-message), or copying
math expressions, and pasting them into the compose box.

!!! tip ""

    If you select part of a math expression to copy, Zulip will automatically
    expand your selection to copy the full expression.

### Copy LaTeX from an external website

You can copy LaTeX from many third-party sites that use KaTeX, and paste it into
Zulip.

!!! tip ""

    If copy-pasting math from a website isn't working, consider contacting the
    website's administrators with the information below, as it may be an easy fix.

This feature is powered by KaTeX's MathML annotations, which embed the original
LaTeX source in the HTML for a math expression. For it to work, the website
needs to:

- Generate math expressions using KaTeX in the default `htmlAndMathml` [output
mode](https://katex.org/docs/options.html).
- Allow MathML annotations to be included in HTML copied by the browser (for
Zulip, this was [a couple lines of
CSS](https://github.com/zulip/zulip/commit/353f57e518b88333615911f12a031177c46d7fbe)).

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Preview messages before sending](/help/preview-your-message-before-sending)
* [Resize the compose box](/help/resize-the-compose-box)
