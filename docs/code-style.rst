==========================
Code style and conventions
==========================

Be consistent!
==============

Look at the surrounding code, or a similar part of the project, and
try to do the same thing. If you think the other code has actively bad
style, fix it (in a separate commit).

When in doubt, send an email to zulip-devel@googlegroups.com with your
question.

Lint tools
==========

You can run them all at once with

::

    ./tools/lint-all

You can set this up as a local Git commit hook with

::

    ``tools/setup-git-repo``

The Vagrant setup process runs this for you.

``lint-all`` runs many lint checks in parallel, including

- Javascript (`JSLint <http://www.jslint.com/>`__)

    ``tools/jslint/check-all.js`` contains a pretty fine-grained set of
    JSLint options, rule exceptions, and allowed global variables. If you
    add a new global, you'll need to add it to the list.

- Python (`Pyflakes <http://pypi.python.org/pypi/pyflakes>`__)
- templates
- Puppet configuration
- custom checks (e.g. trailing whitespace and spaces-not-tabs)

Secrets
=======

Please don't put any passwords, secret access keys, etc. inline in the
code.  Instead, use the ``get_secret`` function in
``zproject/settings.py`` to read secrets from ``/etc/zulip/secrets.conf``.

Dangerous constructs
====================

Misuse of database queries
--------------------------

Look out for Django code like this::

   [Foo.objects.get(id=bar.x.id)
   for bar in Bar.objects.filter(...)
   if  bar.baz < 7]

This will make one database query for each ``Bar``, which is slow in
production (but not in local testing!). Instead of a list comprehension,
write a single query using Django's `QuerySet
API <https://docs.djangoproject.com/en/dev/ref/models/querysets/>`__.

If you can't rewrite it as a single query, that's a sign that something
is wrong with the database schema. So don't defer this optimization when
performing schema changes, or else you may later find that it's
impossible.

UserProfile.objects.get() / Client.objects.get / etc.
-----------------------------------------------------

In our Django code, never do direct
``UserProfile.objects.get(email=foo)`` database queries. Instead always
use ``get_user_profile_by_{email,id}``. There are 3 reasons for this:

#. It's guaranteed to correctly do a case-inexact lookup
#. It fetches the user object from remote cache, which is faster
#. It always fetches a UserProfile object which has been queried using
   .selected\_related(), and thus will perform well when one later
   accesses related models like the Realm.

Similarly we have ``get_client`` and ``get_stream`` functions to fetch
those commonly accessed objects via remote cache.

Using Django model objects as keys in sets/dicts
------------------------------------------------

Don't use Django model objects as keys in sets/dictionaries -- you will
get unexpected behavior when dealing with objects obtained from
different database queries:

For example,
``UserProfile.objects.only("id").get(id=17) in set([UserProfile.objects.get(id=17)])``
is False

You should work with the IDs instead.

user\_profile.save()
--------------------

You should always pass the update\_fields keyword argument to .save()
when modifying an existing Django model object. By default, .save() will
overwrite every value in the column, which results in lots of race
conditions where unrelated changes made by one thread can be
accidentally overwritten by another thread that fetched its UserProfile
object before the first thread wrote out its change.

Using raw saves to update important model objects
-------------------------------------------------

In most cases, we already have a function in zephyr/lib/actions.py with
a name like do\_activate\_user that will correctly handle lookups,
caching, and notifying running browsers via the event system about your
change. So please check whether such a function exists before writing
new code to modify a model object, since your new code has a good chance
of getting at least one of these things wrong.

``x.attr('zid')`` vs. ``rows.id(x)``
------------------------------------

Our message row DOM elements have a custom attribute ``zid`` which
contains the numerical message ID. **Don't access this directly as**
``x.attr('zid')`` ! The result will be a string and comparisons (e.g.
with ``<=``) will give the wrong result, occasionally, just enough to
make a bug that's impossible to track down.

You should instead use the ``id`` function from the ``rows`` module, as
in ``rows.id(x)``. This returns a number. Even in cases where you do
want a string, use the ``id`` function, as it will simplify future code
changes. In most contexts in JavaScript where a string is needed, you
can pass a number without any explicit conversion.

