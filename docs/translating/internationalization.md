# Internationalization for developers

Zulip, like many popular applications, is designed with
internationalization (i18n) in mind, which means users can fully use
the Zulip UI in their preferred language.

This article aims to teach Zulip contributors enough about
internationalization and Zulip's tools for it so that they can make
correct decisions about how to tag strings for translation. A few
principles are important in how we think about internationalization:

- Our goal is for **all end-user facing strings** in Zulip to be
  tagged for translation in both [HTML templates](#html-templates) and
  code, and our linters attempt to enforce this. There are some
  exceptions: we don't tag strings in Zulip's landing pages
  (e.g. /features/) and other documentation (e.g. /help/) for
  translation at this time (though we do aim for those pages to be
  usable with tools like Google Translate).
- Translating all the strings in Zulip for a language and maintaining
  that translation is a lot of work, and that work scales with the
  number of strings tagged for translation in Zulip. For this reason,
  we put significant effort into only tagging for translation content
  that will actually be displayed to users, and minimizing unnecessary
  user-facing strings in the product.
- In order for a translated user experience to be good, every UI
  element needs to be built in a way that supports i18n.
- This is more about string consistency in general, but we have a
  "Sentence case" [capitalization
  policy](translating.md#capitalization) that we enforce using linters
  that check all strings tagged for translation in Zulip.

This article aims to provide a brief introduction. We recommend the
[EdX i18n guide][edx-i18n] as a great resource for learning more about
internationalization in general; we agree with essentially all of
their style guidelines.

[edx-i18n]: https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/internationalization/i18n.html

## Key details about human language

There are a few critical details about human language that are important
to understand when implementing an internationalized application:

- **Punctuation** varies between languages (e.g. Japanese doesn't use
  `.`s at the end of sentences). This means that you should always
  include end-of-sentence symbols like `.` and `?` inside the
  to-be-translated strings, so that translators can correctly
  translate the content.
- **Word order** varies between languages (e.g. some languages put
  subjects before verbs, others the other way around). This means
  that **concatenating translatable strings** produces broken results
  (more details with examples are below).
- The **width of the string needed to express something** varies
  dramatically between languages; this means you can't just hardcode a
  button or widget to look great for English and expect it to work in
  all languages. German is a good test case, as it has a lot of long
  words, as is Japanese (as character-based languages use a lot less
  width).
- This is more about how i18n tooling works, but in code, the
  translation function must be passed the string to translate, not a
  variable containing the target string. Otherwise, the parsers that
  extract the strings in a project to send to translators will not
  find your string.

There's a lot of other interesting differences that are important for
i18n (e.g. Zulip has a "full name" field rather than "first name" and
"last name" because different cultures order the surnames and given
names differently), but the above issues are likely to be relevant to
most people working on Zulip.

## Translation process

The end-to-end tooling process for translations in Zulip is as follows.

1. The strings are marked for translation (see sections for
   [backend](#backend-translations) and
   [frontend](#frontend-translations) translations for details on
   this).

2. Translation resource files are created using the
   `./manage.py makemessages` command. This command will create, for
   each language, a resource file called `translations.json` for the
   frontend strings and `django.po` for the backend strings.

   The `makemessages` command is idempotent in that:

   - It will only delete singular keys in the resource file when they
     are no longer used in Zulip code.
   - It will only delete plural keys (see below for the documentation
     on plural translations) when the corresponding singular key is
     absent.
   - It will not override the value of a singular key if that value
     contains a translated text.

3. Those resource files are uploaded to Transifex by a maintainer using the
   `./tools/i18n/push-translations` command (which invokes a Transifex
   API tool, `tx push`, internally).

4. Translators translate the strings in the Transifex UI. (In theory,
   it's possible to translate locally and then do `tx push`, but
   because our workflow is to sync translation data from Transifex to
   Zulip, making changes to translations in Zulip risks having the
   changes blown away by a data sync, so that's only a viable model
   for a language that has no translations yet).

5. The translations are downloaded back into the codebase by a
   maintainer, using `tools/i18n/sync-translations` (which invokes the
   Transifex API tool, `tx pull`, internally).

If you're interested, you may also want to check out the [translators'
workflow](translating.md#translators-workflow), just so you have a
sense of how everything fits together.

## Translation resource files

All the translation magic happens through resource files, which hold
the translated text. Backend resource files are located at
`locale/<lang_code>/LC_MESSAGES/django.po`, while frontend
resource files are located at
`locale/<lang_code>/translations.json` (and mobile at
`mobile.json`).

These files are uploaded to [Transifex][], where they can be translated.

## HTML Templates

Zulip makes use of the [Jinja2][] templating system for the backend
and [Handlebars][] for the frontend. Our [HTML templates][html-templates]
documentation includes useful information on the syntax and
behavior of these systems.

## Backend translations

### Jinja2 templates

All user-facing text in the Zulip UI should be generated by an Jinja2 HTML
template so that it can be translated.

To mark a string for translation in a Jinja2 template, you
can use the `_()` function in the templates like this:

```jinja
{{ _("English text") }}
```

If a piece of text contains both a literal string component and variables,
you can use a block translation, which makes use of placeholders to
help translators to translate an entire sentence. To translate a
block, Jinja2 uses the [trans][trans] tag. So rather than writing
something ugly and confusing for translators like this:

```jinja
# Don't do this!
{{ _("This string will have") }} {{ value }} {{ _("inside") }}
```

You can instead use:

```jinja
{% trans %}This string will have {{ value }} inside.{% endtrans %}
```

### Python

A string in Python can be marked for translation using the `_()` function,
which can be imported as follows:

```python
from django.utils.translation import gettext as _
```

Zulip expects all the error messages to be translatable as well. To
ensure this, the error message passed to `JsonableError`
should always be a literal string enclosed by `_()`
function, e.g.:

```python
JsonableError(_('English text'))
```

If you're declaring a user-facing string at top level or in a class, you need to
use `gettext_lazy` instead, to ensure that the translation happens at
request-processing time when Django knows what language to use, e.g.:

```python
from zproject.backends import check_password_strength, email_belongs_to_ldap

AVATAR_CHANGES_DISABLED_ERROR = gettext_lazy("Avatar changes are disabled in this organization.")

def confirm_email_change(request: HttpRequest, confirmation_key: str) -> HttpResponse:
  ...
```

```python
class Realm(models.Model):
    MAX_REALM_NAME_LENGTH = 40
    MAX_REALM_SUBDOMAIN_LENGTH = 40

    ...
    ...

    STREAM_EVENTS_NOTIFICATION_TOPIC = gettext_lazy('stream events')
```

To ensure we always internationalize our JSON error messages, the
Zulip linter (`tools/lint`) attempts to verify correct usage.

## Frontend translations

We use the [FormatJS][] library for frontend translations when dealing
with [Handlebars][] templates or JavaScript.

To mark a string translatable in JavaScript files, pass it to the
`intl.formatMessage` function, which we alias to `$t` in `intl.js`:

```js
$t({defaultMessage: "English text"})
```

The string to be translated must be a constant literal string, but
variables can be interpolated by enclosing them in braces (like
`{variable}`) and passing a context object:

```js
$t({defaultMessage: "English text with a {variable}"}, {variable: "Variable value"})
```

FormatJS uses the standard [ICU MessageFormat][], which includes
useful features such as plural translations.

`$t` does not escape any variables, so if your translated string is
eventually going to be used as HTML, use `$t_html` instead.

```js
$("#foo").html(
    $t_html({defaultMessage: "HTML with a {variable}"}, {variable: "Variable value"})
);
```

The only HTML tags allowed directly in translated strings are the
simple HTML tags enumerated in `default_html_elements`
(`web/src/i18n.ts`) with no attributes. This helps to avoid
exposing HTML details to translators. If you need to include more
complex markup such as a link, you can define a custom HTML tag
locally to the translation:

```js
$t_html(
    {defaultMessage: "<b>HTML</b> linking to the <z-link>login page</z-link>"},
    {"z-link": (content_html) => `<a href="/login/">${content_html.join("")}</a>`},
)
```

### Handlebars templates

For translations in Handlebars templates we also use FormatJS, through two
Handlebars [helpers][] that Zulip registers. The syntax for simple strings is:

```html+handlebars
{{t 'English text' }}

{{t 'Block of English text with a {variable}.' }}
```

If you are passing a translated string to a Handlebars partial, you can use:

```html+handlebars
{{> template_name
    variable_name=(t 'English text')
    }}
```

The syntax for HTML strings is:

<!-- The html+handlebars lexer fails to lex the single braces. -->

```text
{{#tr}}
    <p>Block of English text.</p>
{{/tr}}

{{#tr}}
    <p>Block of English text with a {variable}.</p>
{{/tr}}
```

Just like in JavaScript code, variables are enclosed in _single_
braces (rather than the usual Handlebars double braces). Unlike in
JavaScript code, variables are automatically escaped by our Handlebars
helper.

Handlebars expressions like `{{variable}}` or blocks like
`{{#if}}...{{/if}}` aren't permitted inside a `{{#tr}}...{{/tr}}`
translated block, because they don't work properly with translation.
The Handlebars expression would be evaluated before the string is
processed by FormatJS, so that the string to be translated wouldn't be
constant. We have a linter to enforce that translated blocks don't
contain Handlebars.

Restrictions on including HTML tags in translated strings are the same
as in JavaScript. You can insert more complex markup using a local
custom HTML tag like this:

```html+handlebars
{{#tr}}
    <b>HTML</b> linking to the <z-link>login page</z-link>
    {{#*inline "z-link"}}<a href="/login/">{{> @partial-block}}</a>{{/inline}}
{{/tr}}
```

## Transifex config

The config file that maps the resources from Zulip to Transifex is
located at `.tx/config`.

## Transifex CLI setup

In order to be able to run `tx pull` (and `tx push` as well, if you're a
maintainer), you have to specify your Transifex API Token, [generated in
Transifex's web interface][transifex-api-token], in a config file located at
`~/.transifexrc`.

You can find details on how to set it up [here][transifexrc], but it should
look similar to this (with your credentials):

```ini
[https://www.transifex.com]
rest_hostname = https://rest.api.transifex.com
token = 1/abcdefg...
```

This basically identifies you as a Transifex user, so you can access your
organizations from the command line.

[jinja2]: http://jinja.pocoo.org/
[handlebars]: https://handlebarsjs.com/
[trans]: https://jinja.palletsprojects.com/en/3.0.x/extensions/#i18n-extension
[formatjs]: https://formatjs.io/
[icu messageformat]: https://formatjs.io/docs/intl-messageformat
[helpers]: https://handlebarsjs.com/guide/block-helpers.html
[transifex]: https://www.transifex.com
[transifex-api-token]: https://app.transifex.com/user/settings/api/
[transifexrc]: https://docs.transifex.com/client/client-configuration#transifexrc
[html-templates]: ../subsystems/html-css.md#html-templates
