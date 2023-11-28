# Create a poll

Zulip natively supports creating and editing lightweight polls.

{start_tabs}

{tab|via-markdown}

{!start-composing.md!}

1. Type `/poll` followed by a space and the name of the poll.

1. _(optional)_ Type each option on a new line.

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Click the **Add poll** icon at the
   bottom of the compose box.

1. Fill out poll information as desired, and click **Add poll** to insert poll
   formatting.

!!! tip ""

    To reorder the list of options, click and drag the **vertical dots**
    (<i class="zulip-icon zulip-icon-grip-vertical"></i>) to the left of each
    option. To delete an option, click the **trash**
    (<i class="fa fa-trash-o"></i>) icon to the right of it.

{end_tabs}

Once the poll is created, you'll be able to edit the name of the poll and
add options, but you won't be able to edit options once they are created.

Note that anyone can add options to any poll, though only the poll creator
can edit the name.

## Examples

### What you type

To create a poll, send a message like
```
/poll <name of poll>
```
or
```
/poll <name of poll>
option 1
option 2
...
```

### What it looks like

![Markdown polls](/static/images/help/markdown-polls.png)

## Troubleshooting

`/poll` must come at the beginning of the message. It is not possible to
send a message that both has a poll and has any other content.

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Collaborative to-do lists](/help/collaborative-to-do-lists)