Javascript var
--------------

Always declare Javascript variables using ``var``::

   var x = ...;

In a function, ``var`` is necessary or else ``x`` will be a global
variable. For variables declared at global scope, this has no effect,
but we do it for consistency.

Javascript has function scope only, not block scope. This means that a
``var`` declaration inside a ``for`` or ``if`` acts the same as a
``var`` declaration at the beginning of the surrounding ``function``. To
avoid confusion, declare all variables at the top of a function.

Javascript ``for (i in myArray)``
---------------------------------

Don't use it:
`[1] <http://stackoverflow.com/questions/500504/javascript-for-in-with-arrays>`__,
`[2] <http://google-styleguide.googlecode.com/svn/trunk/javascriptguide.xml#for-in_loop>`__,
`[3] <http://www.jslint.com/lint.html#forin>`__

jQuery global state
-------------------

Don't mess with jQuery global state once the app has loaded. Code like
this is very dangerous::

   $.ajaxSetup({ async: false });
   $.get(...);
   $.ajaxSetup({ async: true });

jQuery and the browser are free to run other code while the request is
pending, which could perform other Ajax requests with the altered
settings.

Instead, switch to the more general |ajax|_ function, which can take options
like ``async``.

.. |ajax| replace:: ``$.ajax``
.. _ajax: http://api.jquery.com/jQuery.ajax

State and logs files
--------------------

Do not write state and logs files inside the current working directory
in the production environment. This will not how you expect, because the
current working directory for the app changes every time we do a deploy.
Instead, hardcode a path in settings.py -- see SERVER\_LOG\_PATH in
settings.py for an example.

JS array/object manipulation
============================

For generic functions that operate on arrays or JavaScript objects, you
should generally use `Underscore <http://underscorejs.org/>`__. We used
to use jQuery's utility functions, but the Underscore equivalents are
more consistent, better-behaved and offer more choices.

A quick conversion table::

      $.each → _.each (parameters to the callback reversed)
      $.inArray → _.indexOf (parameters reversed)
      $.grep → _.filter
      $.map → _.map
      $.extend → _.extend

There's a subtle difference in the case of ``_.extend``; it will replace
attributes with undefined, whereas jQuery won't::

      $.extend({foo: 2}, {foo: undefined});  // yields {foo: 2}, BUT...
      _.extend({foo: 2}, {foo: undefined});  // yields {foo: undefined}!

Also, ``_.each`` does not let you break out of the iteration early by
returning false, the way jQuery's version does. If you're doing this,
you probably want ``_.find``, ``_.every``, or ``_.any``, rather than
'each'.

Some Underscore functions have multiple names. You should always use the
canonical name (given in large print in the Underscore documentation),
with the exception of ``_.any``, which we prefer over the less clear
'some'.

More arbitrary style things
===========================

General
-------

Indentation is four space characters for Python, JS, CSS, and shell
scripts. Indentation is two space characters for HTML templates.

We never use tabs anywhere in source code we write, but we have some
third-party files which contain tabs.

Keep third-party static files under the directory
``zephyr/static/third/``, with one subdirectory per third-party project.

We don't have an absolute hard limit on line length, but we should avoid
extremely long lines. A general guideline is: refactor stuff to get it
under 85 characters, unless that makes the code a lot uglier, in which
case it's fine to go up to 120 or so.

Whitespace guidelines:

-  Put one space (or more for alignment) around binary arithmetic and
   equality operators.
-  Put one space around each part of the ternary operator.
-  Put one space between keywords like ``if`` and ``while`` and their
   associated open paren.
-  Put one space between the closing paren for ``if`` and ``while``-like
   constructs and the opening curly brace. Put the curly brace on the
   same line unless doing otherwise improves readability.
-  Put no space before or after the open paren for function calls and no
   space before the close paren for function calls.
-  For the comma operator and colon operator in languages where it is
   used for inline dictionaries, put no space before it and at least one
   space after. Only use more than one space for alignment.

