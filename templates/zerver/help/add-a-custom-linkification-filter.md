# Add a custom linkification filter

{!admin-only.md!}

Linkification filters are used to automatically translate syntax
referring to an issue or support ticket in a message into a link to
that issue or ticket on a third-party site. For instance, you can
define a filter to automatically linkify #1234 to
https://github.com/zulip/zulip/pulls/1234, Z1234 to link to that
Zendesk ticket ID, or anything similar.

1. Go to the [Filter settings](/#organization/filter-settings)
{!admin.md!}

5. In the green section labeled **Add a new filter**, find the **Regular expression**
and **URL format string** fields.

    * In the **Regular expression** field, enter a
[regular expression](http://www.regular-expressions.info) that searches and
identifies the phrases you want to linkify.

        For example, if you want to linkify any numeric phrase that begins with
a `#`, you could use the regular expression `#(?P<id>[0-9]+)` to find those
phrases, where `id` is the variable that represents the phrase found by the
search.

        Please note that all regular expressions used for custom linkification
filters in your organization must be unique. In addition, the regular expression
you enter must have a variable that gets identified by the URL format string.

    * In the **URL format string** field, insert a URL that includes the regular
expression variable you specified in the **Regular expression** field. The URL
format string must be in the format of `https://example.com/%(\w+)s`.

        For example, if you want to use the variable `id` found by your regular
expression to link to a corresponding GitHub pull request on the `zulip/zulip`
repository, you could use the URL format string
`https://github.com/zulip/zulip/pull/%(id)s`.

6. After filling out the **Regular expression** and **URL format string**
fields, click the **Add filter** button to add your custom linkification
filter to your Zulip organization.

7. Upon clicking the **Add filter** button, you will receive a notification
labeled **Custom filter added!** in the **Custom linkification filters**
section, confirming the success of the addition of your custom linkification
filter to your organization.

    ![Custom linkification filter success](/static/images/help/custom-filter-success.png)

    The filter's information and settings will also be displayed above the **Add a new filter**
section. You can choose to delete any custom linkification filters in your
organization through this panel by pressing the **Delete** button next to
the filter you want to delete.

8. Users in your organization can now use your custom linkification filter in
their messages.

    ![Custom linkification filter demo](/static/images/help/custom-filter-demo.png)
