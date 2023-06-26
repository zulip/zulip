# Code style and conventions

This page documents code style policies that every Zulip developer
should understand. We aim for this document to be short and focused
only on details that cannot be easily enforced another way (e.g.,
through linters, automated tests, or subsystem design that makes classes
of mistakes unlikely). This approach minimizes the cognitive
load of ensuring a consistent coding style for both contributors and
maintainers.

One can summarize Zulip's coding philosophy as a relentless focus on
making the codebase easy to understand and difficult to make dangerous
mistakes in (see the sections on [dangerous constructs](#dangerous-constructs-in-django)
at the end of this page). The majority of work in any large software
development project is understanding the existing code so one can debug
or modify it, and investments in code readability usually end up paying
for themselves when someone inevitably needs to debug or improve the code.

When there's something subtle or complex to explain or ensure in the
implementation, we try hard to make it clear through a combination of
clean and intuitive interfaces, well-named variables and functions,
comments/docstrings, and commit messages (roughly in that order of
priority -- if you can make something clear with a good interface,
that's a lot better than writing a comment explaining how the bad
interface works).

After an introduction to our lint tools and test suites, this document
outlines some general
[conventions and practices](#follow-zulip-conventions-and-practices)
applicable to all languages used in the codebase, as well as specific
guidance on [Python](#python-specific-conventions-and-practices) and
[JavaScript and TypeScript](#javascript-and-typescript-conventions-and-practices).
([HTML and CSS](../subsystems/html-css.md) are outlined in their own
documentation.)

At the end of the document, you can read about
[dangerous constructs in Django](#dangerous-constructs-in-django) and
[JavaScript and TypeScript](#dangerous-constructs-in-javascript-and-typescript)
that you should absolutely avoid.

## Be consistent with existing code

Look at the surrounding code, or a similar part of the project, and try
to do the same thing. If you think the other code has actively bad
style, fix it (in a separate commit).

When in doubt, ask in
[#development help](https://chat.zulip.org/#narrow/stream/49-development-help).

### Use the linters

You can run all of the linters at once:

```bash
$ ./tools/lint
```

Note that that takes a little time. `./tools/lint` runs many
lint checks in parallel, including:

- JavaScript ([ESLint](https://eslint.org/),
  [Prettier](https://prettier.io/))
- Python ([mypy](http://mypy-lang.org/),
  [ruff](https://github.com/charliermarsh/ruff),
  [Black](https://github.com/psf/black),
  [isort](https://pycqa.github.io/isort/))
- templates
- Puppet configuration
- custom checks (e.g., trailing whitespace and spaces-not-tabs)

To speed things up, you can [pass specific files or directories
to the linter](../testing/linters.md):

```
$ ./tools/lint web/src/compose.js
```

If you'd like, you can also set up a local Git commit hook that
will lint only your changed files each time you commit:

```bash
$ ./tools/setup-git-repo
```

### Use tests to verify your logic

Clear, readable code is important for [tests](../testing/testing.md);
familiarize yourself with our
[testing frameworks](../testing/testing.md#major-test-suites) and
[testing philosophy](../testing/philosophy.md) so that you can write
clean, readable tests. In-test comments about anything subtle that is
being verified are appreciated.

You can run all of the tests like this:

```
$ ./tools/test-all
```

But consult [our documentation on running tests](../testing/testing.md#running-tests),
which covers more targeted approaches to commanding the test-runners.

## Follow Zulip conventions and practices

What follows is language-neutral advice that is beyond the bounds of
linters and automated tests.

### Observe a reasonable line length

We have an absolute hard limit on line length only for some files, but
we should still avoid extremely long lines. A general guideline is:
refactor stuff to get it under 85 characters, unless that makes the
code a lot uglier, in which case it's fine to go up to 120 or so.

### Tag user-facing strings for translation

Remember to
[tag all user-facing strings for translation](../translating/translating.md),
whether the strings are in HTML templates or output by JavaScript/TypeScript
that injects or modifies HTML (e.g., error messages).

### Correctly prepare paths destined for state or log files

When writing out state or log files, always pass an absolute path
through `zulip_path` (found in `zproject/computed_settings.py`), which
will do the right thing in both development and production.

### Never include secrets inline with code

Please don't put any passwords, secret access keys, etc. inline in the
code. Instead, use the `get_secret` function or the `get_mandatory_secret`
function in `zproject/config.py` to read secrets from `/etc/zulip/secrets.conf`.

### Familiarize yourself with rules about third-party code

See [our docs on dependencies](../subsystems/dependencies.md) for discussion of
rules about integrating third-party projects.

## Python-specific conventions and practices

- Our Python code is formatted with
  [Black](https://github.com/psf/black) and
  [isort](https://pycqa.github.io/isort/). The [linter
  tool](../testing/linters.md) enforces this by running Black and
  isort in check mode, or in write mode with
  `tools/lint --only=black,isort --fix`. You may find it helpful to
  [integrate Black](https://black.readthedocs.io/en/stable/integrations/editors.html)
  and
  [isort](https://pycqa.github.io/isort/#installing-isorts-for-your-preferred-text-editor)
  with your editor.
- Don't put a shebang line on a Python file unless it's meaningful to
  run it as a script. (Some libraries can also be run as scripts, e.g.,
  to run a test suite.)
- Scripts should be executed directly (`./script.py`), so that the
  interpreter is implicitly found from the shebang line, rather than
  explicitly overridden (`python script.py`).
- Put all imports together at the top of the file, absent a compelling
  reason to do otherwise.
- Unpacking sequences doesn't require list brackets:
  ```python
  [x, y] = xs    # unnecessary
  x, y = xs      # better
  ```
- For string formatting, use `x % (y,)` rather than `x % y`, to avoid
  ambiguity if `y` happens to be a tuple.

## JavaScript and TypeScript conventions and practices

Our JavaScript and TypeScript code is formatted with
[Prettier](https://prettier.io/). You can ask Prettier to reformat
all code via our [linter tool](../testing/linters.md) with
`tools/lint --only=prettier --fix`. You can also [integrate it with your
editor](https://prettier.io/docs/en/editors.html).

### Build DOM elements in Handlebars

The best way to build complicated DOM elements is a Handlebars template
like `web/templates/message_reactions.hbs`. For simpler things you can
use jQuery DOM-building APIs like this:

```js
const $new_tr = $('<tr />').attr('id', object.id);
```

### Attach behaviors to event listeners

Attach callback functions to events using jQuery code. For example:

```js
$("body").on("click", ".move_message_button", function (e) {
  // message-moving UI logic
}
```

That approach has multiple benefits:

- Potential huge performance gains by using delegated events where
  possible
- When calling a function from an `onclick` attribute, `this` is not
  bound to the element like you might think
- jQuery does event normalization

Do not use `onclick` attributes in the HTML.

### Declare variables using `const` and `let`

Always declare JavaScript variables using `const` or `let` rather than
`var`.

### Manipulate objects and arrays with modern methods

For functions that operate on arrays or JavaScript objects, you should
generally use modern
[ECMAScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Language_Resources)
primitives such as [`for … of`
loops](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of),
[`Array.prototype.{entries, every, filter, find, indexOf, map, some}`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array),
[`Object.{assign, entries, keys, values}`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object),
[spread
syntax](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Spread_syntax),
and so on. Our Babel configuration automatically transpiles and
polyfills these using [`core-js`](https://github.com/zloirock/core-js)
when necessary. We used to use the
[Underscore](https://underscorejs.org/) library, but that should be
avoided in new code.

## HTML and CSS

See the documentation on [HTML and CSS](../subsystems/html-css.md)
for guidance on conventions in those language.

## Dangerous constructs in Django

### Avoid excessive database queries

Look out for Django code like this:

```python
bars = Bar.objects.filter(...)
for bar in bars:
    foo = bar.foo
    # Make use of foo
```

...because it equates to:

```python
bars = Bar.objects.filter(...)
for bar in bars:
    foo = Foo.objects.get(id=bar.foo.id)
    # Make use of foo
```

...which makes a database query for every `Bar`. While this may be fast
locally in development, it may be quite slow in production! Instead,
tell Django's [QuerySet
API](https://docs.djangoproject.com/en/dev/ref/models/querysets/) to
_prefetch_ the data in the initial query:

```python
bars = Bar.objects.filter(...).select_related()
for bar in bars:
    foo = bar.foo  # This doesn't take another query, now!
    # Make use of foo
```

If you can't rewrite it as a single query, that's a sign that something
is wrong with the database schema. So don't defer this optimization when
performing schema changes, or else you may later find that it's
impossible.

### Never do direct database queries (`UserProfile.objects.get()`, `Client.objects.get()`, etc.)

In our Django code, never do direct `UserProfile.objects.get(email=foo)`
database queries. Instead always use `get_user_profile_by_{email,id}`.
There are 3 reasons for this:

1.  It's guaranteed to correctly do a case-inexact lookup
2.  It fetches the user object from remote cache, which is faster
3.  It always fetches a UserProfile object which has been queried
    using `.select_related()` ([see above](#avoid-excessive-database-queries)!),
    and thus will perform well when one later accesses related models
    like the Realm.

Similarly we have `get_client` and `access_stream_by_id` /
`access_stream_by_name` functions to fetch those commonly accessed
objects via remote cache.

### Don't use Django model objects as keys in sets/dicts

Don't use Django model objects as keys in sets/dictionaries -- you will
get unexpected behavior when dealing with objects obtained from
different database queries:

For example, the following will, surprisingly, fail:

```python
# Bad example -- will raise!
obj: UserProfile = get_user_profile_by_id(17)
some_objs = UserProfile.objects.get(id=17)
assert obj in set([some_objs])
```

You should work with the IDs instead:

```python
obj: UserProfile = get_user_profile_by_id(17)
some_objs = UserProfile.objects.get(id=17)
assert obj.id in set([o.id for o in some_objs])
```

### Don't call user_profile.save() without `update_fields`

You should always pass the `update_fields` keyword argument to `.save()`
when modifying an existing Django model object. By default, `.save()` will
overwrite every value in the column, which results in lots of race
conditions where unrelated changes made by one thread can be
accidentally overwritten by another thread that fetched its `UserProfile`
object before the first thread wrote out its change.

### Don't update important model objects with raw saves

In most cases, we already have a function in `zerver.actions` with
a name like `do_activate_user` that will correctly handle lookups,
caching, and notifying running browsers via the event system about your
change. So please check whether such a function exists before writing
new code to modify a model object, since your new code has a good chance
of getting at least one of these things wrong.

### Don't use naive datetime objects

Python allows datetime objects to not have an associated time zone, which can
cause time-related bugs that are hard to catch with a test suite, or bugs
that only show up during daylight saving time.

Good ways to make time-zone-aware datetimes are below. We import time zone
libraries as `from datetime import datetime, timezone` and
`from django.utils.timezone import now as timezone_now`.

Use:

- `timezone_now()` to get a datetime when Django is available, such as
  in `zerver/`.
- `datetime.now(tz=timezone.utc)` when Django is not available, such as
  for bots and scripts.
- `datetime.fromtimestamp(timestamp, tz=timezone.utc)` if creating a
  datetime from a timestamp. This is also available as
  `zerver.lib.timestamp.timestamp_to_datetime`.
- `datetime.strptime(date_string, format).replace(tzinfo=timezone.utc)` if
  creating a datetime from a formatted string that is in UTC.

Idioms that result in time-zone-naive datetimes, and should be avoided, are
`datetime.now()` and `datetime.fromtimestamp(timestamp)` without a `tz`
parameter, `datetime.utcnow()` and `datetime.utcfromtimestamp()`, and
`datetime.strptime(date_string, format)` without replacing the `tzinfo` at
the end.

Additional notes:

- Especially in scripts and puppet configuration where Django is not
  available, using `time.time()` to get timestamps can be cleaner than
  dealing with datetimes.
- All datetimes on the backend should be in UTC, unless there is a good
  reason to do otherwise.

## Dangerous constructs in JavaScript and TypeScript

### Do not use `for...in` statements to traverse arrays

That construct pulls in properties inherited from the prototype chain.
Don't use it:
[[1]](https://stackoverflow.com/questions/500504/javascript-for-in-with-arrays),
[[2]](https://google.github.io/styleguide/javascriptguide.xml#for-in_loop),
[[3]](https://www.jslint.com/help.html#forin)
