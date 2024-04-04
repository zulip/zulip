"use strict";

const {strict: assert} = require("assert");

/*
    When using zjquery, the first call to $("#foo")
    returns a new instance of the FakeElement pseudoclass,
    and then subsequent calls to $("#foo") get the
    same instance.
*/
const FakeElement = require("./zjquery_element");
const FakeEvent = require("./zjquery_event");

function verify_selector_for_zulip(selector) {
    const is_valid =
        "<#.".includes(selector[0]) ||
        selector === "window-stub" ||
        selector === "document-stub" ||
        selector === "body" ||
        selector === "html" ||
        selector === ":root" ||
        selector.location ||
        selector.includes("#") ||
        selector.includes(".") ||
        (selector.includes("[") && selector.indexOf("]") >= selector.indexOf("["));

    assert.ok(
        is_valid,
        // Check if selector has only english alphabets and space.
        // Then, the user is probably trying to use a tag as a selector
        // like $('div a').
        /^[ A-Za-z]+$/.test(selector)
            ? "Selector too broad! Use id, class or attributes of target instead."
            : `Invalid selector: ${selector}. Use $.create() maybe?`,
    );
}

function make_zjquery() {
    const elems = new Map();

    // Our fn structure helps us simulate extending jQuery.
    // Use this with extreme caution.
    const fn = {};

    function new_elem(selector, create_opts) {
        const $elem = FakeElement(selector, {...create_opts});
        Object.assign($elem, fn);

        // Create a proxy handler to detect missing stubs.
        //
        // For context, zjquery doesn't implement every method/attribute
        // that you'd find on a "real" jQuery object.  Sometimes we
        // expects devs to create their own stubs.
        const handler = {
            get(target, key) {
                // Handle the special case of equality checks, which
                // we can infer by assert.equal trying to access the
                // "stack" key.
                assert.notEqual(
                    key,
                    "stack",
                    "\nInstead of doing equality checks on a full object, " +
                        'do `assert.equal($foo.selector, ".some_class")\n',
                );

                const val = target[key];

                /* istanbul ignore if */
                if (val === undefined && typeof key !== "symbol" && key !== "inspect") {
                    // For undefined values, we'll throw errors to devs saying
                    // they need to create stubs.  We ignore certain keys that
                    // are used for simply printing out the object.
                    throw new Error('You must create a stub for $("' + selector + '").' + key);
                }

                return val;
            },
        };

        const proxy = new Proxy($elem, handler);

        return proxy;
    }

    let initialize_function;

    const zjquery = function (arg, arg2) {
        if (typeof arg === "function") {
            assert.ok(
                !initialize_function,
                `
                    We are trying to avoid the $(...) mechanism
                    for initializing modules in our codebase,
                    and the code that you are compiling/running
                    has tried to do this twice.  Please either
                    clean up the real code or reduce the scope
                    of what you are testing in this test module.
                `,
            );
            initialize_function = arg;
            return undefined;
        }

        // If somebody is passing us an element, we return
        // the element itself if it's been created with
        // zjquery.
        // This may happen in cases like $(this).
        if (arg.selector && elems.has(arg.selector)) {
            return arg;
        }

        // We occasionally create stub objects that know
        // they want to be wrapped by jQuery (so they can
        // in turn return stubs).  The convention is that
        // they provide a to_$ attribute.
        if (arg.to_$) {
            assert.equal(typeof arg.to_$, "function");
            return arg.to_$();
        }

        assert.equal(
            arg2,
            undefined,
            "We only use one-argument variations of $(...) in Zulip code.",
        );

        const selector = arg;

        /* istanbul ignore if */
        if (typeof selector !== "string") {
            console.info(arg);
            throw new Error("zjquery does not know how to wrap this object yet");
        }

        verify_selector_for_zulip(selector);

        if (!elems.has(selector)) {
            const $elem = new_elem(selector);
            elems.set(selector, $elem);
        }
        return elems.get(selector);
    };

    zjquery.get_initialize_function = function () {
        return initialize_function;
    };

    zjquery.clear_initialize_function = function () {
        initialize_function = undefined;
    };

    zjquery.create = function (name, opts) {
        assert.ok(!elems.has(name), "You already created an object with this name!!");
        const $elem = new_elem(name, opts);
        elems.set(name, $elem);

        return $elem;
    };

    /* istanbul ignore next */
    zjquery.state = function () {
        // useful for debugging
        let res = [...elems.values()].map(($v) => $v.debug());

        res = res.map((v) => [v.selector, v.value, v.shown]);

        res.sort();

        return res;
    };

    zjquery.Event = FakeEvent;

    /* istanbul ignore next */
    fn.popover = () => {
        throw new Error(`
            Do not try to test $.fn.popover code unless
            you really know what you are doing.
        `);
    };

    zjquery.fn = new Proxy(fn, {
        set(_obj, _prop, _value) {
            /* istanbul ignore next */
            throw new Error(`
                Please don't use node tests to test code
                that extends $.fn unless you really know
                what you are doing.

                It's likely that you are better off testing
                end-to-end behavior with puppeteer tests.

                If you are trying to get coverage on a module
                that extends $.fn, and you just want to skip
                over that aspect of the module for the purpose
                of testing, see if you can wrap the code
                that extends $.fn and use override() to
                replace the wrapper with tests.lib.noop.
            `);
        },
    });

    zjquery.clear_all_elements = function () {
        elems.clear();
    };

    zjquery.validator = {
        /* istanbul ignore next */
        addMethod() {
            throw new Error("You must create your own $.validator.addMethod stub.");
        },
    };

    return zjquery;
}

const $ = new Proxy(make_zjquery(), {
    set(obj, prop, value) {
        if (obj[prop] && obj[prop]._patched_with_override) {
            obj[prop] = value;
            return true;
        }

        if (value._patched_with_override) {
            obj[prop] = value;
            return true;
        }

        /* istanbul ignore next */
        throw new Error(`
            Please don't modify $.${prop} if you are using zjquery.

            You can do this instead:

                override($, "${prop}", () => {...});

            Or you can do this if you don't actually
            need zjquery and just want to simulate one function.

                mock_cjs("jquery", {
                    ${prop}(...) {...},
                });

            It's also possible that you are testing code with
            node tests when it would be a better strategy to
            use puppeteer tests.
        `);
    },
});

module.exports = $; // eslint-disable-line no-jquery/variable-pattern
