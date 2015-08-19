=======
Testing
=======

Postgres testing databases
==========================

``tools/postgres-init-test-db`` works like ``tools/postgres-init-db`` to
create the database "zulip\_test" and set up the necessary permissions.

.. attention::
   TODO: Is the below still accurate?

``tools/do-destroy-rebuild-test-database`` is an alias for
``tools/generate-fixtures --force``. Do this after creating the
postgres database.

.. note::
   Running ``generate-fixtures`` attempts to restore "zulip\_test" from
   a template database that was created. It's an unsafe copy (assumes that
   no one is writing to the template db, and that the db being copied into
   is DROP-able), so don't try to run the dev server and run tests at the
   same time, though ``generate-fixtures --force`` should make things happy
   again.

Wiping the test databases
-------------------------

You should first try running: ``tools/do-destroy-rebuild-test-database``

If that fails you should try to do:

::

    sudo -u postgres psql
    > DROP DATABASE zulip_test;
    > DROP DATABASE zulip_test_template;

and then run ``tools/do-destroy-rebuild-test-database``

Recreating the postgres cluster
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::

   **This is irreversible, so do it with care, and never do this anywhere
   in production.**

If your postgres cluster (collection of databases) gets totally trashed
permissions-wise, and you can't otherwise repair it, you can recreate
it. On Ubuntu:

::

    sudo pg_dropcluster --stop 9.1 main
    sudo pg_createcluster --locale=en_US.utf8 --start 9.1 main

Running tests
=============

To run everything, just use ``./tools/test-all``. This runs lint checks,
web frontend / whole-system blackbox tests, and backend Django tests.

If you want to run individual parts, see the various commands inside
that script.

Schema and initial data changes
-------------------------------

If you change the database schema or change the initial test data, you
have have to regenerate the pristine test database by running
``tools/generate-fixtures --force``.

Writing tests
=============

We have a list of `test cases to write <Test%20cases%20to%20write>`__.

Backend Django tests
--------------------

These live in ``zerver/tests.py`` and ``zerver/test_*.py``. Run them
with ``tools/test-backend``.

Web frontend black-box tests
----------------------------

These live in ``zerver/tests/frontend/tests/``. This is a "black box"
test; we load the frontend in a real (headless) browser, from a real dev
server, and simulate UI interactions like sending messages, narrowing,
etc.

Since this is interacting with a real dev server, it can catch backend
bugs as well.

You can run this with ``./zerver/tests/frontend/run``. You will need
`PhantomJS <http://phantomjs.org/>`__ 1.7.0 or later.

Debugging Casper.JS
~~~~~~~~~~~~~~~~~~~

Casper.js (via PhantomJS) has support for remote debugging. However, it
is not perfect. Here are some steps for using it and gotchas you might
want to know.

To turn on remote debugging, pass ``--remote-debug`` to the
``./zerver/frontend/tests/run`` script. This will run the tests with
port ``7777`` open for remote debugging. You can now connect to
``localhost:7777`` in a Webkit browser. Somewhat recent versions of
Chrome or Safari might be required.

-  When connecting to the remote debugger, you will see a list of pages,
   probably 2. One page called ``about:blank`` is the headless page in
   which the CasperJS test itself is actually running in. This is where
   your test code is.
-  The other page, probably ``localhost:9981``, is the Zulip page that
   the test is testing---that is, the page running our app that our test
   is exercising.

Since the tests are now running, you can open the ``about:blank`` page,
switch to the Scripts tab, and open the running ``0x-foo.js`` test. If
you set a breakpoint and it is hit, the inspector will pause and you can
do your normal JS debugging. You can also put breakpoints in the Zulip
webpage itself if you wish to inspect the state of the Zulip frontend.

Web frontend unit tests
-----------------------

As an alternative to the black-box whole-app testing, you can unit test
individual JavaScript files that use the module pattern. For example, to
test the ``foobar.js`` file, you would first add the following to the
bottom of ``foobar.js``:

  ::

     if (typeof module !== 'undefined') {
         module.exports = foobar;
     }

This makes ``foobar.js`` follow the CommonJS module pattern, so it can
be required in Node.js, which runs our tests.

Now create ``zerver/tests/frontend/node/foobar.js``. At the top, require
the `Node.js assert module <http://nodejs.org/api/assert.html>`__, and
the module you're testing, like so:

  ::

     var assert = require('assert');
     var foobar = require('js/foobar.js');

(If the module you're testing depends on other modules, or modifies
global state, you need to also read `the next section`__.)

__ handling-dependencies_

