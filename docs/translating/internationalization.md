# Internationalization for developers

Zulip is designed with internationalization (i18n) in mind, which lets users
view the Zulip UI in their preferred language. As a developer, it's your
responsibility to make sure that:

- UIs you implement look good when translated into languages other than English.
- Any strings your code changes touch are correctly marked for translation.

This pages gives concrete guidance on how to accomplish these goals, as well as
providing additional context for those who are curious.

## How internationalization impacts Zulip's UI

Always be mindful that **text width is not a constant**. The width of the string
needed to express something varies dramatically between languages. This means
you can't just hardcode a button or widget to look great for English and expect
it to work in all languages.

You can test your work by changing the lengths of strings to be 50% longer and
50% shorter than in English. For strings that are already in the Zulip UI,
Russian is a good test case for translations that are generally longer than
English. Japanese translations are generally shorter.

## What should be marked for translation

Our goal is for **all user-facing strings** in Zulip to be tagged for
translation in both [HTML templates][html-templates] and code, and our linters
attempt to enforce this. This applies to every bit of language a user might see,
including things like error strings, dates, and email content.

The exceptions to the "tag everything users sees" rule are:

- Landing pages (e.g., <https://zulip.com/features/>)
- [Help center pages](../documentation/helpcenter.md)
- [Zulip updates](https://zulip.com/help/configure-automated-notices#zulip-update-announcements)

We do aim for those pages to be usable with tools like Google Translate.

Note that the "user-facing" part is also important. To make good use of our
community translators' valuable time, we only tag content that will actually be
displayed to users.

## How to mark a string for translation

When tagging strings for translation, variation between languages means that you
have to be careful in exactly what you tag, and how you split things up:

- **Punctuation** varies between languages (e.g., Japanese doesn't use
  `.`s at the end of sentences). This means that you should always
  include end-of-sentence symbols like `.` and `?` inside the
  to-be-translated strings, so that translators can correctly
  translate the content.
- **Word order** varies between languages (e.g., some languages put subjects
  before verbs, others the other way around). This means that **concatenating
  translatable strings** produces broken results. If a sentence contains a
  variable, never tag the part before the variable separately from the part
  after the variable.
- **Strings with numerals** (e.g., "5 bananas") work quite differently between
  languages, so double-check your work when tagging strings with numerals for
  translation. See the [plurals](#plurals-and-lists) section below for details.

Note also that we have a "sentence case" [capitalization
policy](translating.md#capitalization) that we enforce using linters that check
all strings tagged for translation in Zulip.

## Translation syntax in Zulip

A few general notes:

- Translation functions must be passed the string to translate, not a
  variable containing the target string. Otherwise, the parsers that
  extract the strings in a project to send to translators will not
  find your string.

- Zulip makes use of the [Jinja2][] templating system for the server
  and [Handlebars][] for the web app. Our [HTML templates][html-templates]
  documentation includes useful information on the syntax and
  behavior of these systems.

### Web application translations

We use the [FormatJS][] library for translations in the Zulip web app,
both in [Handlebars][] templates and JavaScript.

FormatJS uses the standard [ICU MessageFormat][], which includes
useful features such as [plural translations](#plurals-and-lists).

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

`$t` does not escape any variables, so if your translated string is
eventually going to be used as HTML, use `$t_html` instead.

```js
html_content = $t_html({defaultMessage: "HTML with a {variable}"}, {variable: "Variable value"});
$("#foo").html(html_content);
```

The only HTML tags allowed directly in translated strings are the
simple HTML tags enumerated in `default_html_elements`
(`web/src/i18n.ts`) with no attributes. This helps to avoid
exposing HTML details to translators. If you need to include more
complex markup such as a link, you can define a custom HTML tag
locally to the translation, or use a Handlebars template:

```js
$t_html(
    {defaultMessage: "<b>HTML</b> linking to the <z-link>login page</z-link>"},
    {"z-link": (content_html) => `<a href="/login/">${content_html.join("")}</a>`},
)
```

#### Plurals and lists

Plurals are a complex detail of human language. In English, there are
only two variants for how a word like "banana" might be spelled
depending on the number of objects being discussed: "1 banana" and "2
bananas". But languages vary greatly in how plurals work. For example,
in Russian, the form a noun takes
[depends](https://en.wikipedia.org/wiki/Russian_declension#Declension_of_cardinal_numerals)
in part on the last digit of its quantity.

To solve this problem, Zulip expresses plural strings using the
standard [ICU MessageFormat][] syntax, which defines how the string
varies depending on whether there's one item or many in English:

```js
"{N, plural, one {Done! {N} message marked as read.} other {Done! {N} messages marked as read.}}"
```

Translators are then able to write a translation using this same
syntax, potentially using a different set of cases, like this Russian
translation, which varies the string based on whether there was 1,
few, or many items:

```js
"{N, plural, one {Готово! {N} сообщение помечено как прочитанное.} few {Готово! {N} сообщений помечены как прочитанные.} many {Готово! {N} сообщений помечены как прочитанные.} other {Готово! {N} сообщений помечены как прочитанные.}}"
```

You don't need to understand how to write Russian plurals. As a
developer, you just need to write the correct ICU plurals for English,
which will always just have singular and plural variants, and
translators can take care of the rest.

Nonetheless, even the English format takes some concentration to
read. So when designing UI, we generally try to avoid unnecessarily
writing strings that require plurals in favor of other ways to present
information, like displaying an icon with a number next to it.

Languages differ greatly in how to construct a list of the form "foo,
bar, and baz". Some languages don't use commas! The web application
has a handy `util.format_array_as_list` function for correctly doing
this using the `Intl` module; use `git grep` to find examples.

#### Handlebars templates

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

### Server translations

Strings in the server primarily comprise two areas:

- Error strings and other values returned by the API.
- Strings in portico pages, such as the login flow, that are not
  rendered using JavaScript or Handlebars.

#### Jinja2 templates

All user-facing text in the Zulip UI should be generated by an Jinja2 HTML
template so that it can be translated.

To mark a string for translation in a Jinja2 template, you
can use the `_()` function in the templates like this:

```jinja
{{ _("English text") }}
```

If a piece of text contains both a literal string component and variables, use a
block translation. This puts in placeholders for variables, to allow translators
to translate an entire sentence.

To tag a block for translation, Jinja2 uses the [trans][trans] tag, like this:

```jinja
{% trans %}This string will have {{ value }} inside.{% endtrans %}
```

Never break up a sentence like this, as it will make it impossible to translate
correctly:

```jinja
# Don't do this!
{{ _("This string will have") }} {{ value }} {{ _("inside") }}
```

#### Python

A string in Python can be marked for translation using the `_()` function,
which can be imported as follows:

```python
from django.utils.translation import gettext as _
```

Zulip expects all the error messages to be translatable as well. To
ensure this, the error message passed to `JsonableError`
should always be a literal string enclosed by `_()`
function, for example:

```python
JsonableError(_('English text'))
```

If you're declaring a user-facing string at top level or in a class, you need to
use `gettext_lazy` instead, to ensure that the translation happens at
request-processing time when Django knows what language to use, for example:

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

    STREAM_EVENTS_NOTIFICATION_TOPIC = gettext_lazy("channel events")
```

To ensure we always internationalize our JSON error messages, the
Zulip linter (`tools/lint`) attempts to verify correct usage.

## Translation process

The end-to-end tooling process for translations in Zulip is as follows.

1. The strings are marked for translation (see sections for
   [server](#server-translations) and
   [web app](#web-application-translations) translations for details on
   this).

2. Translation resource files are created using the
   `./manage.py makemessages` command. This command will create, for
   each language, a resource file called `translations.json` for the
   web app strings and `django.po` for the server strings.

   The `makemessages` command is idempotent in that:

   - It will only delete singular keys in the resource file when they
     are no longer used in Zulip code.
   - It will only delete plural keys (see above for the documentation
     on plural translations) when the corresponding singular key is
     absent.
   - It will not override the value of a singular key if that value
     contains a translated text.

3. Those resource files, when committed, are automatically scanned by
   Weblate.

4. Translators translate the strings in the Weblate UI.

5. Weblate makes the translations into a Git commit, which then can be
   merged into the codebase by a maintainer.

If you're interested, you may also want to check out the [translators'
workflow](translating.md#translators-workflow), just so you have a
sense of how everything fits together.

## Translation resource files

All the translation magic happens through resource files, which hold
the translated text. Server resource files are located at
`locale/<lang_code>/LC_MESSAGES/django.po`, while web app resource
files are located at `locale/<lang_code>/translations.json`.

## Additional resources

We recommend the [EdX i18n guide][edx-i18n] as a great resource for learning
more about internationalization in general; we agree with essentially all of
their style guidelines.

[edx-i18n]: https://docs.openedx.org/en/latest/developers/references/developer_guide/internationalization/i18n.html
[jinja2]: http://jinja.pocoo.org/
[handlebars]: https://handlebarsjs.com/
[trans]: https://jinja.palletsprojects.com/en/3.0.x/extensions/#i18n-extension
[formatjs]: https://formatjs.github.io/
[icu messageformat]: https://formatjs.github.io/docs/core-concepts/icu-syntax#plural-format
[helpers]: https://handlebarsjs.com/guide/block-helpers.html
[html-templates]: ../subsystems/html-css.md#html-templates
