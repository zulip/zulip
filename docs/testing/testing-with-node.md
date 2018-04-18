# JavaScript unit tests

As an alternative to the black-box whole-app testing, you can unit test
individual JavaScript files.

You can run tests as follow:
```
    tools/test-js-with-node
```

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

## Coverage reports

You can automatically generate coverage reports for the JavaScript unit
tests like this:

```
    tools/test-js-with-node --coverage
```

If tests pass, you will get instructions to view coverage reports
in your browser.

Note that modules that
we don't test *at all* aren't listed in the report, so this tends to
overstate how good our overall coverage is, but it's accurate for
individual files. You can also click a filename to see the specific
statements and branches not tested. 100% branch coverage isn't
necessarily possible, but getting to at least 80% branch coverage is a
good goal.

## Handling dependencies in unit tests

The following scheme helps avoid tests leaking globals between each
other.

You want to categorize each module as follows:

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
>     page_params.email = 'alice@zulip.com';

Finally, there's the hybrid situation, where you want to borrow some of
a module's real functionality but stub out other pieces. Obviously, this
is a pretty strong smell that the other module might be lacking in
cohesion, but that code might be outside your jurisdiction. The pattern
here is this:

>     // Import real code.
>     zrequire('narrow');
>
>     // And later...
>     narrow.stream = function () {
>         return 'office';
>     };

## Creating new test modules

The test runner (`index.js`) automatically runs all .js files in the
`frontend_tests/node directory`, so you can simply start editing a file
in that directory to create a new test.

The nodes tests rely on JS files that use the module pattern. For example, to
test the `foobar.js` file, you would first ensure that code like below
is at the bottom of `foobar.js`:

>     if (typeof module !== 'undefined') {
>         module.exports = foobar;
>     }

This means `foobar.js` follow the CommonJS module pattern, so it can be
required in Node.js, which runs our tests.

