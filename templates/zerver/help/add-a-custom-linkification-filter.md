# Add a custom linkification filter

{!admin-only.md!}

Linkifiers make it easy to refer to issues or tickets in third
party issue trackers, like GitHub, Salesforce, Zendesk, and others.
For instance, you can add a filter that automatically turns `#2468`
into a link to `https://github.com/zulip/zulip/issues/2468`.

{settings_tab|filter-settings}

1. Under **Add a new linkifier**, enter a **Pattern** and
**URL format string**.

1. Click **Add linkifier**.

!!! tip ""

    If the pattern appears in a message topic, Zulip can't linkify the topic
    itself, since clicking on a topic narrows to that topic. So Zulip
    instead provides a little button to the right of the topic that links to
    the appropriate URL.

## Understanding linkification patterns

This is best explained by example.

Hash followed by a number of any length.

* Pattern: `#(?P<id>[0-9]+)`
* URL format string: `https://github.com/zulip/zulip/issues/%(id)s`
* Original text: `#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

String of hexadecimal digits between 7 and 40 characters long.

* Pattern: `(?P<id>[0-9a-f]{7,40})`
* URL format string: `https://github.com/zulip/zulip/commit/%(id)s`
* Original text: `abdc123`
* Automatically links to: `https://github.com/zulip/zulip/commit/abcd123`

Generic GitHub `org/repo#ID format:

* Pattern: `(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)`
* URL format string: `https://github.com/%(org)s/%(repo)s/issues/%(id)s`
* Original text: `zulip/zulip#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

Linkifiers can be very useful, but also complicated to set up. If you have
any trouble setting these up, please email support@zulipchat.com with a few
examples of "Original text" and "Automatically links to" and we'll be happy
to help you out.
