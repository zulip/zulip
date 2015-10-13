=======
Testing
=======

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
``tools/do-destroy-rebuild-test-database``.

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

Backend Django tests
--------------------

These live in ``zerver/tests.py`` and ``zerver/test_*.py``. Run them
with ``tools/test-backend``.

Web frontend black-box tests
----------------------------

These live in ``frontend_tests/tests/``. This is a "black box"
test; we load the frontend in a real (headless) browser, from a real dev
server, and simulate UI interactions like sending messages, narrowing,
etc.

Since this is interacting with a real dev server, it can catch backend
bugs as well.

You can run this with ``./frontend_tests/run``. You will need
`PhantomJS <http://phantomjs.org/>`__ 1.7.0 or later.

Debugging Casper.JS
~~~~~~~~~~~~~~~~~~~

Casper.js (via PhantomJS) has support for remote debugging. However, it
is not perfect. Here are some steps for using it and gotchas you might
want to know.

To turn on remote debugging, pass ``--remote-debug`` to the
``./frontend_tests/tests/run`` script. This will run the tests with
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

Now create ``frontend_tests/node_tests/foobar.js``. At the top, require
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
frontend_tests/node directory.

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

Setting up the manual testing database
--------------------------------------

::

    ./tools/do-destroy-rebuild-database

Will populate your local database with all the usual accounts plus some
test messages involving Shakespeare characters.
