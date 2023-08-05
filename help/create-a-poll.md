# Create a poll

Zulip natively supports creating and editing lightweight polls.

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

Once the poll is created, you'll be able to edit the name of the poll and
add options, but you won't be able to edit options once they are created.

Note that anyone can add options to any poll, though only the poll creator
can edit the name.

## Troubleshooting

`/poll` must come at the beginning of the message. It is not possible to
send a message that both has a poll and has any other content.

## Related articles

* [Message formatting](/help/format-your-message-using-markdown)
* [Collaborative to-do lists](/help/collaborative-to-do-lists)
