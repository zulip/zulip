# Internationalization for developers

Zulip, like many popular applications, is designed with
internationalization (i18n) in mind, which means users can fully use
the the Zulip UI in their preferred language.

This article aims to teach Zulip contributors enough about
internationalization and Zulip's tools for it so that they can make
correct decisions about how to tag strings for translation.  A few
principles are important in how we think about internationalization:

* Our goal is for **all end-user facing strings** in Zulip to be
  tagged for translation in both [HTML templates](#html-templates) and
  code, and our linters attempt to enforce this.  There are some
  exceptions: we don't tag strings in Zulip's landing pages
  (e.g. /features) and other documentation (e.g. /help) for
  translation at this time (though we do aim for those pages to be
  usable with tools like Google Translate).
* Translating all the strings in Zulip for a language and maintaining
  that translation is a lot of work, and that work scales with the
  number of strings tagged for translation in Zulip.  For this reason,
  we put significant effort into only tagging for translation content
  that will actually be displayed to users, and minimizing unnecessary
  user-facing strings in the product.
* In order for a translated user experience to be good, every UI
  element needs to be built in a way that supports i18n.
* This is more about string consistency in general, but we have a
  "Sentence case" [capitalization
  policy](../translating/translating.html#capitalization) that we enforce using linters
  that check all strings tagged for translation in Zulip.

This article aims to provide a brief introduction.  We recommend the
[EdX i18n guide][edx-i18n] as a great resource for learning more about
internationalization in general; we agree with essentially all of
their style guidelines.

[edx-i18n]: https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/internationalization/i18n.html

## Key details about human language

There's a few critical details about human language that are important
to understand when implementing an internationalized application:

* **Punctuation** varies between languages (e.g. Japanese doesn't use
  `.`s at the end of sentences).  This means that you should always
  include end-of-sentence symbols like `.` and `?` inside the
  to-be-translated strings, so that translators can correctly
  translate the content.
* **Word order** varies between languages (e.g. some languages put
  subjects before verbs, others the other way around).  This means
  that **concatenating translateable strings** produces broken results
  (more details with examples are below).
* The **width of the string needed to express something** varies
  dramatically between languages; this means you can't just hardcode a
  button or widget to look great for English and expect it to work in
  all languages.  German is a good test case, as it has a lot of long
  words, as is Japanese (as character-based languages use a lot less
  width).
* This is more about how i18n tooling works, but in code, the
  translation function must be passed the string to translate, not a
  variable containing the target string.  Otherwise, the parsers that
  extract the strings in a project to send to translators will not
  find your string.

There's a lot of other interesting differences that are important for
i18n (e.g. Zulip has a "Full Name" field rather than "First Name" and
"Last Name" because different cultures order the surnames and given
names differently), but the above issues are likely to be relevant to
most people working on Zulip.

## Translation process

The end-to-end tooling process for translations in Zulip is as follows.

1. The strings are marked for translation (see sections for
   [backend](#backend-translations) and
   [frontend](#frontend-translations) translations for details on
   this).

2. Translation [resource][] files are created using the `./manage.py
   makemessages` command. This command will create, for each language,
   a resource file called `translations.json` for the frontend strings
   and `django.po` for the backend strings.

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

4. Translators translate the strings in the Transifex UI.  (In theory,
   it's possible to translate locally and then do `tx push`, but
   because our workflow is to sync translation data from Transifex to
   Zulip, making changes to translations in Zulip risks having the
   changes blown away by a data sync, so that's only a viable model
   for a language that has no translations yet).

5. The translations are downloaded back into the codebase by a
   maintainer, using `tools/i18n/sync-translations` (which invokes the
   Transifex API tool, `tx pull`, internally).

If you're interested, you may also want to check out the [translators'
workflow](../translating/translating.html#translators-workflow), just so you have a
sense of how everything fits together.

## Translation resource files

All the translation magic happens through resource files which hold
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

All user-facing text in the Zulip UI should be generated by an Jinja2 HTML
template so that it can be translated.

To mark a string for translation in a Jinja2 template, you
can use the `_()` function in the templates like this:

```
{{ _("English text") }}
```

If a piece of text contains both a literal string component and variables,
you can use a block translation, which makes use of placeholders to
help translators to translate an entire sentence.  To translate a
block, Jinja2 uses the [trans][] tag.  So rather than writing
something ugly and confusing for translators like this:

```
# Don't do this!
{{ _("This string will have") }} {{ value }} {{ _("inside") }}
```

You can instead use:

```
{% trans %}This string will have {{ value }} inside.{% endtrans %}
```

A string in Python can be marked for translation using the `_()` function,
which can be imported as follows:

```
from django.utils.translation import ugettext as _
```

Zulip expects all the error messages to be translatable as well.  To
ensure this, the error message passed to `json_error` and
`JsonableError` should always be a literal string enclosed by `_()`
function, e.g.:

```
json_error(_('English Text'))
JsonableError(_('English Text'))
```

To ensure we always internationalize our JSON errors messages, the
Zulip linter (`tools/lint`) checks for correct usage.

## Frontend translations

We use the [i18next][] library for frontend translations when dealing
with [Handlebars][] templates or JavaScript.

To mark a string translatable in JavaScript files, pass it to the
`i18n.t` function.

```
i18n.t('English Text', context);
```

Variables in a translated frontend string are enclosed in
double-underscores, like `__variable__`:

```
i18n.t('English text with a __variable__', {'variable': 'Variable value'});
```

`i18next` also supports plural translations. To support plurals make
sure your resource file contains the related keys:

```
{
    "en": {
        "translation": {
            "key": "item",
            "key_plural": "items",
            "keyWithCount": "__count__ item",
            "keyWithCount_plural": "__count__ items"
        }
    }
}
```

With this resource you can show plurals like this:

```
i18n.t('key', {count: 0}); // output: 'items'
i18n.t('key', {count: 1}); // output: 'item'
i18n.t('key', {count: 5}); // output: 'items'
i18n.t('key', {count: 100}); // output: 'items'
i18n.t('keyWithCount', {count: 0}); // output: '0 items'
i18n.t('keyWithCount', {count: 1}); // output: '1 item'
i18n.t('keyWithCount', {count: 5}); // output: '5 items'
i18n.t('keyWithCount', {count: 100}); // output: '100 items'
```

For further reading on plurals, read the [official] documentation.

By default, all text is escaped by i18next. To unescape a text you can use
double-underscores followed by a dash `__-` like this:

```
i18n.t('English text with a __- variable__', {'variable': 'Variable value'});
```

For more information, you can read the official [unescape] documentation.

### Handlebars templates

For translations in Handlebars templates we also use `i18n.t`, through two
Handlebars [helpers][] that Zulip registers.  The syntax for simple strings is:

```
{{t 'English Text' }}
```

If you are passing a translated string to a Handlebars Partial, you can use:

```
{{> template_name
    variable_name=(t 'English Text')
    }}
```

The syntax for block strings or strings containing variables is:

```
{{#tr context}}
    Block of English text.
{{/tr}}

var context = {'variable': 'variable value'};
{{#tr context}}
    Block of English text with a __variable__.
{{/tr}}
```

Just like in JavaScript code, variables are enclosed in double
underscores `__`.

Handlebars expressions like `{{variable}}` or blocks like
`{{#if}}...{{/if}}` aren't permitted inside a `{{#tr}}...{{/tr}}`
translated block, because they don't work properly with translation.
The Handlebars expression would be evaluated before the string is
processed by `i18n.t`, so that the string to be translated wouldn't be
constant.  We have a linter to enforce that translated blocks don't
contain handlebars.

The rules for plurals are same as for JavaScript files. You just have
to declare the appropriate keys in the resource file and then include
the `count` in the context.

## Transifex config

The config file that maps the resources from Zulip to Transifex is
located at `.tx/config`.

## Transifex CLI setup

In order to be able to run `tx pull` (and `tx push` as well, if you're a
maintainer), you have to specify your Transifex credentials in a config
file, located at `~/.transifexrc`.

You can find details on how to set it up [here][transifexrc], but it should
look similar to this (with your credentials):

```
[https://www.transifex.com]
username = user
token =
password = p@ssw0rd
hostname = https://www.transifex.com
```

This basically identifies you as a Transifex user, so you can access your
organizations from the command line.


[Jinja2]: http://jinja.pocoo.org/
[Handlebars]: https://handlebarsjs.com/
[trans]: http://jinja.pocoo.org/docs/dev/templates/#i18n
[i18next]: https://www.i18next.com
[official]: https://www.i18next.com/plurals.html
[unescape]: https://www.i18next.com/interpolation.html#unescape
[helpers]: https://handlebarsjs.com/guide/block-helpers.html
[resource]: https://www.i18next.com/add-or-load-translations.html
[Transifex]: https://transifex.com
[transifexrc]: https://docs.transifex.com/client/client-configuration#transifexrc
[html-templates]: ../subsystems/html-css.html#html-templates
