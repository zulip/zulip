"use strict";

const assert = require("node:assert/strict");

const FakeEvent = require("./zjquery_event.cjs");

const noop = function () {};

function split_words(x) {
    return Array.isArray(x) ? x : x.trim().split(/\s+/);
}

const ignore_missing = Symbol("ignore_missing");

const reject_missing_handler = {
    has(target, property) {
        if (!(property in target || target[ignore_missing]?.(property))) {
            throw new TypeError(`unknown property ${property} of mock ${target.constructor.name}`);
        }
        return Reflect.has(target, property);
    },
    get(target, property, receiver) {
        if (!(property in target || target[ignore_missing]?.(property))) {
            throw new TypeError(`unknown property ${property} of mock ${target.constructor.name}`);
        }
        return Reflect.get(target, property, receiver);
    },
    ownKeys(target) {
        throw new TypeError(`enumerating properties of mock ${target.constructor.name}`);
    },
};

class RejectMissing {
    constructor() {
        return new Proxy(this, reject_missing_handler);
    }
}

class FakeClassList extends RejectMissing {
    #list = new Set();

    contains(class_name) {
        return this.#list.has(class_name);
    }
    add(...class_names) {
        for (const class_name of class_names) {
            this.#list.add(String(class_name));
        }
    }
    remove(...class_names) {
        for (const class_name of class_names) {
            this.#list.delete(String(class_name));
        }
    }
    toggle(class_name, state = !this.#list.has(String(class_name))) {
        if (state) {
            this.#list.add(String(class_name));
        } else {
            this.#list.delete(String(class_name));
        }
    }
}

class FakeElementState {
    shown = false;
}

const fake_element_state = new WeakMap();

class FakeElement extends RejectMissing {
    _tippy = undefined;
    classList = new FakeClassList();
    innerHTML = "never-been-set";
    textContent = "never-been-set";
    value = undefined;

    constructor() {
        super();
        fake_element_state.set(this, new FakeElementState());
    }
}