Define and call some tests using the `assert
module <http://nodejs.org/api/assert.html>`__. Note that for "equal"
asserts, the *actual* value comes first, the *expected* value second.

  ::

     (function test_somefeature() {
         assert.strictEqual(foobar.somefeature('baz'), 'quux');
         assert.throws(foobar.somefeature('Invalid Input'));
     }());

The test runner (index.js) automatically runs all .js files in the
zerver/tests/frontend/node directory.

.. _handling-dependencies:

Handling dependencies in tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following scheme helps avoid tests leaking globals between each
other.

First, if you can avoid globals, do it, and the code that is directly
under test can simply be handled like this:

  ::

        var search = require('js/search_suggestion.js');

For deeper dependencies, you want to categorize each module as follows:

-  Exercise the module's real code for deeper, more realistic testing?
-  Stub out the module's interface for more control, speed, and
   isolation?
-  Do some combination of the above?

For all the modules where you want to run actual code, add a statement
like the following to the top of your test file:

  ::

     add_dependencies({
         _: 'third/underscore/underscore.js',
         util: 'js/util.js',
         Dict: 'js/dict.js',
         Handlebars: 'handlebars',
         Filter: 'js/filter.js',
         typeahead_helper: 'js/typeahead_helper.js',
         stream_data: 'js/stream_data.js',
         narrow: 'js/narrow.js'
     });

For modules that you want to completely stub out, please use a pattern
like this:

  ::

     set_global('page_params', {
         email: 'bob@zulip.com'
     });

     // then maybe further down
     global.page_params.email = 'alice@zulip.com';

Finally, there's the hybrid situation, where you want to borrow some of
a module's real functionality but stub out other pieces. Obviously, this
is a pretty strong smell that the other module might be lacking in
cohesion, but that code might be outside your jurisdiction. The pattern
here is this:

  ::

     // Use real versions of parse/unparse
     var narrow = require('js/narrow.js');
     set_global('narrow', {
         parse: narrow.parse,
         unparse: narrow.unparse
     });

     // But later, I want to stub the stream without having to call super-expensive
     // real code like narrow.activate().
     global.narrow.stream = function () {
         return 'office';
     };

Coverage reports
~~~~~~~~~~~~~~~~

You can automatically generate coverage reports for the JavaScript unit
tests. To do so, install istanbul:

  ::

     sudo npm install -g istanbul

And run test-js-with-node with the 'cover' parameter:

  ::

     tools/test-js-with-node cover

Then open ``coverage/lcov-report/js/index.html`` in your browser.
Modules we don't test *at all* aren't listed in the report, so this
tends to overstate how good our overall coverage is, but it's accurate
for individual files. You can also click a filename to see the specific
statements and branches not tested. 100% branch coverage isn't
necessarily possible, but getting to at least 80% branch coverage is a
good goal.

Manual testing (local app + web browser)
========================================

Setting up the test database
----------------------------

::

    ./tools/do-destroy-rebuild-database

Will populate your local database with all the usual accounts plus some
test messages involving Shakespeare characters.

Testing signups
---------------

The logic behind signups is dependent on the setting of
``ALLOW_REGISTER``; if ``True``, any email on any domain can be used to
register, if ``False``, only emails which belong to already extant
realms can register [#]_.

.. [#]
   If ``ALLOW_REGISTER`` is ``False``, MIT users cannot register at all
   unless they already have an account created via Zephyr mirroring and are
   activated by us.

Normal user creation
~~~~~~~~~~~~~~~~~~~~

#. Visit ``/accounts/home/`` and enter an email address of
   ``<something random>@zulip.com``.
#. Check the console where you're running ``run-dev`` for the email, and
   copy-paste the link, changing the hostname from ``example.com``.
#. Fill out the signup form.

You should be sent to the Zulip app after hitting "Register".

Realm creation control
~~~~~~~~~~~~~~~~~~~~~~

#. Set ``ALLOW_REGISTER = False``.
#. Try to sign up with ``alice@example.net``.
#. Try to sign up with ``zulip@mit.edu``.

You should get an error message for both.

MIT user activation
~~~~~~~~~~~~~~~~~~~

TODO: Do we want to keep this content?

Mailing list synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When new users are created an event is dispatched to the ``signups``
RabbitMQ queue. The ``subscribe_new_users`` ``manage.py`` command
attaches to this queue as a consumer and makes the appropriate calls to
Mailchimp. To test this, you need to have RabbitMQ installed and
configured on your workstation as well as the ``postmonkey`` library.

Then, keep ``python manage.py subscribe_new_users`` running while
signing up a user and ask somebody to confirm that a user was in fact
subscribed on MailChimp. TODO: split tests off into a separate list.
