"use strict";

const {strict: assert} = require("assert");

const FakeEvent = require("./zjquery_event");

const noop = function () {};

// TODO: convert this to a true class
function FakeElement(selector, opts) {
    let html = "never-been-set";
    let text = "never-been-set";
    let value;
    let shown = false;
    let height;

    const find_results = new Map();
    let my_parent;
    const parents_result = new Map();
    const properties = new Map();
    const attrs = new Map();
    const classes = new Map();
    const event_store = make_event_store(selector);

    const self = {
        addClass(class_name) {
            classes.set(class_name, true);
            return self;
        },
        append(arg) {
            html = html + arg;
            return self;
        },
        attr(name, val) {
            if (val === undefined) {
                return attrs.get(name);
            }
            attrs.set(name, val);
            return self;
        },
        data(name, val) {
            if (val === undefined) {
                return attrs.get("data-" + name);
            }
            attrs.set("data-" + name, val);
            return self;
        },
        delay() {
            return self;
        },
        debug() {
            return {
                value,
                shown,
                selector,
            };
        },
        empty(arg) {
            if (arg === undefined) {
                find_results.clear();
            }
            return self;
        },
        eq() {
            return self;
        },
        expectOne() {
            // silently do nothing
            return self;
        },
        fadeTo: noop,
        find(child_selector) {
            const child = find_results.get(child_selector);
            if (child) {
                return child;
            }
            if (child === false) {
                // This is deliberately set to simulate missing find results.
                // Return an empty array, the most common check is
                // if ($.find().length) { //success }
                return [];
            }
            throw new Error(`
                We need you to simulate the results of $(...).find(...)
                by using set_find_results. You want something like this:

                    const container = ...;
                    const child = ...;
                    container.set_find_results("${child_selector}", child);

                Then calling container.find("${child_selector}") will return
                the "child" zjquery element.

                `);
        },
        get_on_handler(name, child_selector) {
            return event_store.get_on_handler(name, child_selector);
        },
        hasClass(class_name) {
            return classes.has(class_name);
        },
        height() {
            if (height === undefined) {
                throw new Error(`Please call $("${selector}").set_height`);
            }
            return height;
        },
        hide() {
            shown = false;
            return self;
        },
        html(arg) {
            if (arg !== undefined) {
                html = arg;
                return self;
            }
            return html;
        },
        is(arg) {
            if (arg === ":visible") {
                return shown;
            }
            if (arg === ":focus") {
                return self.is_focused();
            }
            return self;
        },
        is_focused() {
            // is_focused is not a jQuery thing; this is
            // for our testing
            return event_store.is_focused();
        },
        off(...args) {
            event_store.off(...args);
            return self;
        },
        offset() {
            return {
                top: 0,
                left: 0,
            };
        },
        on(...args) {
            event_store.on(...args);
            return self;
        },
        one(...args) {
            event_store.one(...args);
            return self;
        },
        parent() {
            return my_parent;
        },
        parents(parents_selector) {
            const result = parents_result.get(parents_selector);
            assert.ok(
                result,
                "You need to call set_parents_result for " + parents_selector + " in " + selector,
            );
            return result;
        },
        prepend(arg) {
            html = arg + html;
            return self;
        },
        prop(name, val) {
            if (val === undefined) {
                return properties.get(name);
            }
            properties.set(name, val);
            return self;
        },
        removeAttr(name) {
            attrs.delete(name);
            return self;
        },
        removeClass(class_names) {
            class_names = class_names.split(" ");
            for (const class_name of class_names) {
                classes.delete(class_name);
            }
            return self;
        },
        remove() {
            throw new Error(`
                We don't support remove in zjquery.

                You can do $(...).remove = ... if necessary.

                But you are probably writing too deep a test
                for node testing.
            `);
        },
        removeData: noop,
        replaceWith() {
            return self;
        },
        scrollTop() {
            return self;
        },
        serializeArray() {
            return self;
        },
        set_find_results(find_selector, jquery_object) {
            find_results.set(find_selector, jquery_object);
        },
        set_height(fake_height) {
            height = fake_height;
        },
        set_parent(parent_elem) {
            my_parent = parent_elem;
        },
        set_parents_result(selector, result) {
            parents_result.set(selector, result);
        },
        show() {
            shown = true;
            return self;
        },
        slice() {
            return self;
        },
        stop() {
            return self;
        },
        text(...args) {
            if (args.length !== 0) {
                if (args[0] !== undefined) {
                    text = args[0].toString();
                }
                return self;
            }
            return text;
        },
        toggle(show) {
            assert.ok([true, false].includes(show));
            shown = show;
            return self;
        },
        tooltip() {
            return self;
        },
        trigger(ev) {
            event_store.trigger(self, ev);
            return self;
        },
        val(...args) {
            if (args.length === 0) {
                return value || "";
            }
            [value] = args;
            return self;
        },
        visible() {
            return shown;
        },
    };

    if (opts.children) {
        self.map = (f) => opts.children.map((i, elem) => f(elem, i));
        self.each = (f) => {
            for (const child of opts.children) {
                f.call(child);
            }
        };
        self[Symbol.iterator] = function* () {
            for (const child of opts.children) {
                yield child;
            }
        };

        for (const [i, child] of opts.children.entries()) {
            self[i] = child;
        }

        self.length = opts.children.length;
    }

    if (selector[0] === "<") {
        self.html(selector);
    }

    self.selector = selector;

    self.__zjquery = true;

    return self;
}

