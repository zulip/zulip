# Construct a narrow

A **narrow** is a set of filters for Zulip messages, that can be based on many
different factors (like sender, date, stream...).

Narrows look like this:

```
stream:announce sender:iago@zulip.com
```

## Operators and operands

Each of the key-value pairs that make a narrow are a filter for a specific
characteristic of the messages.
[These](/help/search-for-messages#search-operators) are the message filters (or
**operators**) you can use for a narrow.

The values that each operator carry are the **operands**. Thus, in the
following narrow:

```
stream:holidays search:where+are+my+sunglasses?
```

<table>
    <tr>
        <th>Operator</th>
        <th>Operand</th>
    </tr>
    <tr>
        <td>stream</td>
        <td>holidays</td>
    </tr>
    <tr>
        <td>search</td>
        <td>where are my sunglasses?</td>
    </tr>
</table>

Note that you can escape the spaces with the plus (`+`) character when you're
using the `key:value` narrow syntax.

## JSON-based narrows

While `key:value` can be used in Zulip's search bar, the narrows used by
endpoints in our REST API are structured in JSON format.

The result is an array of objects, each with an `operator` and an `operand`
key.

This way, the previous example would look like this:

```
[
    {
        "operator": "stream",
        "operand": "holidays"
    },
    {
        "operator": "search",
        "operand": "where are my sunglasses?"
    }
]
```

Note that escaping spaces isn't required here.
