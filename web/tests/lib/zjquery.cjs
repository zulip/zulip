"use strict";

const assert = require("node:assert/strict");

/*
    When using zjquery, the first call to $("#foo")
    returns a new instance of the FakeJQuery pseudoclass,
    and then subsequent calls to $("#foo") get the
    same instance.
*/
const {FakeJQuery} = require("./zjquery_element.cjs");
const FakeEvent = require("./zjquery_event.cjs");

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

    function new_elem(selector, create_opts) {
        const $elem = FakeJQuery(selector, {...create_opts});

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

                /* istanbul ignore if */
                if (!(key in target) && typeof key !== "symbol" && key !== "inspect") {
                    // For undefined values, we'll throw errors to devs saying
                    // they need to create stubs.  We ignore certain keys that
                    // are used for simply printing out the object.
                    throw new Error('You must create a stub for $("' + selector + '").' + key);
                }

                return target[key];
            },
        };

        const proxy = new Proxy($elem, handler);

        return proxy;
    }

    const zjquery = function (arg, arg2) {
        assert.ok(typeof arg !== "function", "zjquery does not support $(callback)");

        // We occasionally create stub objects that know
        // they want to be wrapped by jQuery (so they can
        // in turn return stubs).  The convention is that
        // they provide a to_$ attribute.
        if (typeof arg === "object" && "to_$" in arg) {
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

    zjquery.create = function (name, opts) {
        assert.ok(!elems.has(name), "You already created an object with this name!!");
        const $elem = new_elem(name, opts);
        elems.set(name, $elem);

        return $elem;
    };

    zjquery.set_results = (selector, elements) => zjquery.create(selector, {elements});

    zjquery.Event = FakeEvent;

    zjquery.reset_selector = (selector) => {
        elems.delete(selector);
    };

    zjquery.clear_all_elements = function () {
        elems.clear();
    };

    return zjquery;
}

const $ = Object.freeze(make_zjquery());
module.exports = $; // eslint-disable-line no-jquery/variable-pattern
