"use strict";

const assert = require("node:assert/strict");

const FakeEvent = require("./zjquery_event.cjs");

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

class FakeStyle extends RejectMissing {
    #style = new Map();

    get length() {
        return this.#style.size;
    }
    getPropertyValue(name) {
        return this.#style.get(name) ?? "";
    }
    setProperty(name, value) {
        this.#style.set(name, String(value));
    }
    removeProperty(name) {
        const value = this.#style.get(name) ?? "";
        this.#style.delete(name);
        return value;
    }
}

class FakeElementState {
    closest_results = new Map();
    computed_style = new FakeStyle();
    event_handlers = new Map();
    delegated_event_handlers = new Map();
    is_focused = false;
    jquery_data = new Map();
    jquery_next_results = new Map();
    jquery_prev_results = new Map();
    match_results = new Map([["*", true]]);
    parents_results = new Map();
    query_results = new Map();
    selector = undefined;
    shown = false;
}

const fake_element_state = new WeakMap();

function camel(s) {
    return s.replaceAll(/-([a-z])/g, (_, c) => c.toUpperCase());
}

function decamel(s) {
    return s.replaceAll(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
}

function normalize_attribute(name) {
    return String(name).replaceAll(/[A-Z]/g, (c) => c.toLowerCase());
}

function attribute_to_dataset_key(name) {
    assert.ok(name.startsWith("data-"));
    return camel(name.slice("data-".length));
}

function is_dataset_key(key) {
    return !/-[a-z]/.test(key);
}

function dataset_key_to_attribute(key) {
    return `data-${decamel(key)}`;
}

class FakeDataSet {
    constructor(element) {
        return new Proxy(this, {
            get(target, key, receiver) {
                return (
                    (is_dataset_key(key)
                        ? element.getAttribute(dataset_key_to_attribute(key))
                        : null) ?? Reflect.get(target, key, receiver)
                );
            },
            has(_target, key) {
                return is_dataset_key(key) && element.hasAttribute(dataset_key_to_attribute(key));
            },
            set(_target, key, value) {
                assert.ok(is_dataset_key(key));
                element.setAttribute(dataset_key_to_attribute(key), value);
                return true;
            },
            deleteProperty(_target, key) {
                if (is_dataset_key(key)) {
                    element.removeAttribute(dataset_key_to_attribute(key));
                }
                return true;
            },
            ownKeys(_target) {
                return element
                    .getAttributeNames()
                    .filter((name) => name.startsWith("data-"))
                    .map((name) => attribute_to_dataset_key(name));
            },
        });
    }
}

// https://api.jquery.com/css/
const auto_px =
    /^(Border(Top|Right|Bottom|Left)?(Width)?|(Margin|Padding)?(Top|Right|Bottom|Left)?|(Min|Max)?(Width|Height))$/;

class FakeElement extends RejectMissing {
    _tippy = undefined;
    classList = new FakeClassList();
    dataset = new FakeDataSet(this);
    innerHTML = "never-been-set";
    selectionEnd = undefined;
    selectionStart = undefined;
    style = new FakeStyle();
    textContent = "never-been-set";
    value = undefined;

    #attributes = new Map();

    constructor() {
        super();
        fake_element_state.set(this, new FakeElementState());
    }
    append() {}
    closest(selector) {
        const state = fake_element_state.get(this);
        if (!state.closest_results.has(selector)) {
            throw new Error(
                `You need to call $(${JSON.stringify(state.selector)}).set_closest_results(${JSON.stringify(selector)}, ...)`,
            );
        }
        return state.closest_results.get(selector);
    }
    hasAttribute(name) {
        return this.#attributes.has(normalize_attribute(name));
    }
    getAttribute(name) {
        return this.#attributes.get(normalize_attribute(name)) ?? null;
    }
    getAttributeNames() {
        return this.#attributes.keys();
    }
    matches(selector) {
        const state = fake_element_state.get(this);
        if (!state.match_results.has(selector)) {
            throw new Error(
                `You need to call $(${JSON.stringify(state.selector)}).set_matches(${JSON.stringify(selector)}, boolean)`,
            );
        }
        return state.match_results.get(selector);
    }
    querySelectorAll(selector) {
        const state = fake_element_state.get(this);
        const results = state.query_results.get(selector);
        if (results) {
            return results;
        }
        throw new Error(
            `You need to call $(${JSON.stringify(state.selector)}).set_find_results(${JSON.stringify(selector)}, ...).`,
        );
    }
    removeAttribute(name) {
        this.#attributes.delete(normalize_attribute(name));
    }
    setAttribute(name, value) {
        this.#attributes.set(normalize_attribute(name), String(value));
    }
    setSelectionRange(start, end) {
        this.selectionStart = start;
        this.selectionEnd = end;
    }
    to_$() {
        return new exports.FakeJQuery([this]);
    }
}

exports.default_element = function (selector) {
    const element = new FakeElement();
    fake_element_state.get(element).selector = selector;
    if (selector[0] === "<") {
        element.innerHTML = selector;
    }
    return element;
};

function dom_args(args) {
    return args.flat().flatMap((arg) => {
        assert.equal(typeof arg, "object");
        return arg.__zjquery ? [...arg] : [arg];
    });
}

{
    exports.FakeJQuery = class extends RejectMissing {
        [Symbol.iterator] = Array.prototype.values;
        __zjquery = true;

        constructor(elements) {
            super();
            this.length = elements.length;
            for (const [i, element] of elements.entries()) {
                this[i] = element;
            }
        }

        get selector() {
            assert.equal(this.length, 1);
            return fake_element_state.get(this[0]).selector;
        }

        addClass(class_names) {
            class_names = split_words(class_names);
            for (const element of this) {
                element.classList.add(...class_names);
            }
            return this;
        }
        after(...args) {
            assert.equal(this.length, 1);
            this[0].after(...dom_args(args));
            return this;
        }
        append(...args) {
            assert.equal(this.length, 1);
            this[0].append(...dom_args(args));
            return this;
        }
        attr(name, ...args) {
            assert.notEqual(name, undefined);
            if (args.length === 0) {
                return 0 in this ? (this[0].getAttribute(name) ?? undefined) : undefined;
            }
            const [value] = args;
            for (const element of this) {
                element.setAttribute(name, value);
            }
            return this;
        }
        before(...args) {
            assert.equal(this.length, 1);
            this[0].before(...dom_args(args));
            return this;
        }
        caret(...args) {
            if (args.length === 0) {
                return this[0]?.selectionStart;
            }
            assert.equal(typeof args[0], "number", "zjquery does not support this caret() call");
            for (const element of this) {
                element.setSelectionRange(args[0], args[0]);
            }
            return this;
        }
        children(selector = "*") {
            return new exports.FakeJQuery(
                [...this].flatMap((element) =>
                    [...element.children].filter((child) => child.matches(selector)),
                ),
            );
        }
        closest(selector) {
            return new exports.FakeJQuery(
                [...this].flatMap((element) => element.closest(selector) ?? []),
            );
        }
        contents() {
            return new exports.FakeJQuery([...this].flatMap((element) => [...element.childNodes]));
        }
        css(property, ...args) {
            if (args.length === 0 && typeof property === "string") {
                if (!(0 in this)) {
                    return undefined;
                }
                return fake_element_state
                    .get(this[0])
                    .computed_style.getPropertyValue(decamel(property));
            }

            if (args.length === 0 && Array.isArray(property)) {
                if (!(0 in this)) {
                    return undefined;
                }
                const state = fake_element_state.get(this[0]);
                return Object.fromEntries(
                    property.map((key) => [
                        key,
                        state.computed_style.getPropertyValue(decamel(key)),
                    ]),
                );
            }

            for (const element of this) {
                for (const [key, value] of Object.entries(
                    typeof property === "string" ? {[property]: args[0]} : property,
                )) {
                    element.style.setProperty(
                        decamel(key),
                        typeof value === "number" &&
                            auto_px.test(camel(key).replace(/^./, (c) => c.toUpperCase()))
                            ? `${value}px`
                            : value,
                    );
                }
            }
            return this;
        }
        data(key, ...args) {
            if (args.length === 0) {
                if (!(0 in this)) {
                    return undefined;
                }
                const state = fake_element_state.get(this[0]);
                if (state.jquery_data.has(key)) {
                    return state.jquery_data.get(key);
                }
                let value = this[0].getAttribute(dataset_key_to_attribute(key));

                if (value === null) {
                    return null;
                }

                if (/^true$|^false$|^null$|^{.*}$|^\[.*]$/s.test(value)) {
                    try {
                        value = JSON.parse(value);
                    } catch {
                        // use the unparsed value
                    }
                } else if (Number(value).toString() === value) {
                    value = Number(value);
                }

                state.jquery_data.set(key, value);
                return value;
            }

            const [value] = args;
            for (const element of this) {
                fake_element_state.get(element).jquery_data.set(key, value);
            }
            return this;
        }
        detach() {
            for (const element of this) {
                element.remove();
            }
            return this;
        }
        each(callback) {
            for (const [index, element] of [...this].entries()) {
                callback.call(element, index, element);
            }
            return this;
        }
        empty() {
            for (const element of this) {
                fake_element_state.get(element).query_results.clear();
                element.innerHTML = "";
            }
            return this;
        }
        expectOne() {
            // silently do nothing
            return this;
        }
        fadeIn() {
            for (const element of this) {
                fake_element_state.get(element).shown = true;
            }
            return this;
        }
        fadeOut() {
            for (const element of this) {
                fake_element_state.get(element).shown = false;
            }
            return this;
        }
        fadeTo() {
            return this;
        }
        filter(arg) {
            return new exports.FakeJQuery(
                [...this].filter(
                    typeof arg === "function"
                        ? (element, index) => arg.call(element, index, element)
                        : (element) => element.matches(arg),
                ),
            );
        }
        find(selector) {
            return new exports.FakeJQuery(
                [...this].flatMap((element) => [...element.querySelectorAll(selector)]),
            );
        }
        get(index) {
            return index === undefined ? [...this] : this[index];
        }
        get_on_handler(event_type, child_selector) {
            assert.ok(0 in this);
            const state = fake_element_state.get(this[0]);

            if (child_selector === undefined) {
                const handler = state.event_handlers.get(event_type);
                assert.ok(handler !== undefined, `no ${event_type} handler for ${state.selector}`);
                return handler;
            }

            const handler = state.delegated_event_handlers.get(child_selector)?.get(event_type);
            assert.ok(
                handler !== undefined,
                `no ${event_type} handler for ${state.selector} ${child_selector}`,
            );
            return handler;
        }
        hasClass(class_name) {
            return [...this].some((element) => element.classList.contains(class_name));
        }
        height(...args) {
            if (args.length === 0) {
                if (!(0 in this)) {
                    return undefined;
                }
                const state = fake_element_state.get(this[0]);
                const height = state.computed_style.getPropertyValue("height");
                assert.notEqual(
                    height,
                    "",
                    `Please call $(${JSON.stringify(state.selector)}).set_height`,
                );
                assert.ok(height.endsWith("px"));
                return Number(height.slice(0, -"px".length));
            }
            for (const element of this) {
                element.style.setProperty(
                    "height",
                    typeof args[0] === "number" ? `${args[0]}px` : args[0],
                );
            }
            return this;
        }
        hide() {
            for (const element of this) {
                fake_element_state.get(element).shown = false;
            }
            return this;
        }
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
        }
        insertAfter(...args) {
            args = dom_args(args);
            assert.equal(args.length, 1);
            args[0].after(...this);
            return this;
        }
        insertBefore(...args) {
            args = dom_args(args);
            assert.equal(args.length, 1);
            args[0].before(...this);
            return this;
        }
        is(arg) {
            switch (arg) {
                case ":visible":
                    return [...this].some((element) => fake_element_state.get(element).shown);
                case ":focus":
                    return this.is_focused();
                /* istanbul ignore next */
                default:
                    return [...this].some((element) => element.matches(arg));
            }
        }
        is_focused() {
            // is_focused is not a jQuery thing; this is
            // for our testing
            assert.ok(0 in this);
            return fake_element_state.get(this[0]).is_focused;
        }
        last() {
            return new exports.FakeJQuery([...this].slice(-1));
        }
        next(next_selector = "*") {
            assert.equal(this.length, 1);
            const state = fake_element_state.get(this[0]);
            if (!state.jquery_next_results.has(next_selector)) {
                throw new Error(
                    `You need to call $(${JSON.stringify(state.selector)}).set_next_results(${JSON.stringify(next_selector)}, ...)`,
                );
            }
            return state.jquery_next_results.get(next_selector);
        }
        off(event_type, ...args) {
            if (args.length === 0) {
                for (const element of this) {
                    const state = fake_element_state.get(element);
                    state.event_handlers.delete(event_type);
                }
            } else {
                // In the Zulip codebase we never use this form of
                // .off in code that we test: $(...).off('click', child_sel);
                //
                // So we don't support this for now.
                /* istanbul ignore next */
                throw new Error("zjquery does not support this call sequence");
            }
            return this;
        }
        on(event_type, ...args) {
            // parameters will either be
            //    (event_type, handler) or
            //    (event_type, sel, handler)
            if (args.length === 1) {
                const [handler] = args;
                for (const element of this) {
                    const state = fake_element_state.get(element);
                    /* istanbul ignore if */
                    if (state.event_handlers.has(event_type)) {
                        console.info("\nEither the app or the test can be at fault here..");
                        console.info("(sometimes you just want to call $.clear_all_elements();)\n");
                        throw new Error("dup " + event_type + " handler for " + state.selector);
                    }

                    state.event_handlers.set(event_type, handler);
                }
            } else {
                assert.equal(args.length, 2, "wrong number of arguments passed in");

                const [sel, handler] = args;
                assert.equal(typeof sel, "string", "String selectors expected here.");
                assert.equal(typeof handler, "function", "An handler function expected here.");

                for (const element of this) {
                    const state = fake_element_state.get(element);
                    if (!state.delegated_event_handlers.has(sel)) {
                        state.delegated_event_handlers.set(sel, new Map());
                    }
                    const child_on = state.delegated_event_handlers.get(sel);

                    assert.ok(
                        !child_on.has(event_type),
                        `dup ${event_type} handler for ${state.selector} ${sel}`,
                    );

                    child_on.set(event_type, handler);
                }
            }
            return this;
        }
        /* istanbul ignore next */
        one(event_type, handler) {
            return this.on(
                event_type,
                /* istanbul ignore next */ function (...args) {
                    this.off(event_type);
                    return handler.call(this, ...args);
                },
            );
        }
        outerHeight(...args) {
            assert.equal(args.length, 0, "zjquery does not support this outerHeight() call");
            return 0 in this ? this[0].offsetHeight : undefined;
        }
        parent(selector = "*") {
            return new exports.FakeJQuery(
                [...this]
                    .map((element) => element.parentNode)
                    .filter((parent) => parent !== null && parent.matches(selector)),
            );
        }
        parents(selector = "*") {
            return new exports.FakeJQuery(
                [...this].flatMap((element) => {
                    const state = fake_element_state.get(element);
                    if (!state.parents_results.has(selector)) {
                        throw new Error(
                            `You need to call $(${JSON.stringify(state.selector)}).set_parents_result(${JSON.stringify(selector)}, ...)`,
                        );
                    }
                    return state.parents_results.get(selector);
                }),
            );
        }
        prepend(...args) {
            assert.equal(this.length, 1);
            this[0].prepend(...dom_args(args));
            return this;
        }
        prev(prev_selector = "*") {
            assert.equal(this.length, 1);
            const state = fake_element_state.get(this[0]);
            if (!state.jquery_prev_results.has(prev_selector)) {
                throw new Error(
                    `You need to call $(${JSON.stringify(state.selector)}).set_prev_results(${JSON.stringify(prev_selector)}, ...)`,
                );
            }
            return state.jquery_prev_results.get(prev_selector);
        }
        prop(name, ...args) {
            if (args.length === 0) {
                return this[0]?.[name];
            }
            const [value] = args;
            for (const element of this) {
                element[name] = value;
            }
            return this;
        }
        range(...args) {
            if (args.length === 0) {
                return 0 in this
                    ? {
                          start: this[0].selectionStart,
                          end: this[0].selectionEnd,
                          length: this[0].selectionEnd - this[0].selectionStart,
                          text: this[0].value.slice(this[0].selectionStart, this[0].selectionEnd),
                      }
                    : undefined;
            }
            assert.equal(typeof args[0], "number", "zjquery does not support this range() call");
            for (const element of this) {
                element.setSelectionRange(args[0], args[1]);
            }
            return this;
        }
        removeAttr(name) {
            for (const element of this) {
                element.removeAttribute(name);
            }
            return this;
        }
        removeClass(class_names) {
            class_names = split_words(class_names);
            for (const element of this) {
                element.classList.remove(...class_names);
            }
            return this;
        }
        remove() {
            for (const element of this) {
                element.remove();
                fake_element_state.get(element).jquery_data.clear();
            }
            return this;
        }
        removeData(keys) {
            keys = split_words(keys);
            for (const element of this) {
                const state = fake_element_state.get(element);
                for (const key of keys) {
                    state.jquery_data.delete(key);
                }
            }
            return this;
        }
        replaceWith(...args) {
            assert.equal(this.length, 1);
            this[0].replaceWith(...dom_args(args));
            return this;
        }
        set_children(elements) {
            assert.equal(this.length, 1);
            this[0].children = [...elements];
        }
        set_closest_results(selector, elements) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).closest_results.set(selector, elements[0] ?? null);
        }
        set_contents(nodes) {
            assert.equal(this.length, 1);
            this[0].childNodes = [...nodes];
        }
        set_find_results(selector, elements) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).query_results.set(selector, [...elements]);
        }
        set_height(fake_height) {
            for (const element of this) {
                fake_element_state
                    .get(element)
                    .computed_style.setProperty(
                        "height",
                        typeof fake_height === "number" ? `${fake_height}px` : fake_height,
                    );
            }
        }
        set_matches(selector, value) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).match_results.set(selector, value);
        }
        set_next_results(selector, $result) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).jquery_next_results.set(selector, $result);
        }
        set_parent($parent_elem) {
            assert.equal(this.length, 1);
            assert.equal($parent_elem.length, 1);
            this[0].parentNode = $parent_elem[0];
        }
        set_parents_result(selector, elements) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).parents_results.set(selector, [...elements]);
        }
        set_prev_results(selector, $result) {
            assert.equal(this.length, 1);
            fake_element_state.get(this[0]).jquery_prev_results.set(selector, $result);
        }
        show() {
            for (const element of this) {
                fake_element_state.get(element).shown = true;
            }
            return this;
        }
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
        }
        // Used by zjquery to support $($x) === $x
        to_$() {
            return new exports.FakeJQuery([...this]);
        }
        toggle(show) {
            assert.ok([true, false].includes(show));
            for (const element of this) {
                fake_element_state.get(element).shown = show;
            }
            return this;
        }
        toggleClass(class_names, add) {
            class_names = split_words(class_names);
            for (const element of this) {
                for (const class_name of class_names) {
                    element.classList.toggle(class_name, add);
                }
            }
            return this;
        }
        trigger(event_arg, extra_args) {
            for (const element of this) {
                const event = new FakeEvent(
                    typeof event_arg === "string" ? event_arg : event_arg.type,
                    {
                        target: element,
                        currentTarget: element,
                        ...event_arg,
                    },
                );
                const state = fake_element_state.get(element);
                const func = state.event_handlers.get(event.type);

                if (func) {
                    // It's possible that test code will trigger events
                    // that haven't been set up yet, but we are trying to
                    // eventually deprecate trigger in our codebase, so for
                    // now we just let calls to trigger silently do nothing.
                    // (And I think actual jQuery would do the same thing.)
                    func.call(
                        element,
                        event,
                        ...(Array.isArray(extra_args) ? extra_args : [extra_args]),
                    );
                }

                if (event.type === "focus" || event.type === "focusin") {
                    state.is_focused = true;
                } else if (event.type === "blur" || event.type === "focusout") {
                    state.is_focused = false;
                }
            }
            return this;
        }
        unwrap(...args) {
            assert.equal(args.length, 0, "zjquery does not support this unwrap() call");
            for (const element of this) {
                element.parentNode.replaceWith(element.childNodes);
            }
            return this;
        }
        val(...args) {
            if (args.length === 0) {
                return 0 in this ? (this[0].value ?? "") : undefined;
            }
            const [value] = args;
            for (const element of this) {
                element.value = value;
            }
            return this;
        }
        visible() {
            return [...this].some((element) => fake_element_state.get(element).shown);
        }
        [ignore_missing](property) {
            return [
                `${Number(property) >>> 0}`, // eslint-disable-line no-bitwise
                "__esModule",
                "stack",
            ].includes(property);
        }
    };
}
