# Code style and conventions

## Be consistent!

Look at the surrounding code, or a similar part of the project, and try
to do the same thing. If you think the other code has actively bad
style, fix it (in a separate commit).

When in doubt, ask in [chat.zulip.org](https://chat.zulip.org).

## Lint tools

You can run them all at once with

    ./tools/lint

You can set this up as a local Git commit hook with

    ``tools/setup-git-repo``

The Vagrant setup process runs this for you.

`lint` runs many lint checks in parallel, including

-   JavaScript ([ESLint](http://eslint.org/))
-   Python ([Pyflakes](http://pypi.python.org/pypi/pyflakes))
-   templates
-   Puppet configuration
-   custom checks (e.g. trailing whitespace and spaces-not-tabs)

## Secrets

Please don't put any passwords, secret access keys, etc. inline in the
code. Instead, use the `get_secret` function in `zproject/settings.py`
to read secrets from `/etc/zulip/secrets.conf`.

## Dangerous constructs

### Misuse of database queries

Look out for Django code like this:

    [Foo.objects.get(id=bar.x.id)
    for bar in Bar.objects.filter(...)
    if  bar.baz < 7]

This will make one database query for each `Bar`, which is slow in
production (but not in local testing!). Instead of a list comprehension,
write a single query using Django's [QuerySet
API](https://docs.djangoproject.com/en/dev/ref/models/querysets/).

If you can't rewrite it as a single query, that's a sign that something
is wrong with the database schema. So don't defer this optimization when
performing schema changes, or else you may later find that it's
impossible.

### UserProfile.objects.get() / Client.objects.get / etc.

In our Django code, never do direct `UserProfile.objects.get(email=foo)`
database queries. Instead always use `get_user_profile_by_{email,id}`.
There are 3 reasons for this:

1.  It's guaranteed to correctly do a case-inexact lookup
2.  It fetches the user object from remote cache, which is faster
3.  It always fetches a UserProfile object which has been queried using
    .select\_related(), and thus will perform well when one later
    accesses related models like the Realm.

Similarly we have `get_client` and `get_stream` functions to fetch those
commonly accessed objects via remote cache.

### Using Django model objects as keys in sets/dicts

Don't use Django model objects as keys in sets/dictionaries -- you will
get unexpected behavior when dealing with objects obtained from
different database queries:

For example,
`UserProfile.objects.only("id").get(id=17) in set([UserProfile.objects.get(id=17)])`
is False

You should work with the IDs instead.

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

Good ways to make timezone-aware datetimes are below. We import `timezone`
function as `from django.utils.timezone import now as timezone_now` and
`from django.utils.timezone import utc as timezone_utc`. When Django is not
available, `timezone_utc` should be replaced with `pytz.utc` below.
* `timezone_now()` when Django is available, such as in `zerver/`.
* `datetime.now(tz=pytz.utc)` when Django is not available, such as for bots
  and scripts.
* `datetime.fromtimestamp(timestamp, tz=timezone_utc)` if creating a
  datetime from a timestamp. This is also available as
  `zerver.lib.timestamp.timestamp_to_datetime`.
* `datetime.strptime(date_string, format).replace(tzinfo=timezone_utc)` if
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

### JavaScript var

Always declare JavaScript variables using `var`.  JavaScript has
function scope only, not block scope. This means that a `var`
declaration inside a `for` or `if` acts the same as a `var`
declaration at the beginning of the surrounding `function`. To avoid
confusion, declare all variables at the top of a function.

### JavaScript `for (i in myArray)`

Don't use it:
[[1]](http://stackoverflow.com/questions/500504/javascript-for-in-with-arrays),
[[2]](https://google.github.io/styleguide/javascriptguide.xml#for-in_loop),
[[3]](http://www.jslint.com/help.html#forin)

### Translation tags

Remember to
[tag all user-facing strings for translation](../translating/translating.html), whether
they are in HTML templates or JavaScript editing the HTML (e.g. error
messages).

### State and logs files

When writing out state of log files, always declare the path in
`ZULIP_PATHS` in `zproject/settings.py`, which will do the right thing
in both development and production.

## JS array/object manipulation

For generic functions that operate on arrays or JavaScript objects, you
should generally use [Underscore](http://underscorejs.org/). We used to
use jQuery's utility functions, but the Underscore equivalents are more
consistent, better-behaved and offer more choices.

A quick conversion table:

       $.each → _.each (parameters to the callback reversed)
       $.inArray → _.indexOf (parameters reversed)
       $.grep → _.filter
       $.map → _.map
       $.extend → _.extend

There's a subtle difference in the case of `_.extend`; it will replace
attributes with undefined, whereas jQuery won't:

       $.extend({foo: 2}, {foo: undefined});  // yields {foo: 2}, BUT...
       _.extend({foo: 2}, {foo: undefined});  // yields {foo: undefined}!

Also, `_.each` does not let you break out of the iteration early by
returning false, the way jQuery's version does. If you're doing this,
you probably want `_.find`, `_.every`, or `_.any`, rather than 'each'.

Some Underscore functions have multiple names. You should always use the
canonical name (given in large print in the Underscore documentation),
with the exception of `_.any`, which we prefer over the less clear
'some'.

## More arbitrary style things

### Line length

We have an absolute hard limit on line length only for some files, but
we should still avoid extremely long lines. A general guideline is:
refactor stuff to get it under 85 characters, unless that makes the
code a lot uglier, in which case it's fine to go up to 120 or so.

### JavaScript

When calling a function with an anonymous function as an argument, use
this style:

    my_function('foo', function (data) {
        var x = ...;
        // ...
    });

The inner function body is indented one level from the outer function
call. The closing brace for the inner function and the closing
parenthesis for the outer call are together on the same line. This style
isn't necessarily appropriate for calls with multiple anonymous
functions or other arguments following them.

Combine adjacent on-ready functions, if they are logically related.

The best way to build complicated DOM elements is a Mustache template
like `static/templates/message_reactions.handlebars`. For simpler things
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

All significant new features should come with tests. See testing.

### Third party code

See [our docs on dependencies](../subsystems/dependencies.html) for discussion of
rules about integrating third-party projects.
