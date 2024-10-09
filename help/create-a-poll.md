# Polls

Zulip makes it easy to create a poll. Polls in Zulip are collaborative, so
anyone can add new options to a poll. However, only the creator of the poll can
edit the question.

## Create a poll

{start_tabs}

{tab|via-compose-box-buttons}

{!start-composing.md!}

1. Make sure the compose box is empty.

1. Click the **Add poll** (<i class="zulip-icon zulip-icon-poll"></i>) icon at
   the bottom of the compose box.

1. Fill out poll information as desired, and click **Add poll** to insert poll
   formatting.

1. Click the **Send** (<i class="zulip-icon zulip-icon-send"></i>) button, or
   use a [keyboard shortcut](/help/configure-send-message-keys) to send your
   message.

!!! tip ""

    To reorder the list of options, click and drag the **vertical dots**
    (<i class="zulip-icon zulip-icon-grip-vertical"></i>) to the left of each
    option. To delete an option, click the **trash**
    (<i class="fa fa-trash-o"></i>) icon to the right of it.

{tab|via-markdown}

{!start-composing.md!}

1. Make sure the compose box is empty.

2. Type `/poll` followed by a space, and the question you want to ask.

3. _(optional)_ Type each option on a new line.

4. Click the **Send** (<i class="zulip-icon zulip-icon-send"></i>) button, or
   use a [keyboard shortcut](/help/configure-send-message-keys) to send your
   message.

!!! tip ""

    You will be able to add options after the poll is created.

{end_tabs}

## Add options to a poll

!!! warn ""

    To preserve the meaning of votes in the poll, existing poll options cannot
    be modified.

{start_tabs}

1. Fill out the **New option** field at the bottom of the poll.

1. Click **Add option** or press <kbd>Enter</kbd> to add the new option to
   the poll.

{end_tabs}

## Edit the question

!!! warn ""

    Only the creator of a poll can edit the question.

{start_tabs}

1. Click the **pencil** (<i class="fa fa-pencil"></i>) icon
   to the right of the question.

1. Edit the question as desired.

1. Click the **checkmark** (<i class="fa fa-check"></i>) icon or press
   <kbd>Enter</kbd> to save your changes.

!!! tip ""

    You can click the <i class="fa fa-remove"></i> icon or press
    <kbd>Esc</kbd> to discard your changes.

{end_tabs}

## Examples

### What you type

```
/poll What did you drink this morning?
Milk
Tea
Coffee
```

### What it looks like

![Markdown polls](/static/images/help/markdown-polls.png)

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Collaborative to-do lists](/help/collaborative-to-do-lists)
