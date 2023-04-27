# Add a custom linkifier

{!admin-only.md!}

Linkifiers make it easy to refer to issues or tickets in third
party issue trackers, like GitHub, Salesforce, Zendesk, and others.
For instance, you can add a linkifier that automatically turns `#2468`
into a link to `https://github.com/zulip/zulip/issues/2468`.

If the pattern appears in a topic, Zulip adds an **Open**
(<i class="fa fa-external-link-square"></i>) button to the right of the
topic in the message recipient bar that links to the appropriate URL.

### Add a custom linkifier

{start_tabs}

{settings_tab|linkifier-settings}

1. Under **Add a new linkifier**, enter a **Pattern** and
**URL template**.

1. Click **Add linkifier**.

{end_tabs}

## Understanding linkification patterns

Linkifier patterns are best explained by example.

Hash followed by a number of any length.

* Pattern: `#(?P<id>[0-9]+)`
* URL template: `https://github.com/zulip/zulip/issues/{id}`
* Original text: `#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

String of hexadecimal digits between 7 and 40 characters long.

* Pattern: `(?P<id>[0-9a-f]{7,40})`
* URL template: `https://github.com/zulip/zulip/commit/{id}`
* Original text: `abdc123`
* Automatically links to: `https://github.com/zulip/zulip/commit/abcd123`

Generic GitHub `org/repo#ID` format:

* Pattern: `(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)`
* URL template: `https://github.com/{org}/{repo}/issues/{id}`
* Original text: `zulip/zulip#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

The following examples cover the most common types of linkifiers,
where the variable part of what you want to linkifier is relatively
simple. But linkifiers are powerful enough to do much fancier rules
than the examples above. If you have any trouble creating the
linkifiers you want, please [contact us](/help/contact-support) with
details on what you're trying to do, and we'll be happy to help you
out.

### Technical specification and advanced linkifiers

Linkifier patterns are regular expressions, using the
[re2](https://github.com/google/re2/wiki/Syntax) regular expression
engine. Linkifiers use [RFC
6570](https://www.rfc-editor.org/rfc/rfc6570.html) compliant URL
templates to describe how links should be generated.

RFC 6570 URL templates support several expression types. The default
expression type (`{var}`) will URL-encode special characters like `/`
and `&`; this behavior is desired for the vast majority of linkifiers.

Fancier URL template expression types can allow you to get the exact
behavior you want in corner cases like optional URL query
parameters. For example, `{+var}` helps when you want URL delimiter
characters to not be URL-encoded, `{?var}` and `{&var}` help when
generating URL query parameters, and `{\#var}` helps when generating
`#` fragments in URLs.

This toy linkifier is a shorthand for linking to pages on Zulip's
ReadTheDocs site. It uses the `{+var}` expression type; with the
default expression type (`{article}`), the `/` between `overview` and
`changelog` would incorrectly be URL-encoded:

* Pattern: `RTD/(?P<article>[a-zA-Z0-9_/.#-]+)`
* URL template: `https://zulip.readthedocs.io/en/latest/{+article}`
* Original text: `RTD/overview/changelog.html`
* Automatically links to: `https://zulip.readthedocs.io/en/latest/overview/changelog.html`

This toy linkifier allows linking to Google searches. It uses the
`{?var}` expression type; with the default expression type
(`{query}`), there would be no way to only include the `?` in the URL
if the optional `query` is present.

* Pattern: `google:(?P<query>\w+)?`
* URL template: `https://google.com/search{?query}`
* Original text: `google:foo` or `google:`
* Automatically links to: `https://google.com/search?q=foo` or `https://google.com/search`

The URL template specfication has [brief
examples](https://www.rfc-editor.org/rfc/rfc6570.html#section-1.2) and
[detailed
examples](https://www.rfc-editor.org/rfc/rfc6570.html#section-3.2)
explaining the precise behavior of URL templates.
