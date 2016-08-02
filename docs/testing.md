# Testing and writing tests

We have three major test suites in our codebase:
- **Django** (aka backend tests, aka Python tests)
- **zjsunit** (aka js unit tests, aka node tests)
- **Casper** (aka end-to-end tests)

Click the following link for the zjsunit docs: [zjsunit](zjsunit.html).

## Running tests


To run the full Zulip test suite, do this:
```
./tools/test-all
```

Zulip tests must be run inside a Zulip development environment; if
you're using Vagrant, you will need to enter the Vagrant environment
before running the tests:

```
vagrant ssh
cd /srv/zulip
```

This runs the linter (`tools/lint-all`) plus all of our test suites;
they can all be run separately (just read `tools/test-all` to see
them).  You can also run individual tests which can save you a lot of
time debugging a test failure, e.g.:

```
./tools/lint-all # Runs all the linters in parallel
./tools/test-backend zerver.tests.test_bugdown.BugdownTest.test_inline_youtube
./tools/test-js-with-casper 09-navigation.js
./tools/test-js-with-node utils.js
```
The above setup instructions include the first-time setup of test
databases, but you may need to rebuild the test database occasionally
if you're working on new database migrations.  To do this, run:

```
./tools/do-destroy-rebuild-test-database
```

### Possible testing issues

- When running the test suite, if you get an error like this:

  ```
      sqlalchemy.exc.ProgrammingError: (ProgrammingError) function ts_match_locs_array(unknown, text, tsquery) does not   exist
      LINE 2: ...ECT message_id, flags, subject, rendered_content, ts_match_l...
                                                                   ^
  ```

  … then you need to install tsearch-extras, described
  above. Afterwards, re-run the `init*-db` and the
  `do-destroy-rebuild*-database` scripts.

- When building the development environment using Vagrant and the LXC
  provider, if you encounter permissions errors, you may need to
  `chown -R 1000:$(whoami) /path/to/zulip` on the host before running
  `vagrant up` in order to ensure that the synced directory has the
  correct owner during provision. This issue will arise if you run `id
  username` on the host where `username` is the user running Vagrant
  and the output is anything but 1000.
  This seems to be caused by Vagrant behavior; for more information,
  see [the vagrant-lxc FAQ entry about shared folder permissions][lxc-sf].

[lxc-sf]: https://github.com/fgrehm/vagrant-lxc/wiki/FAQ#help-my-shared-folders-have-the-wrong-owner


## Schema and initial data changes

If you change the database schema or change the initial test data, you
have to regenerate the pristine test database by running
`tools/do-destroy-rebuild-test-database`.

## Wiping the test databases

You should first try running: `tools/do-destroy-rebuild-test-database`

If that fails you should try to do:

    sudo -u postgres psql
    > DROP DATABASE zulip_test;
    > DROP DATABASE zulip_test_template;

and then run `tools/do-destroy-rebuild-test-database`

### Recreating the postgres cluster

> **warning**
>
> **This is irreversible, so do it with care, and never do this anywhere
> in production.**

If your postgres cluster (collection of databases) gets totally trashed
permissions-wise, and you can't otherwise repair it, you can recreate
it. On Ubuntu:

    sudo pg_dropcluster --stop 9.1 main
    sudo pg_createcluster --locale=en_US.utf8 --start 9.1 main

## Backend Django tests

These live in `zerver/tests/tests.py` and `zerver/tests/test_*.py`. Run
them with `tools/test-backend`.

## Web frontend black-box casperjs tests

These live in `frontend_tests/casper_tests/`. This is a "black box"
test; we load the frontend in a real (headless) browser, from a real dev
server, and simulate UI interactions like sending messages, narrowing,
etc.

Since this is interacting with a real dev server, it can catch backend
bugs as well.

You can run this with `./tools/test-js-with-casper` or as
`./tools/test-js-with-casper 06-settings.js` to run a single test file
from `frontend_tests/casper_tests/`.

#### Debugging Casper.JS

Casper.js (via PhantomJS) has support for remote debugging. However, it
is not perfect. Here are some steps for using it and gotchas you might
want to know.

To turn on remote debugging, pass `--remote-debug` to the
`./frontend_tests/run-casper` script. This will run the tests with port
`7777` open for remote debugging. You can now connect to
`localhost:7777` in a Webkit browser. Somewhat recent versions of Chrome
or Safari might be required.

-   When connecting to the remote debugger, you will see a list of
    pages, probably 2. One page called `about:blank` is the headless
    page in which the CasperJS test itself is actually running in. This
    is where your test code is.
-   The other page, probably `localhost:9981`, is the Zulip page that
    the test is testing---that is, the page running our app that our
    test is exercising.

Since the tests are now running, you can open the `about:blank` page,
switch to the Scripts tab, and open the running `0x-foo.js` test. If you
set a breakpoint and it is hit, the inspector will pause and you can do
your normal JS debugging. You can also put breakpoints in the Zulip
webpage itself if you wish to inspect the state of the Zulip frontend.

You can also check the screenshots of failed tests at `/tmp/casper-failure*.png`.

