# Add a custom linkification filter

{!admin-only.md!}

Linkification filters are used to automatically translate syntax
referring to an issue or support ticket in a message into a link to
that issue or ticket on a third-party site. For instance, you can
define a filter to automatically linkify #1234 to
https://github.com/zulip/zulip/pulls/1234.

{settings_tab|filter-settings}

5. Under **Add a new filter**, in the **Regular expression** field, enter a
[regular expression](http://www.regular-expressions.info) that matches the
phrases you want to linkify. The regular expression you enter must have a
variable that gets used by the URL format string. Each regular expression used
for custom linkification filters in your organization must be unique. For
example, if you want to linkify any numeric phrase that begins with a `#`, you
could use the regular expression `#(?P<id>[0-9]+)`. `id` is the variable that
represents the phrase found by the search.

6. In the **URL format string** field, insert a URL that includes the regular
expression variable you specified in the **Regular expression** field.
For example, if you want to use the variable `id` to link to a corresponding
GitHub pull request on the `zulip/zulip` repository, you would use the URL
format string `https://github.com/zulip/zulip/pull/%(id)s`.

6. Click **Add filter**.

8. Users in your organization can use your custom linkification filter in
their messages by typing strings that match the specified regular expression.

!!! tip """
  If the pattern appears in a message topic, Zulip provides a button to the right of
  the topic that links to the appropriate URL.
