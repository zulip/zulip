"use strict";

const {strict: assert} = require("assert");

const noop = function () {};

class Event {
    constructor(type, props) {
        if (!(this instanceof Event)) {
            return new Event(type, props);
        }
        this.type = type;
        Object.assign(this, props);
    }
    preventDefault() {}
    stopPropagation() {}
}

function verify_selector_for_zulip(selector) {
    const is_valid =
        "<#.".includes(selector[0]) ||
        selector === "window-stub" ||
        selector === "document-stub" ||
        selector === "body" ||
        selector === "html" ||
        selector.location ||
        selector.includes("#") ||
        selector.includes(".") ||
        (selector.includes("[") && selector.indexOf("]") >= selector.indexOf("["));

    if (!is_valid) {
        // Check if selector has only english alphabets and space.
        // Then, the user is probably trying to use a tag as a selector
        // like $('div a').
        if (/^[ A-Za-z]+$/.test(selector)) {
            throw new Error("Selector too broad! Use id, class or attributes of target instead.");
        } else {
            throw new Error("Invalid selector: " + selector + " Use $.create() maybe?");
        }
    }
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
                ev = new Event(ev);
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

function make_new_elem(selector, opts) {
    let html = "never-been-set";
    let text = "never-been-set";
    let value;
    let css;
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
        css(...args) {
            if (args.length === 0) {
                return css || {};
            }
            [css] = args;
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
            throw new Error("Cannot find " + child_selector + " in " + selector);
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
            if (arg === ":checked") {
                return self.prop("checked");
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
            assert(
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
                We don't support remove in zjuery.

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
            assert([true, false].includes(show));
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
        self.length = opts.children.length;
    }

    if (selector[0] === "<") {
        self.html(selector);
    }

    self.selector = selector;

    return self;
}

function make_zjquery() {
    const elems = new Map();

    // Our fn structure helps us simulate extending jQuery.
    // Use this with extreme caution.
    const fn = {};

    function new_elem(selector, create_opts) {
        const elem = make_new_elem(selector, {...create_opts});
        Object.assign(elem, fn);

        // Create a proxy handler to detect missing stubs.
        //
        // For context, zjquery doesn't implement every method/attribute
        // that you'd find on a "real" jQuery object.  Sometimes we
        // expects devs to create their own stubs.
        const handler = {
            get: (target, key) => {
                // Handle the special case of equality checks, which
                // we can infer by assert.equal trying to access the
                // "stack" key.
                if (key === "stack") {
                    const error =
                        "\nInstead of doing equality checks on a full object, " +
                        'do `assert_equal(foo.selector, ".some_class")\n';
                    throw new Error(error);
                }

                const val = target[key];

                if (val === undefined && typeof key !== "symbol" && key !== "inspect") {
                    // For undefined values, we'll throw errors to devs saying
                    // they need to create stubs.  We ignore certain keys that
                    // are used for simply printing out the object.
                    throw new Error('You must create a stub for $("' + selector + '").' + key);
                }

                return val;
            },
        };

        const proxy = new Proxy(elem, handler);

        return proxy;
    }

    let initialize_function;

    const zjquery = function (arg, arg2) {
        if (typeof arg === "function") {
            if (initialize_function) {
                throw new Error(`
                    We are trying to avoid the $(...) mechanism
                    for initializing modules in our codebase,
                    and the code that you are compiling/running
                    has tried to do this twice.  Please either
                    clean up the real code or reduce the scope
                    of what you are testing in this test module.
                `);
            }
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
            assert(typeof arg.to_$ === "function");
            return arg.to_$();
        }

        if (arg2 !== undefined) {
            throw new Error("We only use one-argument variations of $(...) in Zulip code.");
        }

        const selector = arg;

        if (typeof selector !== "string") {
            console.info(arg);
            throw new Error("zjquery does not know how to wrap this object yet");
        }

        verify_selector_for_zulip(selector);

        if (!elems.has(selector)) {
            const elem = new_elem(selector);
            elems.set(selector, elem);
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
        assert(!elems.has(name), "You already created an object with this name!!");
        const elem = new_elem(name, opts);
        elems.set(name, elem);

        return elem;
    };

    zjquery.trim = function (s) {
        return s;
    };

    zjquery.state = function () {
        // useful for debugging
        let res = Array.from(elems.values(), (v) => v.debug());

        res = res.map((v) => [v.selector, v.value, v.shown]);

        res.sort();

        return res;
    };

    zjquery.Event = Event;

    fn.popover = () => {
        throw new Error(`
            Do not try to test $.fn.popover code unless
            you really know what you are doing.
        `);
    };

    zjquery.fn = new Proxy(fn, {
        set(obj, prop, value) {
            if (prop === "popover") {
                // We allow our popovers test to modify
                // $.fn so we can bypass a gruesome hack
                // in our popovers.js module.
                obj[prop] = value;
                return true;
            }

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
                replace the wrapper with () => {}.
            `);
        },
    });

    zjquery.clear_all_elements = function () {
        elems.clear();
    };

    zjquery.validator = {
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

        throw new Error(`
            Please don't modify $.${prop} if you are using zjquery.

            You can do this instead:

                override($, "${prop}", () => {...});

            Or you can do this if you don't actually
            need zjquery and just want to simulate one function.

                set_global("$", {
                    ${prop}(...) {...},
                });

            It's also possible that you are testing code with
            node tests when it would be a better strategy to
            use puppeteer tests.
        `);
    },
});

module.exports = $;