function make_event_store(selector) {
    /*

       This function returns an event_store object that
       simulates the behavior of .on and .off from jQuery.

       It also has methods to retrieve handlers that have
       been set via .on (or similar methods), which can
       be useful for tests that want to test the actual
       handlers.

    */
    const on_functions = new Map();
    const child_on_functions = new Map();
    let focused = false;

    const self = {
        get_on_handler(name, child_selector) {
            let handler;

            if (child_selector === undefined) {
                handler = on_functions.get(name);
                if (!handler) {
                    throw new Error("no " + name + " handler for " + selector);
                }
                return handler;
            }

            const child_on = child_on_functions.get(child_selector);
            if (child_on) {
                handler = child_on.get(name);
            }

            if (!handler) {
                throw new Error("no " + name + " handler for " + selector + " " + child_selector);
            }

            return handler;
        },

        off(event_name, ...args) {
            if (args.length === 0) {
                on_functions.delete(event_name);
                return;
            }

            // In the Zulip codebase we never use this form of
            // .off in code that we test: $(...).off('click', child_sel);
            //
            // So we don't support this for now.
            throw new Error("zjquery does not support this call sequence");
        },

        on(event_name, ...args) {
            // parameters will either be
            //    (event_name, handler) or
            //    (event_name, sel, handler)
            if (args.length === 1) {
                const [handler] = args;
                if (on_functions.has(event_name)) {
                    console.info("\nEither the app or the test can be at fault here..");
                    console.info("(sometimes you just want to call $.clear_all_elements();)\n");
                    throw new Error("dup " + event_name + " handler for " + selector);
                }

                on_functions.set(event_name, handler);
                return;
            }

            if (args.length !== 2) {
                throw new Error("wrong number of arguments passed in");
            }

            const [sel, handler] = args;
            assert.equal(typeof sel, "string", "String selectors expected here.");
            assert.equal(typeof handler, "function", "An handler function expected here.");

            if (!child_on_functions.has(sel)) {
                child_on_functions.set(sel, new Map());
            }

            const child_on = child_on_functions.get(sel);

            if (child_on.has(event_name)) {
                throw new Error("dup " + event_name + " handler for " + selector + " " + sel);
            }

            child_on.set(event_name, handler);
        },

        one(event_name, handler) {
            self.on(event_name, function (ev) {
                self.off(event_name);
                return handler.call(this, ev);
            });
        },

        trigger($element, ev, data) {
            if (typeof ev === "string") {
                ev = new FakeEvent(ev);
            }
            if (!ev.target) {
                ev.target = $element;
            }
            const func = on_functions.get(ev.type);

            if (func) {
                // It's possible that test code will trigger events
                // that haven't been set up yet, but we are trying to
                // eventually deprecate trigger in our codebase, so for
                // now we just let calls to trigger silently do nothing.
                // (And I think actual jQuery would do the same thing.)
                func.call($element, ev, data);
            }

            if (ev.type === "focus" || ev.type === "focusin") {
                focused = true;
            } else if (ev.type === "blur" || ev.type === "focusout") {
                focused = false;
            }
        },

        is_focused() {
            return focused;
        },
    };

    return self;
}

module.exports = FakeElement;
