# Web frontend black-box casperjs tests

These live in `frontend_tests/casper_tests/`. This is a "black box"
integration test; we load the frontend in a real (headless) browser,
from a real (development) server, and simulate UI interactions like
sending messages, narrowing, etc., by actually clicking around the UI
and waiting for things to change before doing the next step.  These
tasks are fantastic for ensuring the overall health of the project,
but are also costly to maintain and keep free of nondeterministic
failures, so we usually prefer to write a Node test instead when
possible.

Since the Casper tests interact with a real dev server, they can often
catch backend bugs as well.

You can run the casper tests with `./tools/test-js-with-casper` or as
`./tools/test-js-with-casper 06-settings.js` to run a single test file
from `frontend_tests/casper_tests/`.

## Debugging Casper.JS

Casper.js (via PhantomJS) has support for remote debugging. However, it
is not perfect. Here are some steps for using it and gotchas you might
want to know; you'll likely also want to read the section on writing
tests (below) if you get stuck, since the advice on how to write
correct Casper selectors will likely be relevant.

The first thing to do when debugging Casper tests is to check the
additional debug output that our framework provides:
* You can check the screenshots of what the UI looked like at the time
  of failures at `var/casper/casper-failure*.png`.
* If it's possible there's a backend exception involved,
  `var/casper/server.log` will contain the server logs from the casper
  run; it's worth looking there for tracebacks if you get stuck.

### Print debugging

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

### Remote debugging

This is a pain to setup with Vagrant because port `7777` and `9981`
aren't forwarded to the host by default, but can be pretty useful in
rare difficult cases.

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

### Reproducing races only seen in Travis CI

We've sometimes found it useful for reproducing Casper race conditions
in Casper tests that mostly only happen in Travis CI with really cheap
VPS servers (e.g. Scaleway's 2GB x86).  This works because an ultra
slow machine is more likely to have things happen in an order similar
to what happens in Travis CI's very slow containers.

## Writing Casper tests

Probably the easiest way to learn how to write Casper tests is to study
some of the existing test files. There are a few tips that can be useful
for writing Casper tests in addition to the debugging notes below:

-   Run just the file containing your new tests as described above to
    have a fast debugging cycle.
- With frontend tests in general, it's very important to write your
    code to wait for the right events. Before essentially every action
    you take on the page, you'll want to use `waitUntilVisible`,
    `waitWhileVisible`, or a similar function to make sure the page
    or elemant is ready before you interact with it. For instance, if
    you want to click a button that you can select via `#btn-submit`,
    and then check that it causes `success-elt` to appear, you'll want
    to write something like:

        casper.waitUntilVisible("#btn-submit", function () {
           casper.click('#btn-submit')
           casper.test.assertExists("#success-elt");
         });

    In many cases, you will actually need to wait for the UI to update
    clicking the button before doing asserts or the next step.  This
    will ensure that the UI has finished updating from the previous
    step before Casper attempts to next step. The various wait
    functions supported in Casper are documented in the Casper here:
    <http://docs.casperjs.org/en/latest/modules/casper.html#waitforselector>
    and the various assert statements available are documented here:
    <http://docs.casperjs.org/en/latest/modules/tester.html#the-tester-prototype>

-   The `casper.wait` style functions (`waitWhileVisible`,
    `waitUntilVisible`, etc.) cannot be chained together in certain
    conditions without creating race conditions where the test may
    fail nondeterministically. For example, don't do this:

        casper.waitUntilVisible('tag 1');
        casper.click('button');
        casper.waitUntilVisible('tag 2');

    Instead, if you want to avoid race condition, wrap the second
    `waitFor` in a `then` function like this:

        casper.then(function () {
            casper.waitUntilVisible('tag 1', function () {
                casper.click('#btn-submit');
            });
        });
        casper.then(function () {
            casper.waitUntilVisible('tag 2', function () {
                casper.test.assertExists('#success-elt');
            });
        });

    (You'll also want to use selectors that are as explicit as
    possible, to avoid accidentally clicking multiple buttons or the
    wrong button in your test, which can cause nondeterministic failures)

- Generally `casper.waitUntilVisible` is preferable to
    e.g. `casper.waitForSelector`, since the former will confirm the
    thing is actually on screen.  E.g. if you're waiting to switch
    from one panel of the the settings overlay to another by waiting
    for a particular widget to appear, `casper.waitForSelector` may
    not actually wait (since the widget is probably in the DOM, just
    not visible), but casper.waitUntilVisible will wait until it's
    actually shown.

- The selectors (i.e. things you put inside
    `casper.waitUntilVisible()` and friends) appearing in Casper tests
    are CSS3 selectors, which is a slightly different syntax from the
    jQuery selectors used in the rest of the Zulip codebase; in
    particular, some expressions that work with jQuery (and thus
    normal Zulip JavaScript code) won't work with CSS3.  It's often
    helpful to debug selectors interactively, which you can do in the
    Chrome JavaScript console.  The way to do it is
    `$$("#settings-dropdown")`; that queries CSS3 selectors, so you
    can debug your selector in the console and then paste it into your
    Casper test once it's working.  For other browsers like Firefox,
    you can use `querySelectorAll("#settings-dropdown")`, syntax which
    is only available in the browser's JavaScript console.

    You can learn more about these selectors and other JavaScript console tools
    [here](https://developers.google.com/web/tools/chrome-devtools/console/command-line-reference).
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
