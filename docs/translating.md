# Translating Zulip

Zulip has full support for unicode, so you can already use your
preferred language everywhere in Zulip.

To make Zulip even better for users around the world, the Zulip UI is
being translated into a number of major languages, including Spanish,
German, French, Chinese, Russian, and Japanese, with varying levels of
progress.  If you speak a language other than English, your help with
translating Zulip would be greatly appreciated!

If you're interested in contributing translations to Zulip, join the
[Zulip project on Transifex](https://www.transifex.com/zulip/zulip/)
and ask to join any languages you'd like to contribute to (or add new
ones).  Transifex's notification system sometimes fails to notify the
maintainers when you ask to join a project, so please send a quick
email to zulip-core@googlegroups.com when you request to join the
project or add a language so that we can be sure to accept your
request to contribute.

## Translation Tags
Zulip now supports both Jinja2 and Django template backends. There is
a slight difference in the tags which are used to mark the translation
strings in the two backends. To translate a block Jinja2 uses
[trans](http://jinja.pocoo.org/docs/dev/templates/#i18n)
tag while Django uses [blocktrans](https://docs.djangoproject.com/en/1.8/topics/i18n/translation/#std:templatetag-blocktrans)
tag.

#### Jinja2 example
```
{% trans %}foobar{% endtrans %}
```

#### Django example
```
{% blocktrans %}foobar{% endblocktrans %}
```

To translate a string in both backends we are in luck as both backends
recognize `_()` function.

#### Example code which works in both backends
```
_('foobar')
```
