# Message formatting

[//]: # (All screenshots here require line-height: 22px and font-size: 16px in .message-content.)
[//]: # (Requires some additional fiddling for the LaTeX picture, inline code span, and maybe a few others.)

Zulip uses Markdown to allow you to easily format your messages. Even if you've
never heard of Markdown, you are probably familiar with basic Markdown
formatting, such as using `*` at the start of a line in a bulleted list, or
around text to indicate emphasis.

This page provides an overview of all the formatting available in Zulip. There
is a convenient [**message formatting
reference**](#message-formatting-reference) in the Zulip app that you can use
whenever you need a reminder of the formatting syntax below.

* [Text emphasis](#text-emphasis)
* [Bulleted lists](#bulleted-lists)
* [Numbered lists](#numbered-lists)
* [Links](#links)
* [Code blocks](#code-blocks)
* [LaTeX](#latex)
* [Quotes](#quotes)
* [Spoilers](#spoilers)
* [Emoji and emoticons](#emoji-and-emoticons)
* [Mentions](#mentions)
* [Status messages](#status-messages)
* [Global times](#global-times)
* [Tables](#tables)
* [To-do lists](#to-do-lists)
* [Paragraphs and lines](#paragraphs-and-lines)

## Text emphasis

{!emphasis.md!}

!!! tip ""
    You can also use buttons or keyboard shortcuts (<kbd>Ctrl</kbd> +
    <kbd>B</kbd> or <kbd>Ctrl</kbd> + <kbd>I</kbd>) to make text bold or italic.
    [Learn more](/help/text-emphasis).

{!format-lists.md!}

## Links

{!links-intro.md!}

{!links-examples.md!}

!!! tip ""
    You can also use a button or a keyboard shortcut (<kbd>Ctrl</kbd> +
    <kbd>Shift</kbd> + <kbd>L</kbd>) to insert a link.
    [Learn more](/help/insert-a-link).

## Code blocks

{!code-blocks-intro.md!}

{!code-blocks-examples.md!}

## LaTeX

{!latex-intro.md!}

{!latex-examples.md!}

## Quotes

{!quotes-intro.md!}

{!quotes-examples.md!}

!!! tip ""

    There is a handy option to [quote and reply](/help/quote-and-reply) to a
    message in Zulip.

## Spoilers

{!spoilers-intro.md!}

{!spoilers-examples.md!}

## Emoji and emoticons

To translate emoticons into emoji, you'll need to
[enable emoticon translations](/help/configure-emoticon-translations).
You can also [add custom emoji](/help/custom-emoji).

```
:octopus: :heart: :zulip: :)
```

![Markdown emoji](/static/images/help/markdown-emoji.png)

## Mentions

Learn more about mentions [here](/help/mention-a-user-or-group).

```
Users: @**Polonius** or @**aaron|26** or @**|26** (two asterisks)
User group: @*support team* (one asterisk)
Silent mention: @_**Polonius** or @_**|26** (@_ instead of @)
```

The variants with numbers use user IDs, and are intended for
disambiguation (if multiple users have the same name) and bots (for
the variant that only contains the user ID).

![Markdown mentions](/static/images/help/markdown-mentions.png)

## Status messages

```
/me is away
```

![Markdown status](/static/images/help/markdown-status.png)

## Global times

When collaborating with people in another time zone, you often need to
express a specific time clearly. Rather than typing out your time zone
and having everyone translate the time in their heads, in Zulip, you
can mention a time, and it'll be displayed to each user in their own
time zone (just like the timestamps on Zulip messages).

A date picker will appear once you type `<time`.

```
Our next meeting is scheduled for <time:2020-05-28T13:30:00+05:30>
```

A person in San Francisco will see:

> Our next meeting is scheduled for *Thu, May 28 2020, 1:00 AM*.

While someone in India will see:

> Our next meeting is scheduled for *Thu, May 28 2020, 1:30 PM*.

You can also use other formats such as UNIX timestamps or human readable
dates, for example, `<time:May 28 2020, 1:30 PM IST>`.

## Tables

The initial pipes (`|`) are optional if every entry in the first column is non-empty.
The header separators (`---`) must be at least three dashes long.

```
|| yes | no | maybe
|---|---|:---:|------:
| A | left-aligned | centered | right-aligned
| B |     extra      spaces      |  are |  ok
| C | **bold** *italic* ~~strikethrough~~  :smile:  ||
```

![Markdown table](/static/images/help/markdown-table.png)

## To-do lists

Sending a message with the text `/todo` creates a simple collaborative
to-do list. Any user who can access the message can add tasks by
entering the task's title and description and clicking "Add task". Once
created, task titles and descriptions cannot be edited.

Tasks can be marked (and unmarked) as completed by clicking the
checkboxes on the left.

![Markdown todo-lists](/static/images/help/markdown-todo.png)


## Paragraphs and lines

```
One blank space for a new paragraph
New line, same paragraph

New paragraph

---, ***, or ___ for a horizontal line
Over the line

---

Under the line
```

![Markdown paragraph](/static/images/help/markdown-paragraph.png)

## Message formatting reference

A summary of the formatting syntax above is available in the Zulip app.

{start_tabs}

{!start-composing.md!}

1. Click the **question mark** (<i class="fa fa-question"></i>) icon at the
   bottom of the compose box.

{end_tabs}

## Related articles

* [Create a poll](/help/create-a-poll)
* [Mention a user or group](/help/mention-a-user-or-group)
* [Preview messages before sending](/help/preview-your-message-before-sending)
* [Resize the compose box](/help/resize-the-compose-box)
* [Messaging tips & tricks](/help/messaging-tips)