If you need to use print debugging in casper, you can do using
`casper.log`; see <http://docs.casperjs.org/en/latest/logging.html> for
details.

An additional debugging technique is to enable verbose mode in the
Casper tests; you can do this by adding to the top of the relevant test
file the following:

>     var casper = require('casper').create({
>        verbose: true,
>        logLevel: "debug"
>     });

This can sometimes give insight into exactly what's happening.

## Writing tests

### Writing Casper tests

Probably the easiest way to learn how to write Casper tests is to study
some of the existing test files. There are a few tips that can be useful
for writing Casper tests in addition to the debugging notes below:

-   Run just the file containing your new tests as described above to
    have a fast debugging cycle.
-   With frontend tests in general, it's very important to write your
    code to wait for the right events. Before essentially every action
    you take on the page, you'll want to use `waitForSelector`,
    `waitUntilVisible`, or a similar function to make sure the page or
    elemant is ready before you interact with it. For instance, if you
    want to click a button that you can select via `#btn-submit`, and
    then check that it causes `success-elt` to appear, you'll want to
    write something like:

        casper.waitForSelector("#btn-submit", function () {
           casper.click('#btn-submit')
           casper.test.assertExists("#success-elt");
         });

    This will ensure that the element is present before the interaction
    is attempted. The various wait functions supported in Casper are
    documented in the Casper here:
    <http://docs.casperjs.org/en/latest/modules/casper.html#waitforselector>
    and the various assert statements available are documented here:
    <http://docs.casperjs.org/en/latest/modules/tester.html#the-tester-prototype>

- The 'waitFor' style functions (waitForSelector, etc.) cannot be
    chained together in certain conditions without creating race
    conditions where the test may fail nondeterministically. For
    example, don't do this:

        casper.waitForSelector('tag 1');
        casper.waitForSelector('tag 2');

    Instead, if you want to avoid race condition, wrap the second
    `waitFor` in a `then` function like this:

        casper.waitForSelector('tag 1');
        casper.then(function () {
            casper.waitForSelector('tag 2');
        });

-   Casper uses CSS3 selectors; you can often save time by testing and
    debugging your selectors on the relevant page of the Zulip
    development app in the Chrome JavaScript console by using e.g.
    `$$("#settings-dropdown")`.
-   The test suite uses a smaller set of default user accounts and other
    data initialized in the database than the development environment;
    to see what differs check out the section related to
    `options["test_suite"]` in
    `zilencer/management/commands/populate_db.py`.
-   Casper effectively runs your test file in two phases -- first it
    runs the code in the test file, which for most test files will just
    collect a series of steps (each being a `casper.then` or
    `casper.wait...` call). Then, usually at the end of the test file,
    you'll have a `casper.run` call which actually runs that series of
    steps. This means that if you write code in your test file outside a
    `casper.then` or `casper.wait...` method, it will actually run
    before all the Casper test steps that are declared in the file,
    which can lead to confusing failures where the new code you write in
    between two `casper.then` blocks actually runs before either of
    them. See this for more details about how Casper works:
    <http://docs.casperjs.org/en/latest/faq.html#how-does-then-and-the-step-stack-work>

## Manual testing (local app + web browser)

### Clearing the manual testing database

You can use:

    ./tools/do-destroy-rebuild-database

to drop the database on your development environment and repopulate
your it with the Shakespeare characters and some test messages between
them.  This is run automatically as part of the development
environment setup process, but is occasionally useful when you want to
return to a clean state for testing.

### JavaScript manual testing

`debug.js` has some tools for profiling JavaScript code, including:

-   \`print\_elapsed\_time\`: Wrap a function with it to print the time
    that function takes to the JavaScript console.
-   \`IterationProfiler\`: Profile part of looping constructs (like a
    for loop or \$.each). You mark sections of the iteration body and
    the IterationProfiler will sum the costs of those sections over all
    iterations.

Chrome has a very good debugger and inspector in its developer tools.
Firebug for Firefox is also pretty good. They both have profilers, but
Chrome's is a sampling profiler while Firebug's is an instrumenting
profiler. Using them both can be helpful because they provide different
information.

## Python 3 Compatibility

Zulip is working on supporting Python 3, and all new code in Zulip
should be Python 2+3 compatible. We have converted most of the codebase
to be compatible with Python 3 using a suite of 2to3 conversion tools
and some manual work. In order to avoid regressions in that
compatibility as we continue to develop new features in Zulip, we have a
special tool, `tools/check-py3`, which checks all code for Python 3
syntactic compatibility by running a subset of the automated migration
tools and checking if they trigger any changes. `tools/check-py3` is run
automatically in Zulip's Travis CI tests (in the 'static-analysis'
build) to avoid any regressions, but is not included in `test-all` since
it is quite slow.

To run `tools/check-py3`, you need to install the `modernize` and
`future` Python packages (which are included in
`requirements/py3k.txt`, which itself is included in
`requirements/dev.txt`, so you probably already have these packages
installed).

To run `check-py3` on just the Python files in a particular directory, you
can change the current working directory (e.g. `cd zerver/`) and run
`check-py3` from there.