Javascript
----------

Don't use ``==`` and ``!=`` because these operators perform type
coercions, which can mask bugs. Always use ``===`` and ``!==``.

End every statement with a semicolon.

``if`` statements with no braces are allowed, if the body is simple and
its extent is abundantly clear from context and formatting.

Anonymous functions should have spaces before and after the argument
list::

   var x = function (foo, bar) { // ...

When calling a function with an anonymous function as an argument, use
this style::

   $.get('foo', function (data) {
       var x = ...;
       // ...
   });

The inner function body is indented one level from the outer function
call. The closing brace for the inner function and the closing
parenthesis for the outer call are together on the same line. This style
isn't necessarily appropriate for calls with multiple anonymous
functions or other arguments following them.

Use

::

   $(function () { ...

rather than

::

   $(document).ready(function () { ...

and combine adjacent on-ready functions, if they are logically related.

The best way to build complicated DOM elements is a Mustache template
like ``zephyr/static/templates/message.handlebars``. For simpler things
you can use jQuery DOM building APIs like so::

   var new_tr = $('<tr />').attr('id', zephyr.id);

Passing a HTML string to jQuery is fine for simple hardcoded things::

   foo.append('<p id="selected">foo</p>');

but avoid programmatically building complicated strings.

We used to favor attaching behaviors in templates like so::

    <p onclick="select_zephyr({{id}})">

but there are some reasons to prefer attaching events using jQuery code:

-  Potential huge performance gains by using delegated events where
   possible
-  When calling a function from an ``onclick`` attribute, ``this`` is
   not bound to the element like you might think
-  jQuery does event normalization

Either way, avoid complicated JavaScript code inside HTML attributes;
call a helper function instead.

HTML / CSS
----------

Don't use the ``style=`` attribute. Instead, define logical classes and
put your styles in ``zulip.css``.

Don't use the tag name in a selector unless you have to. In other words,
use ``.foo`` instead of ``span.foo``. We shouldn't have to care if the
tag type changes in the future.

Don't use inline event handlers (``onclick=``, etc. attributes).
Instead, attach a jQuery event handler
(``$('#foo').on('click', function () {...})``) when the DOM is ready
(inside a ``$(function () {...})`` block).

Use this format when you have the same block applying to multiple CSS
styles (separate lines for each selector)::

    selector1,
    selector2 {
    };

Python
------

- Scripts should start with ``#!/usr/bin/env python`` and not
  ``#/usr/bin/python`` (the right Python may not be installed at
  /usr/bin) or ``#/usr/bin/env/python2.7`` (bad for Python 3
  compatibility).  Don't put a shebang line on a Python file unless
  it's meaningful to run it as a script. (Some libraries can also be
  run as scripts, e.g. to run a test suite.)

-  The first import in a file should be
   ``from __future__ import absolute_import``, per `PEP
   328 <http://docs.python.org/2/whatsnew/2.5.html#pep-328-absolute-and-relative-imports>`__
-  Put all imports together at the top of the file, absent a compelling
   reason to do otherwise.
-  Unpacking sequences doesn't require list brackets::

      [x, y] = xs    # unnecessary
      x, y = xs      # better

-  For string formatting, use ``x % (y,)`` rather than ``x % y``, to
   avoid ambiguity if ``y`` happens to be a tuple.
-  When selecting by id, don't use ``foo.pk`` when you mean ``foo.id``.
   E.g.

   ::

      recipient = Recipient(type_id=huddle.pk, type=Recipient.HUDDLE)

   should be written as

   ::

      recipient = Recipient(type_id=huddle.id, type=Recipient.HUDDLE)

   in case we ever change the primary keys.

Version Control
===============

Commit Discipline
-----------------

We follow the Git project's own commit discipline practice of "Each
commit is a minimal coherent idea".  This discipline takes a bit of
work, but it makes it much easier for code reviewers to spot bugs, and
makesthe commit history a much more useful resource for developers
trying to understand why the code works the way it does, which also
helps a lot in preventing bugs.

Coherency requirements for any commit:

-  It should pass tests (so test updates needed by a change should be in
   the same commit as the original change, not a separate "fix the tests
   that were broken by the last commit" commit).
-  It should be safe to deploy individually, or comment in detail in the
   commit message as to why it isn't (maybe with a [manual] tag). So
   implementing a new API endpoint in one commit and then adding the
   security checks in a future commit should be avoided -- the security
   checks should be there from the beginning.
-  Error handling should generally be included along with the code that
   might trigger the error.
-  TODO comments should be in the commit that introduces the
   issue or functionality with further work required.

When you should be minimal:

-  Significant refactorings should be done in a separate commit from
   functional changes.
-  Moving code from one file to another should be done in a separate
   commits from functional changes or even refactoring within a file.
-  2 different refactorings should be done in different commits.
-  2 different features should be done in different commits.
-  If you find yourself writing a commit message that reads like a list
   of somewhat dissimilar things that you did, you probably should have
   just done 2 commits.

When not to be overly minimal:

-  For completely new features, you don't necessarily need to split out
   new commits for each little subfeature of the new feature. E.g. if
   you're writing a new tool from scratch, it's fine to have the initial
   tool have plenty of options/features without doing separate commits
   for each one.  That said, reviewing a 2000-line giant blob of new
   code isn't fun, so please be thoughtful about submitting things in
   reviewable units.
-  Don't bother to split back end commits from front end commits, even
   though the backend can often be coherent on its own.

Other considerations:

-  Overly fine commits are easily squashed, but not vice versa, so err
   toward small commits, and the code reviewer can advise on squashing.
-  If a commit you write doesn't pass tests, you should usually fix
   that by amending the commit to fix the bug, not writing a new "fix
   tests" commit on top of it.

Zulip expects you to structure the commits in your pull requests to
form a clean history before we will merge them; it's best to write
your commits following these guidelines in the first place, but if you
don't, you can always fix your history using `git rebase -i`.

It can take some practice to get used to writing your commits with a
clean history so that you don't spend much time doing interactive
rebases.  For example, often you'll start adding a feature, and
discover you need to a refactoring partway through writing the
feature.  When that happens, we recommend stashing your partial
feature, do the refactoring, commit it, and then finish implementing
your feature.

Commit Messages
---------------

-  The first line of commit messages should be written in the imperative
   and be kept relatively short while concisely explaining what the
   commit does. For example:

Bad::

   bugfix
   gather_subscriptions was broken
   fix bug #234.

Good::

   Fix gather_subscriptions throwing an exception when given bad input.

-  Use present-tense action verbs in your commit messages.

Bad::

   Fixing gather_subscriptions throwing an exception when given bad input.
   Fixed gather_subscriptions throwing an exception when given bad input.

Good::

   Fix gather_subscriptions throwing an exception when given bad input.

-  Please use a complete sentence in the summary, ending with a
   period.

-  The rest of the commit message should be written in full prose and
   explain why and how the change was made. If the commit makes
   performance improvements, you should generally include some rough
   benchmarks showing that it actually improves the performance.

-  When you fix a GitHub issue, `mark that you've fixed the issue in
   your commit message
   <https://help.github.com/articles/closing-issues-via-commit-messages/>`__
   so that the issue is automatically closed when your code is merged.
   Zulip's preferred style for this is to have the final paragraph
   of the commit message read e.g. "Fixes: #123."

-  Any paragraph content in the commit message should be line-wrapped
   to less than 76 characters per line, so that your commit message
   will be reasonably readable in `git log` in a normal terminal.

-  In your commit message, you should describe any manual testing you
   did in addition to running the automated tests, and any aspects of
   the commit that you think are questionable and you'd like special
   attention applied to.

Tests
-----

All significant new features should come with tests. See :doc:`testing`.

Third party code
----------------

When adding new third-party packages to our codebase, please include
"[third]" at the beginning of the commit message. You don't necessarily
need to do this when patching third-party code that's already in tree.
