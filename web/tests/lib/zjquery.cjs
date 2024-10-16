"use strict";

const assert = require("node:assert/strict");

/*
    When using zjquery, the first call to $("#foo")
    returns a new instance of the FakeJQuery pseudoclass,
    and then subsequent calls to $("#foo") get the
    same instance.
*/
const {default_element, FakeJQuery} = require("./zjquery_element.cjs");
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
            const $elem = new FakeJQuery([default_element(selector)]);
            $elem[0].to_$ = () => $elem;
            elems.set(selector, $elem);
        }
        return elems.get(selector);
    };

    zjquery.create = function (selector, opts) {
        assert.ok(!elems.has(selector), "You already created an object with this name!!");
        const $elem = new FakeJQuery(opts?.elements ?? [default_element(selector)]);
        if (!opts?.elements) {
            $elem[0].to_$ = () => $elem;
        }
        elems.set(selector, $elem);

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
