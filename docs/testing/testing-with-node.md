# JavaScript/TypeScript unit tests

Our node-based unit tests system is the preferred way to test
JavaScript/TypeScript code in Zulip. We prefer it over the [Puppeteer
black-box whole-app testing](testing-with-puppeteer.md),
system since it is much (>100x) faster and also easier to do correctly
than the Puppeteer system.

You can run this test suite as follows:

```bash
tools/test-js-with-node
```

See `test-js-with-node --help` for useful options; even though the
whole suite is quite fast, it still saves time to run a single test by
name when debugging something.

The JS unit tests are written to work with node. You can find them
in `web/tests`. Here is an example test from
`web/tests/stream_data.test.js`:

```js
(function test_get_by_id() {
    stream_data.clear_subscriptions();
    var id = 42;
    var sub = {
        name: 'Denmark',
        subscribed: true,
        color: 'red',
        stream_id: id
    };
    stream_data.add_sub('Denmark', sub);
    sub = stream_data.get_sub('Denmark');
    assert.equal(sub.color, 'red');
    sub = sub_store.get(id);
    assert.equal(sub.color, 'red');
}());
```

The names of the node tests generally align with the names of the
modules they test. If you modify a JS module in `web/src` you should
see if there are corresponding test in `web/tests`. If
there are, you should strive to follow the patterns of the existing tests
and add your own tests.

A good first test to read is
[example1.js](https://github.com/zulip/zulip/blob/main/web/tests/example1.test.js).
(And then there are several other example files.)

## How the node tests work

Unlike the [Puppeteer unit tests](testing-with-puppeteer.md),
which use a headless Chromium browser connected to a running Zulip
development server, our node unit tests don't have a browser, don't
talk to a server, and generally don't use a complete virtual DOM (a
handful of tests use the `jsdom` library for this purpose) because
those slow down the tests a lot, and often don't add much value.

