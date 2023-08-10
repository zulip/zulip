# Add a custom linkifier

{!admin-only.md!}

Linkifiers make it easy to refer to issues or tickets in third
party issue trackers, like GitHub, Salesforce, Zendesk, and others.
For instance, you can add a linkifier that automatically turns `#2468`
into a link to `https://github.com/zulip/zulip/issues/2468`.

If the pattern appears in a topic, Zulip adds an **Open**
(<i class="fa fa-external-link-square"></i>) button to the right of the
topic in the message recipient bar that links to the appropriate URL.

If you have any trouble creating the linkifiers you want, please [contact Zulip
support](/help/contact-support) with details on what you're trying to do.

### Add a custom linkifier

{start_tabs}

{settings_tab|linkifier-settings}

1. Under **Add a new linkifier**, enter a **Pattern** and
**URL template**.

1. Click **Add linkifier**.

{end_tabs}

### Reorder linkifiers

Linkifiers are processed in order, and will not apply to text that
already is linkified. One can thus configure multiple linkifiers with
overlapping syntax, and only the first one whose regular expression
matches a given part of a message will take effect. See the
[overlapping patterns section](#overlapping-patterns) for examples.

{start_tabs}

{settings_tab|linkifier-settings}

1. Under **Linkifiers**, click and drag existing linkifiers into
   the desired order.

{end_tabs}

## Common linkifier patterns

The following examples cover the most common types of linkifiers, with a focus
on linkifiers for issues or tickets.

### Link to an issue or ticket

This is a pattern that turns a `#` followed by a number into a link. It is often
used to link to issues or tickets in third party issue trackers, like GitHub,
Salesforce, Zendesk, and others.

{start_tabs}

* Pattern: `#(?P<id>[0-9]+)`
* URL template: `https://github.com/zulip/zulip/issues/{id}`
* Original text: `#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

{end_tabs}

### Link to issues or tickets in multiple projects or apps

To set up linkifiers for issues or tickets in multiple projects,
consider extending the `#2468` format with project-specific
variants. For example, the Zulip development community
[uses](https://zulip.com/development-community/#linking-to-github-issues-and-pull-requests)
`#M2468` for an issue in the repository for the Zulip mobile app,
`#D2468` and issue in the desktop app repository, etc.

{start_tabs}

* Pattern: `#M(?P<id>[0-9]+)`
* URL template: `https://github.com/zulip/zulip-mobile/issues/{id}`
* Original text: `#M2468`
* Automatically links to: `https://github.com/zulip/zulip-mobile/issues/2468`

{end_tabs}

### Link to issues or tickets in multiple repositories

For organizations that commonly link to multiple GitHub repositories, this
linkfier pattern turns `org/repo#ID` into an issue or pull request link.

{start_tabs}

* Pattern: `(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)`
* URL template: `https://github.com/{org}/{repo}/issues/{id}`
* Original text: `zulip/zulip#2468`
* Automatically links to: `https://github.com/zulip/zulip/issues/2468`

{end_tabs}

### Link to a hexadecimal issue or ticket number

The following pattern linkfies a string of hexadecimal digits between 7 and 40
characters long, such as a Git commit ID.

{start_tabs}

* Pattern: `(?P<id>[0-9a-f]{7,40})`
* URL template: `https://github.com/zulip/zulip/commit/{id}`
* Original text: `abdc123`
* Automatically links to: `https://github.com/zulip/zulip/commit/abcd123`

{end_tabs}

## Advanced linkifier patterns

Linkifiers are a flexible system that can be used to construct rules for a wide
variety of situations. Linkifier patterns are regular expressions, using the
[re2](https://github.com/google/re2/wiki/Syntax) regular expression
engine.

Linkifiers use [RFC 6570](https://www.rfc-editor.org/rfc/rfc6570.html) compliant
URL templates to describe how links should be generated. These templates support
several expression types. The default expression type (`{var}`) will URL-encode
special characters like `/` and `&`; this behavior is desired for the vast
majority of linkifiers. Fancier URL template expression types can allow you to
get the exact behavior you want in corner cases like optional URL query
parameters. For example:

- Use `{+var}` when you want URL delimiter characters to not be URL-encoded.
- Use `{?var}` and `{&var}` for variables in URL query parameters.
- Use <code>{&#35;var}</code> when generating `#` fragments in URLs.

The URL template specification has [brief
examples](https://www.rfc-editor.org/rfc/rfc6570.html#section-1.2) and [detailed
examples](https://www.rfc-editor.org/rfc/rfc6570.html#section-3.2) explaining
the precise behavior of URL templates.

### Linking to documentation pages

This example pattern is a shorthand for linking to pages on Zulip's ReadTheDocs
site.

{start_tabs}

* Pattern: `RTD/(?P<article>[a-zA-Z0-9_/.#-]+)`
* URL template: `https://zulip.readthedocs.io/en/latest/{+article}`
* Original text: `RTD/overview/changelog.html`
* Automatically links to: `https://zulip.readthedocs.io/en/latest/overview/changelog.html`

{end_tabs}

!!! tip ""

    This pattern uses the `{+var}` expression type. With the
    default expression type (`{article}`), the `/` between `overview` and
    `changelog` would incorrectly be URL-encoded.

### Linking to Google search results

This example pattern allows linking to Google searches.

{start_tabs}

* Pattern: `google:(?P<q>\w+)?`
* URL template: `https://google.com/search{?q}`
* Original text: `google:foo` or `google:`
* Automatically links to: `https://google.com/search?q=foo` or `https://google.com/search`

{end_tabs}

!!! tip ""

    This pattern uses the `{?var}` expression type. With the default expression
    type (`{q}`), there would be no way to only include the `?` in the URL
    if the optional `q` is present.

### Overlapping patterns

In this example, a general linkifier is configured to make GitHub
repository references like `zulip-desktop#123` link to issues in that
repository within the `zulip` GitHub organization. A more specific
linkifier overrides that linkifier for a specific repository of
interest (`django/django`) that is in a different organization.

{start_tabs}

* Specific linkifier (ordered before the general linkifier)
    * Pattern: `django#(?P<id>[0-9]+)`
    * URL template: `https://github.com/django/django/pull/{id}`

* General linkifier
    * Pattern: `(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)`
    * URL template: `https://github.com/zulip/{repo}/pull/{id}`

* Example matching both linkifiers; specific linkifier takes precedence:
    * Original text: `django#123`
    * Automatically links to: `https://github.com/django/django/pull/123`

* Example matching only the general linkifier:
    * Original text: `zulip-desktop#123`
    * Automatically links to: `https://github.com/zulip/zulip-desktop/pull/123`

{end_tabs}

!!! tip ""

    This set of patterns has overlapping regular expressions. Note that
    the general linkifier pattern would match `lorem#123` too. The specific
    linkifier will only get prioritized over the general linkifier if it is
    ordered before the more general pattern. This can be customized by
    dragging and dropping existing linkifiers into the desired order. New
    linkifiers will automatically be ordered last.
