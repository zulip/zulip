# JavaScript unit tests

As an alternative to the black-box whole-app testing, you can unit test
individual JavaScript files.

If you are writing JavaScript code that manipulates data (as opposed
to coordinating UI changes), then you probably modify existing unit test
modules to ensure the quality of your code and prevent regressions.

The JS unit tests are written to work with node.  You can find them
in `frontend_tests/node_tests`.  Here is an example test from
`frontend_tests/node_tests/stream_data.js`:

```
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
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, 'red');
}());
```

The names of the node tests generally align with the names of the
modules they test.  If you modify a JS module in `static/js` you should
see if there are corresponding test in `frontend_tests/node_tests`.  If
there are, you should strive to follow the patterns of the existing tests
and add your own tests.

## HTML output

The JavaScript unit tests can generate output to be viewed in the
browser.  The best examples of this are in `frontend_tests/node_tests/templates.js`.

The main use case for this mechanism is to be able to unit test
templates and see how they are rendered without the complications
of the surrounding app.  (Obviously, you still need to test the
app itself!)  The HTML output can also help to debug the unit tests.

Each test calls a method named `write_handlebars_output` after it
renders a template with similar data.  This API is still evolving,
but you should be able to look at existing code for patterns.

When you run `tools/test-js-with-node`, it will present you with a
message like "To see more output, open var/test-js-with-node/index.html."
Basically, you just need to open the file in the browser.  (If you are
running a VM, this might require switching to another terminal window
to launch the `open` command.)

## Coverage reports

You can automatically generate coverage reports for the JavaScript unit
tests like this:

>     tools/test-js-with-node --coverage

Then open `coverage/lcov-report/js/index.html` in your browser. Modules
we don't test *at all* aren't listed in the report, so this tends to
overstate how good our overall coverage is, but it's accurate for
individual files. You can also click a filename to see the specific
statements and branches not tested. 100% branch coverage isn't
necessarily possible, but getting to at least 80% branch coverage is a
good goal.

## Handling dependencies in unit tests

The following scheme helps avoid tests leaking globals between each
other.

First, if you can avoid globals, do it, and the code that is directly
under test can simply be handled like this:

>     var search = require('js/search_suggestion.js');

For deeper dependencies, you want to categorize each module as follows:

-   Exercise the module's real code for deeper, more realistic testing?
-   Stub out the module's interface for more control, speed, and
    isolation?
-   Do some combination of the above?

For all the modules where you want to run actual code, add statements
like the following toward the top of your test file:

>     zrequire('util');
>     zrequire('stream_data');
>     zrequire('Filter', 'js/filter');

For modules that you want to completely stub out, please use a pattern
like this:

>     set_global('page_params', {
>         email: 'bob@zulip.com'
>     });
>
>     // then maybe further down
>     global.page_params.email = 'alice@zulip.com';

Finally, there's the hybrid situation, where you want to borrow some of
a module's real functionality but stub out other pieces. Obviously, this
is a pretty strong smell that the other module might be lacking in
cohesion, but that code might be outside your jurisdiction. The pattern
here is this:

>     // Use real versions of parse/unparse
>     var narrow = require('js/narrow.js');
>     set_global('narrow', {
>         parse: narrow.parse,
>         unparse: narrow.unparse
>     });
>
>     // But later, I want to stub the stream without having to call super-expensive
>     // real code like narrow.activate().
>     global.narrow.stream = function () {
>         return 'office';
>     };

## Creating new test modules

The nodes tests rely on JS files that use the module pattern. For example, to
test the `foobar.js` file, you would first add the following to the
bottom of `foobar.js`:

>     if (typeof module !== 'undefined') {
>         module.exports = foobar;
>     }

This makes `foobar.js` follow the CommonJS module pattern, so it can be
required in Node.js, which runs our tests.

Now create `frontend_tests/node_tests/foobar.js`. At the top, require
the [Node.js assert module](http://nodejs.org/api/assert.html), and the
module you're testing, like so:

>     var assert = require('assert');
>     var foobar = require('js/foobar.js');

And of course, if the module you're testing depends on other modules,
or modifies global state, you may need to review the
[section on handling dependencies](#handling-dependencies-in-unit-tests) above.

Define and call some tests using the [assert
module](http://nodejs.org/api/assert.html). Note that for "equal"
asserts, the *actual* value comes first, the *expected* value second.

>     (function test_somefeature() {
>         assert.strictEqual(foobar.somefeature('baz'), 'quux');
>         assert.throws(foobar.somefeature('Invalid Input'));
>     }());

The test runner (`index.js`) automatically runs all .js files in the
frontend\_tests/node directory.
