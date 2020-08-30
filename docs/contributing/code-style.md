# Code style and conventions

One can summarize Zulip's coding philosophy as a relentless focus on
making the codebase easy to understand and difficult to make dangerous
mistakes in.  The majority of work in any large software development
project is understanding the existing code so one can debug or modify
it, and investments in code readability usually end up paying for
themselves when someone inevitably needs to debug or improve the code.

When there's something subtle or complex to explain or ensure in the
implementation, we try hard to make it clear, through a combination of
clean and intuitive interfaces, well-named variables and functions,
comments/docstrings, and commit messages (roughly in order of priority
-- if you can make something clear with a good interface, that's a lot
better than writing a comment explaining how the bad interface works).

This page documents code style policies that every Zulip developer
should understand.  We aim for this document to be short and focused
only on details that cannot be easily enforced another way (e.g.
through linters, automated tests, subsystem design that makes classes
of mistakes unlikely, etc.).  This approach minimizes the cognitive
load of ensuring a consistent coding style for both contributors and
maintainers.

## Be consistent!

Look at the surrounding code, or a similar part of the project, and try
to do the same thing. If you think the other code has actively bad
style, fix it (in a separate commit).

When in doubt, ask in [chat.zulip.org](https://chat.zulip.org).

## Lint tools

You can run them all at once with

    ./tools/lint

You can set this up as a local Git commit hook with

    tools/setup-git-repo

The Vagrant setup process runs this for you.

`lint` runs many lint checks in parallel, including

-   JavaScript ([ESLint](https://eslint.org/))
-   Python ([Pyflakes](https://pypi.python.org/pypi/pyflakes))
-   templates
-   Puppet configuration
-   custom checks (e.g. trailing whitespace and spaces-not-tabs)

## Secrets

Please don't put any passwords, secret access keys, etc. inline in the
code. Instead, use the `get_secret` function in `zproject/config.py`
to read secrets from `/etc/zulip/secrets.conf`.

## Dangerous constructs

### Too many database queries

Look out for Django code like this:

    bars = Bar.objects.filter(...)
    for bar in bars:
        foo = bar.foo
        # Make use of foo

...because it equates to:

    bars = Bar.objects.filter(...)
    for bar in bars:
        foo = Foo.objects.get(id=bar.foo.id)
        # Make use of foo

...which makes a database query for every Bar.  While this may be fast
locally in development, it may be quite slow in production!  Instead,
tell Django's [QuerySet
API](https://docs.djangoproject.com/en/dev/ref/models/querysets/) to
_prefetch_ the data in the initial query:

    bars = Bar.objects.filter(...).select_related()
    for bar in bars:
        foo = bar.foo  # This doesn't take another query, now!
        # Make use of foo

If you can't rewrite it as a single query, that's a sign that something
is wrong with the database schema. So don't defer this optimization when
performing schema changes, or else you may later find that it's
impossible.

### UserProfile.objects.get() / Client.objects.get() / etc.

In our Django code, never do direct `UserProfile.objects.get(email=foo)`
database queries. Instead always use `get_user_profile_by_{email,id}`.
There are 3 reasons for this:

1.  It's guaranteed to correctly do a case-inexact lookup
2.  It fetches the user object from remote cache, which is faster
3.  It always fetches a UserProfile object which has been queried
    using `.select_related()` (see above!), and thus will perform well
    when one later accesses related models like the Realm.

Similarly we have `get_client` and `access_stream_by_id` /
`access_stream_by_name` functions to fetch those commonly accessed
objects via remote cache.

### Using Django model objects as keys in sets/dicts

Don't use Django model objects as keys in sets/dictionaries -- you will
get unexpected behavior when dealing with objects obtained from
different database queries:

For example, the following will, surprisingly, fail:

```
# Bad example -- will raise!
obj: UserProfile = get_user_profile_by_id(17)
some_objs = UserProfile.objects.get(id=17)
assert obj in set([some_objs])
```

You should work with the IDs instead:

```
obj: UserProfile = get_user_profile_by_id(17)
some_objs = UserProfile.objects.get(id=17)
assert obj.id in set([o.id for i in some_objs])
```

### user\_profile.save()

You should always pass the update\_fields keyword argument to .save()
when modifying an existing Django model object. By default, .save() will
overwrite every value in the column, which results in lots of race
conditions where unrelated changes made by one thread can be
accidentally overwritten by another thread that fetched its UserProfile
object before the first thread wrote out its change.

### Using raw saves to update important model objects

In most cases, we already have a function in zerver/lib/actions.py with
a name like do\_activate\_user that will correctly handle lookups,
caching, and notifying running browsers via the event system about your
change. So please check whether such a function exists before writing
new code to modify a model object, since your new code has a good chance
of getting at least one of these things wrong.

### Naive datetime objects

Python allows datetime objects to not have an associated timezone, which can
cause time-related bugs that are hard to catch with a test suite, or bugs
that only show up during daylight savings time.

Good ways to make timezone-aware datetimes are below. We import timezone
libraries as `from datetime import datetime, timezone` and `from
django.utils.timezone import now as timezone_now`.

Use:
* `timezone_now()` to get a datetime when Django is available, such as
  in `zerver/`.
* `datetime.now(tz=timezone.utc)` when Django is not available, such as
  for bots and scripts.
* `datetime.fromtimestamp(timestamp, tz=timezone.utc)` if creating a
  datetime from a timestamp. This is also available as
  `zerver.lib.timestamp.timestamp_to_datetime`.
* `datetime.strptime(date_string, format).replace(tzinfo=timezone.utc)` if
  creating a datetime from a formatted string that is in UTC.

Idioms that result in timezone-naive datetimes, and should be avoided, are
`datetime.now()` and `datetime.fromtimestamp(timestamp)` without a `tz`
parameter, `datetime.utcnow()` and `datetime.utcfromtimestamp()`, and
`datetime.strptime(date_string, format)` without replacing the `tzinfo` at
the end.

Additional notes:
* Especially in scripts and puppet configuration where Django is not
  available, using `time.time()` to get timestamps can be cleaner than
  dealing with datetimes.
* All datetimes on the backend should be in UTC, unless there is a good
  reason to do otherwise.

### `x.attr('zid')` vs. `rows.id(x)`

Our message row DOM elements have a custom attribute `zid` which
contains the numerical message ID. **Don't access this directly as**
`x.attr('zid')` ! The result will be a string and comparisons (e.g. with
`<=`) will give the wrong result, occasionally, just enough to make a
bug that's impossible to track down.

You should instead use the `id` function from the `rows` module, as in
`rows.id(x)`. This returns a number. Even in cases where you do want a
string, use the `id` function, as it will simplify future code changes.
In most contexts in JavaScript where a string is needed, you can pass a
number without any explicit conversion.

### JavaScript `const` and `let`

Always declare JavaScript variables using `const` or `let` rather than
`var`.

### JavaScript and TypeScript `for (i in myArray)`

Don't use it:
[[1]](https://stackoverflow.com/questions/500504/javascript-for-in-with-arrays),
[[2]](https://google.github.io/styleguide/javascriptguide.xml#for-in_loop),
[[3]](https://www.jslint.com/help.html#forin)

### Translation tags

Remember to
[tag all user-facing strings for translation](../translating/translating.md), whether
they are in HTML templates or JavaScript/TypeScript editing the HTML (e.g. error
messages).

### Paths to state or log files

When writing out state or log files, always pass an absolute path
through `zulip_path` (found in `zproject/computed_settings.py`), which
will do the right thing in both development and production.

## JS array/object manipulation

For functions that operate on arrays or JavaScript objects, you should
generally use modern
[ECMAScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Language_Resources)
primitives such as [`for … of`
loops](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/for...of),
[`Array.prototype.{entries, every, filter, find, indexOf, map,
some}`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array),
[`Object.{assign, entries, keys,
values}`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object),
[spread
syntax](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Spread_syntax),
and so on. Our Babel configuration automatically transpiles and
polyfills these using [`core-js`](https://github.com/zloirock/core-js)
when necessary. We used to use the
[Underscore](https://underscorejs.org/) library, but that should be
avoided in new code.

## More arbitrary style things

### Line length

We have an absolute hard limit on line length only for some files, but
we should still avoid extremely long lines. A general guideline is:
refactor stuff to get it under 85 characters, unless that makes the
code a lot uglier, in which case it's fine to go up to 120 or so.

### JavaScript and TypeScript

Our JavaScript and TypeScript code is formatted with
[Prettier](https://prettier.io/).  You can ask Prettier to reformat
all code via our [linter tool](../testing/linters.md) with `tools/lint
--only=prettier --fix`.  You can also [integrate it with your
editor](https://prettier.io/docs/en/editors.html).

Combine adjacent on-ready functions, if they are logically related.

The best way to build complicated DOM elements is a Mustache template
like `static/templates/message_reactions.hbs`. For simpler things
you can use jQuery DOM building APIs like so:

    var new_tr = $('<tr />').attr('id', object.id);

Passing a HTML string to jQuery is fine for simple hardcoded things
that don't need internationalization:

    foo.append('<p id="selected">/</p>');

but avoid programmatically building complicated strings.

We used to favor attaching behaviors in templates like so:

    <p onclick="select_zerver({{id}})">

but there are some reasons to prefer attaching events using jQuery code:

-   Potential huge performance gains by using delegated events where
    possible
-   When calling a function from an `onclick` attribute, `this` is not
    bound to the element like you might think
-   jQuery does event normalization

Either way, avoid complicated JavaScript code inside HTML attributes;
call a helper function instead.

### HTML / CSS

Our CSS is formatted with [Prettier](https://prettier.io/).  You can
ask Prettier to reformat all code via our [linter
tool](../testing/linters.md) with `tools/lint --only=prettier --fix`.
You can also [integrate it with your
editor](https://prettier.io/docs/en/editors.html).

Avoid using the `style=` attribute unless the styling is actually
dynamic. Instead, define logical classes and put your styles in
external CSS files such as `zulip.css`.

Don't use the tag name in a selector unless you have to. In other words,
use `.foo` instead of `span.foo`. We shouldn't have to care if the tag
type changes in the future.

### Python

-   Don't put a shebang line on a Python file unless it's meaningful to
    run it as a script. (Some libraries can also be run as scripts, e.g.
    to run a test suite.)
-   Scripts should be executed directly (`./script.py`), so that the
    interpreter is implicitly found from the shebang line, rather than
    explicitly overridden (`python script.py`).
-   Put all imports together at the top of the file, absent a compelling
    reason to do otherwise.
-   Unpacking sequences doesn't require list brackets:

        [x, y] = xs    # unnecessary
        x, y = xs      # better

-   For string formatting, use `x % (y,)` rather than `x % y`, to avoid
    ambiguity if `y` happens to be a tuple.

### Tests

Clear, readable code is important for [tests](../testing/testing.md);
familiarize yourself with our testing frameworks so that you can write
clean, readable tests.  Comments about anything subtle about what is
being verified are appreciated.

### Third party code

See [our docs on dependencies](../subsystems/dependencies.md) for discussion of
rules about integrating third-party projects.
