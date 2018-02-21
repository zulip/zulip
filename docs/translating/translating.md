# Translation Guidelines

To make Zulip even better for users around the world, the Zulip UI is
being translated into a number of major languages, including Spanish,
German, Hindi, French, Chinese, Russian, and Japanese, with varying levels of
progress. If you speak a language other than English, your help with
translating Zulip would be greatly appreciated!

If you're interested in contributing translations to Zulip, please
join [#translation](https://chat.zulip.org/#narrow/stream/translation)
in the [Zulip development community server](../contributing/chat-zulip-org.html), and
say hello. And please join the
[Zulip project on Transifex](https://www.transifex.com/zulip/zulip/)
and ask to join any languages you'd like to contribute to (or add new
ones). Transifex's notification system sometimes fails to notify the
maintainers when you ask to join a project, so please send a quick
email to zulip-core@googlegroups.com when you request to join the
project or add a language so that we can be sure to accept your
request to contribute.

Zulip has full support for Unicode, so you can already use your
preferred language everywhere in Zulip.

## Translation style guides

We are building a collection of translation style guides for Zulip,
giving guidance on how Zulip should be translated into specific
languages (e.g. what word to translate words like "home" to):

* [Chinese](chinese.html)
* [French](french.html)
* [German](german.html)
* [Hindi](hindi.html)
* [Polish](polish.html)
* [Russian](russian.html)
* [Spanish](spanish.html)

A great first step when getting started translating Zulip into a new
language is to write a style guide, since it greatly increases the
ability of future translators to translate in a way that's consistent
with what your work.

## Capitalization

We expect that all the English translatable strings in Zulip are
properly capitalized in a way consistent with how Zulip does
capitalization in general.  This means that:

* The first letter of a sentence or phrase should be capitalized.
    - Correct: "Manage streams"
    - Incorrect: "Manage Streams"
* All proper nouns should be capitalized.
    - Correct: "This is Zulip"
    - Incorrect: "This is zulip"
* All common words like URL, HTTP, etc. should be written in their
  standard forms.
    - Correct: "URL"
    - Incorrect: "Url"

We have a tool to check for the correct capitalization of the
translatable strings; this tool will not allow the Travis builds to
pass in case of errors. You can use our capitalization checker to
validate your code by running `./tools/check-capitalization`. If you
think that you have a case where our capitalization checker tool
wrongly categorizes a string as not capitalized, you can add an
exception in the `tools.lib.capitalization.IGNORED_PHRASES` list to
make the tool pass.

Please, stick to these while translating, and feel free to point out
any strings that should be improved or fixed.

## Translation process

The end-to-end process to get the translations working is as follows.

Please note that you don't need to do this if you're translating; this is
only to describe how the whole process is. If you're interested in
translating, you should check out the
[translators' workflow](#translators-workflow).

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
   `./tools/push-translations` command.

4. Translators translate the strings in Transifex.

5. The translations are downloaded back into the codebase by a
   maintainer, using `tools/sync-translations` (which invokes `tx
   pull`, internally).

## Translators' workflow

These are the steps you should follow if you want to help to translate
Zulip:

1. Join us on Zulip and ask for access to the organization, as
   [described](#translation-guidelines) at the beginning.

2. Make sure you have access to Zulip's dashboard in Transifex.

3. Ask a maintainer to update the strings.

4. Translate the strings for your language in Transifex.

Some useful tips for your translating journey:

- Follow your language's [translation guide](#translation-style-guides).
  Keeping it open in a tab while translating is very handy.  If one
  doesn't exist one, write one as you go; they're easiest to write as
  you go along and will help any future translators a lot.

- Don't translate variables or code (usually preceded by a `%`, or inside
  HTML tags `<...>`).

- When in doubt, ask for context in
  [#translation](https://chat.zulip.org/#narrow/stream/translation) in
  the [Zulip development community server](../contributing/chat-zulip-org.html).

- If there are multiple possible translations for a term, search for it in
  the *Concordance* tool (the button with a magnet in the top right corner).

  It will show if anyone translated that term before, so we can achieve good
  consistency with all the translations, no matter who makes them.

- Pay attention to capital letters and punctuation. Details make the
  difference!

- Take advantage of the hotkeys the Transifex Web Editor provides, such as
  `Tab` for saving and going to the next string.

## Testing translations

This section assumes you have a
[Zulip development environment](../development/overview.html) set up.

First of all, download the updated resource files from Transifex using the
`tx pull -a --mode=developer` command (it will require some
[initial setup](#transifex-cli-setup)). This command will download the
resource files from Transifex and replace your local resource files with
them.

Then, make sure that you have compiled the translation strings using
`./manage.py compilemessages`.

Django figures out the effective language by going through the following
steps:

1. It looks for the language code in the url (e.g. `/de/`).
2. It looks for the `LANGUAGE_SESSION_KEY` key in the current user's
session.
3. It looks for the cookie named 'django_language'. You can set a
different name through the `LANGUAGE_COOKIE_NAME` setting.
4. It looks for the `Accept-Language` HTTP header in the HTTP request.
Normally your browser will take care of this.

The easiest way to test translations is through the i18n URLs, e.g., if you
have German translations available, you can access the German version of a
page by going to `/de/path_to_page` in your browser.

To test translations using other methods you will need an HTTP client
library like `requests`, `cURL` or `urllib`. Here is some sample code to
test `Accept-Language` header using Python and `requests`:

```
import requests
headers = {"Accept-Language": "de"}
response = requests.get("http://localhost:9991/login/", headers=headers)
print(response.content)
```

## Setting the default language in Zulip

Zulip allows you to set the default language through the settings
page, in the 'Display settings' section. The URL will be
`/#settings/display-settings` on your realm.

Organizations can set the default language for new users in their
organization on the `/#organization` page.

## Translation resource files

All the translation magic happens through resource files which hold
the translated text. Backend resource files are located at
`static/locale/<lang_code>/LC_MESSAGES/django.po`, while frontend
resource files are located at
`static/locale/<lang_code>/translations.json`.

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
[Handlebars]: http://handlebarsjs.com/
[trans]: http://jinja.pocoo.org/docs/dev/templates/#i18n
[i18next]: https://www.i18next.com
[official]: https://www.i18next.com/plurals.html
[unescape]: https://www.i18next.com/interpolation.html#unescape
[helpers]: http://handlebarsjs.com/block_helpers.html
[resource]: https://www.i18next.com/add-or-load-translations.html
[Transifex]: https://transifex.com
[transifexrc]: https://docs.transifex.com/client/client-configuration#transifexrc
[html-templates]: ../subsystems/html-templates.html
