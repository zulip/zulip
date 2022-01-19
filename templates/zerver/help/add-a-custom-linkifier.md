# Add a custom linkifier

{!admin-only.md!}

Linkifiers make it easy to refer to issues or tickets in third
party issue trackers, like GitHub, Salesforce, Zendesk, and others.
For instance, you can add a linkifier that automatically turns `#2468`
into a link to `https://github.com/zulip/zulip/issues/2468`.

If the pattern appears in a message topic, Zulip adds a little button to the
right of the topic that links to the appropriate URL.

### Add a custom linkifier

{start_tabs}

{settings_tab|linkifier-settings}

1. Under **Add a new linkifier**, enter a **Pattern** and
**URL format string**.

1. Click **Add linkifier**.

{end_tabs}

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

Generic GitHub `org/repo#ID` format:

* Pattern: `(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)`
* URL format string: `https://github.com/%(org)s/%(repo)s/issues/%(id)s`
* Original text: `zulip/zulip#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

Linkifier patterns are regular expressions, using the
[re2](https://github.com/google/re2/wiki/Syntax) regular expression
engine.

If you have any trouble setting these up, please [contact
us](/help/contact-support) with details on what you're trying to do,
and we'll be happy to help you out.