// TODO: convert this to a true class
exports.FakeJQuery = function (selector, opts) {
    let height;

    const find_results = new Map();
    let $my_parent;
    const parents_result = new Map();
    const attrs = new Map();
    const event_store = make_event_store(selector);

    const $self = {
        [Symbol.iterator]: Array.prototype.values,
        addClass(class_names) {
            class_names = split_words(class_names);
            for (const element of this) {
                element.classList.add(...class_names);
            }
            return this;
        },
        append(arg) {
            assert.notEqual(typeof arg, "string");
            return this;
        },
        attr(name, val) {
            if (val === undefined) {
                return attrs.get(name);
            }
            attrs.set(name, val);
            return this;
        },
        data(name, val) {
            if (val === undefined) {
                return attrs.get("data-" + name);
            }
            attrs.set("data-" + name, val);
            return this;
        },
        each(callback) {
            for (const [index, element] of [...this].entries()) {
                callback.call(element, index, element);
            }
            return this;
        },
        empty() {
            find_results.clear();
            for (const element of this) {
                element.innerHTML = "";
            }
            return this;
        },
        expectOne() {
            // silently do nothing
            return this;
        },
        fadeTo() {
            return this;
        },
        find(child_selector) {
            const $child = find_results.get(child_selector);
            if ($child) {
                return $child;
            }
            if ($child === false) {
                // This is deliberately set to simulate missing find results.
                // Return an empty array, the most common check is
                // if ($.find().length) { //success }
                return [];
            }
            /* istanbul ignore next */
            throw new Error(`
                We need you to simulate the results of $(...).find(...)
                by using set_find_results. You want something like this:

                    const $container = ...;
                    const $child = ...;
                    $container.set_find_results("${child_selector}", $child);

                Then calling $container.find("${child_selector}") will return
                the "$child" zjquery element.

                `);
        },
        get(index) {
            return index === undefined ? [...this] : this[index];
        },
        get_on_handler(name, child_selector) {
            return event_store.get_on_handler(name, child_selector);
        },
        hasClass(class_name) {
            return [...this].some((element) => element.classList.contains(class_name));
        },
        height() {
            assert.notEqual(height, undefined, `Please call $("${selector}").set_height`);
            return height;
        },
        hide() {
            for (const element of this) {
                fake_element_state.get(element).shown = false;
            }
            return this;
        },
        html(...args) {
            if (args.length === 0) {
                return this[0]?.innerHTML;
            }

            const [arg] = args;
            assert.equal(typeof arg, "string");
            for (const element of this) {
                element.innerHTML = arg;
            }
            return this;
        },
        is(arg) {
            switch (arg) {
                case ":visible":
                    return [...this].some((element) => fake_element_state.get(element).shown);
                case ":focus":
                    return this.is_focused();
                /* istanbul ignore next */
                default:
                    throw new Error("zjquery does not support this is() call");
            }
        },
        is_focused() {
            // is_focused is not a jQuery thing; this is
            // for our testing
            return event_store.is_focused();
        },
        off(...args) {
            event_store.off(...args);
            return this;
        },
        on(...args) {
            event_store.on(...args);
            return this;
        },
        /* istanbul ignore next */
        one(...args) {
            event_store.one(...args);
            return this;
        },
        parent() {
            return $my_parent;
        },
        parents(parents_selector) {
            const $result = parents_result.get(parents_selector);
            assert.ok(
                $result,
                "You need to call set_parents_result for " + parents_selector + " in " + selector,
            );
            return $result;
        },
        prepend(arg) {
            assert.notEqual(typeof arg, "string");
            return this;
        },
        prop(name, ...args) {
            if (args.length === 0) {
                return this[0]?.[name];
            }
            const [value] = args;
            for (const element of this) {
                element[name] = value;
            }
            return this;
        },
        removeAttr(name) {
            attrs.delete(name);
            return this;
        },
        removeClass(class_names) {
            class_names = split_words(class_names);
            for (const element of this) {
                element.classList.remove(...class_names);
            }
            return this;
        },
        /* istanbul ignore next */
        remove() {
            throw new Error(`
                We don't support remove in zjquery.

                You can do $(...).remove = ... if necessary.

                But you are probably writing too deep a test
                for node testing.
            `);
        },
        removeData: noop,
        set_find_results(find_selector, $jquery_object) {
            assert.notEqual(
                $jquery_object,
                undefined,
                "Please make the 'find result' be something like $.create('unused')",
            );
            find_results.set(find_selector, $jquery_object);
        },
        set_height(fake_height) {
            height = fake_height;
        },
        set_parent($parent_elem) {
            $my_parent = $parent_elem;
        },
        set_parents_result(selector, $result) {
            parents_result.set(selector, $result);
        },
        show() {
            for (const element of this) {
                fake_element_state.get(element).shown = true;
            }
            return this;
        },
        text(...args) {
            if (args.length === 0) {
                return [...this].map((element) => element.textContent).join("");
            }
            const [arg] = args;
            for (const [i, element] of [...this].entries()) {
                element.textContent =
                    (typeof arg === "function"
                        ? arg.call(element, i, element.textContent)
                        : arg
                    )?.toString() ?? "";
            }
            return this;
        },
        // Used by zjquery to support $($x) === $x
        to_$() {
            return this;
        },
        toggle(show) {
            assert.ok([true, false].includes(show));
            for (const element of this) {
                fake_element_state.get(element).shown = show;
            }
            return this;
        },
        toggleClass(class_names, add) {
            class_names = split_words(class_names);
            for (const element of this) {
                for (const class_name of class_names) {
                    element.classList.toggle(class_name, add);
                }
            }
            return this;
        },
        trigger(ev) {
            event_store.trigger(this, ev);
            return this;
        },
        val(...args) {
            if (args.length === 0) {
                return 0 in this ? (this[0].value ?? "") : undefined;
            }
            const [value] = args;
            for (const element of this) {
                element.value = value;
            }
            return this;
        },
        visible() {
            return [...this].some((element) => fake_element_state.get(element).shown);
        },
    };

    if (opts.elements) {
        for (const [i, element] of opts.elements.entries()) {
            $self[i] = element;
        }

        $self.length = opts.elements.length;
    } else {
        $self.length = 1;
        $self[0] = new FakeElement();
        $self[0].to_$ = () => $self;
        if (selector[0] === "<") {
            $self.html(selector);
        }
    }

    $self.selector = selector;

    $self.__zjquery = true;

    return $self;
};

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
                assert.ok(handler, `no ${name} handler for ${selector}`);
                return handler;
            }

            const child_on = child_on_functions.get(child_selector);
            if (child_on) {
                handler = child_on.get(name);
            }

            assert.ok(handler, `no ${name} handler for ${selector} ${child_selector}`);

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
            /* istanbul ignore next */
            throw new Error("zjquery does not support this call sequence");
        },

        on(event_name, ...args) {
            // parameters will either be
            //    (event_name, handler) or
            //    (event_name, sel, handler)
            if (args.length === 1) {
                const [handler] = args;
                /* istanbul ignore if */
                if (on_functions.has(event_name)) {
                    console.info("\nEither the app or the test can be at fault here..");
                    console.info("(sometimes you just want to call $.clear_all_elements();)\n");
                    throw new Error("dup " + event_name + " handler for " + selector);
                }

                on_functions.set(event_name, handler);
                return;
            }

            assert.equal(args.length, 2, "wrong number of arguments passed in");

            const [sel, handler] = args;
            assert.equal(typeof sel, "string", "String selectors expected here.");
            assert.equal(typeof handler, "function", "An handler function expected here.");

            if (!child_on_functions.has(sel)) {
                child_on_functions.set(sel, new Map());
            }

            const child_on = child_on_functions.get(sel);

            assert.ok(
                !child_on.has(event_name),
                `dup ${event_name} handler for ${selector} ${sel}`,
            );

            child_on.set(event_name, handler);
        },

        /* istanbul ignore next */
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
                // FIXME: event.target should not be a jQuery object
                ev.target = $element; // eslint-disable-line no-jquery/variable-pattern
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
