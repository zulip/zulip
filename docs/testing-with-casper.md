# Web frontend black-box casperjs tests

These live in `frontend_tests/casper_tests/`. This is a "black box"
test; we load the frontend in a real (headless) browser, from a real dev
server, and simulate UI interactions like sending messages, narrowing,
etc.

Since this is interacting with a real dev server, it can catch backend
bugs as well.

You can run this with `./tools/test-js-with-casper` or as
`./tools/test-js-with-casper 06-settings.js` to run a single test file
from `frontend_tests/casper_tests/`.

## Debugging Casper.JS

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

## Writing Casper tests

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

