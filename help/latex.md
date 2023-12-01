# LaTeX

{!latex-intro.md!}

## Insert LaTeX formatting

{start_tabs}

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. _(optional)_ Select the text you want to format.

1. Click the **LaTeX** (<i class="zulip-icon zulip-icon-math"></i>) icon at the
   bottom of the compose box to insert LaTeX formatting. The appropriate inline
   or block formatting will be applied automatically depending on whether you
   selected a whole line, part of a line, or multiple lines.

!!! tip ""

    You can also use the **LaTeX** (<i class="zulip-icon zulip-icon-math"></i>)
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

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Preview messages before sending](/help/preview-your-message-before-sending)
* [Resize the compose box](/help/resize-the-compose-box)