Instead, the preferred model for our unit tests is to mock DOM
manipulations (which in Zulip are almost exclusively done via
`jQuery`) using a custom library
[zjquery](https://github.com/zulip/zulip/blob/main/web/tests/lib/zjquery.js).

The
[unit test file](https://github.com/zulip/zulip/blob/main/web/tests/zjquery.test.js)
for `zjquery` is designed to be also serve as nice documentation for
how to use `zjquery`, and is **highly recommended reading** for anyone
working on or debugging the Zulip node tests.

Conceptually, the `zjquery` library provides minimal versions of most
`jQuery` DOM manipulation functions, and has a convenient system for
letting you set up return values for more complex functions. For
example, if the code you'd like to test calls `$obj.find()`, you can
use `$obj.set_find_results(selector, $value)` to set up `zjquery` so
that calls to `$obj.find(selector)` will return `$value`. See the unit
test file for details.

This process of substituting `jQuery` functions with our own code for
testing purposes is known as "stubbing". `zjquery` does not stub all
possible interactions with the dom, as such, you may need to write out
the stub for a function you're calling in your patch. Typically the stub
is just placed in the test file, to prevent bloating of `zjquery`
with functions that are only used in a single test.

If you need to stub, you will see an error of this form:
`Error: You must create a stub for $("#foo").bar`

The `zjquery` library itself is only about 500 lines of code, and can
also be a useful resource if you're having trouble debugging DOM
access in the unit tests.

It is typically a good idea to figure out how to stub a given function
based on how other functions have been stubbed in the same file.

## Handling dependencies in unit tests

The other big challenge with doing unit tests for a JavaScript project
is that often one wants to limit the scope the production code being
run, just to avoid doing extra setup work that isn't relevant to the
code you're trying to test. For that reason, each unit test file
explicitly declares all of the modules it depends on, with a few
different types of declarations depending on whether we want to:

- Exercise the module's real code for deeper, more realistic testing?
- Stub out the module's interface for more control, speed, and
  isolation?
- Do some combination of the above?

For all the modules where you want to run actual code, add statements
like the following toward the top of your test file:

```js
zrequire('util');
zrequire('stream_data');
zrequire('Filter', 'js/filter');
```

For modules that you want to completely stub out, use a pattern like
this:

```js
const reminder = mock_esm("../../web/src/reminder", {
    is_deferred_delivery: noop,
});

// then maybe further down
reminder.is_deferred_delivery = () => true;
```

One can similarly stub out functions in a module's exported interface
with either `noop` functions or actual code.

Finally, there's the hybrid situation, where you want to borrow some
of a module's real functionality but stub out other pieces. Obviously,
this is a pretty strong code smell that the other module might be
lacking in cohesion, but sometimes it's not worth going down the
rabbit hole of trying to improve that. The pattern here is this:

```js
// Import real code.
zrequire('narrow_state');

// And later...
narrow_state.stream = function () {
    return 'office';
};
```

## Creating new test modules

The test runner (`index.js`) automatically runs all .js files in the
`web/tests` directory, so you can simply start editing a file
in that directory to create a new test.

## Coverage reports

You can automatically generate coverage reports for the JavaScript unit
tests like this:

```bash
tools/test-js-with-node --coverage
```

If tests pass, you will get instructions to view coverage reports
in your browser.

Note that modules that we don't test _at all_ aren't listed in the
report, so this tends to overstate how good our overall coverage is,
but it's accurate for individual files. You can also click a filename
to see the specific statements and branches not tested. 100% branch
coverage isn't necessarily possible, but getting to at least 80%
branch coverage is a good goal.

The overall project goal is to get to 100% node test coverage on all
data/logic modules (UI modules are lower priority for unit testing).

## Editor debugger integration

Our node test system is pretty simple, and it's possible to configure
the native debugger features of popular editors to allow stepping
through the code. Below we document the editors where someone has put
together detailed instructions for how to do so. Contributions of
notes for other editors are welcome!

## Webstorm integration setup

These instructions assume you're using the Vagrant development environment.

1. Set up [Vagrant in WebStorm][vagrant-webstorm].

2. In WebStorm, navigate to `Preferences -> Tools -> Vagrant` and
   configure the following:

   - `Instance folder` should be the root of the `zulip` repository on
     your host (where the Vagrantfile is located).
   - `Provider` should be `virtualbox` on macOS and Docker on Linux
   - In `Boxes`, choose the one used for Zulip (unless you use
     Virtualbox for other things, there should only be one option).

   You shouldn't need to set these additional settings:

   - `Vagrant executable` should already be correctly `vagrant`.
   - `Environment Variables` is not needed.

3. You'll now need to set up a WebStorm "Debug Configuration". Open
   the `Run/Debug Configuration` menu and create a new `Node.js` config:
   1. Under `Node interpreter:` click the 3 dots to the right side and
      click on the little plus in the bottom left of the
      `Node.js Interpreters` window.
   1. Select `Add Remote...`.
      1. In the `Configure Node.js Remote Interpreter`, window select `Vagrant`
      1. Wait for WebStorm to connect to Vagrant. This will be displayed
         by the `Vagrant Host URL` section updating to contain the Vagrant
         SSH URL, e.g. `ssh://vagrant@127.0.0.1:2222`.
      1. **Set the `Node.js interpreter path` to `/usr/local/bin/node`**
      1. Hit `OK` 2 times to get back to the `Run/Debug Configurations` window.
   1. Under `Working Directory` select the root `zulip` directory.
   1. Under `JavaScript file`, enter `web/tests/lib/index.js`
      -- this is the root script for Zulip's node unit tests.

Congratulations! You've now set up the integration.

## Running tests with the debugger

To use Webstorm to debug a given node test file, do the following:

1. Under `Application parameters` choose the node test file that you
   are trying to test (e.g. `web/tests/message_store.test.js`).
1. Under `Path Mappings`, set `Project Root` to `/srv/zulip`
   (i.e. where the `zulip` Git repository is mounted in the Vagrant guest).
1. Use the WebStorm debugger; see [this overview][webstorm-debugging]
   for details on how to use it.

[webstorm-debugging]: https://blog.jetbrains.com/webstorm/2018/01/how-to-debug-with-webstorm/
[vagrant-webstorm]: https://www.jetbrains.com/help/webstorm/vagrant-support.html?section=Windows%20or%20Linux
