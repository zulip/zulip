const noop = function () {};

exports.make_event_store = (selector) => {
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

    function generic_event(event_name, arg) {
        if (typeof arg === 'function') {
            on_functions.set(event_name, arg);
        } else {
            const handler = on_functions.get(event_name);
            if (!handler) {
                const error = 'Cannot find ' + event_name + ' handler for ' + selector;
                throw Error(error);
            }
            handler(arg);
        }
    }

    const self = {
        generic_event: generic_event,

        get_on_handler: function (name, child_selector) {
            let handler;

            if (child_selector === undefined) {
                handler = on_functions.get(name);
                if (!handler) {
                    throw Error('no ' + name + ' handler for ' + selector);
                }
                return handler;
            }

            const child_on = child_on_functions.get(child_selector);
            if (child_on) {
                handler = child_on.get(name);
            }

            if (!handler) {
                throw Error('no ' + name + ' handler for ' + selector + ' ' + child_selector);
            }

            return handler;
        },

        off: function (event_name, ...args) {
            if (args.length === 0) {
                on_functions.delete(event_name);
                return;
            }

            // In the Zulip codebase we never use this form of
            // .off in code that we test: $(...).off('click', child_sel);
            //
            // So we don't support this for now.
            throw Error('zjquery does not support this call sequence');
        },

        on: function (event_name, ...args) {
            // parameters will either be
            //    (event_name, handler) or
            //    (event_name, sel, handler)
            if (args.length === 1) {
                const [handler] = args;
                if (on_functions.has(event_name)) {
                    console.info('\nEither the app or the test can be at fault here..');
                    console.info('(sometimes you just want to call $.clear_all_elements();)\n');
                    throw Error('dup ' + event_name + ' handler for ' + selector);
                }

                on_functions.set(event_name, handler);
                return;
            }

            if (args.length !== 2) {
                throw Error('wrong number of arguments passed in');
            }

            const [sel, handler] = args;
            assert.equal(typeof sel, 'string', 'String selectors expected here.');
            assert.equal(typeof handler, 'function', 'An handler function expected here.');

            if (!child_on_functions.has(sel)) {
                child_on_functions.set(sel, new Map());
            }

            const child_on = child_on_functions.get(sel);

            if (child_on.has(event_name)) {
                throw Error('dup ' + event_name + ' handler for ' + selector + ' ' + sel);
            }

            child_on.set(event_name, handler);
        },

        trigger: function (ev) {
            const ev_name = typeof ev === 'string' ? ev : ev.name;
            const func = on_functions.get(ev_name);

            if (!func) {
                // It's possible that test code will trigger events
                // that haven't been set up yet, but we are trying to
                // eventually deprecate trigger in our codebase, so for
                // now we just let calls to trigger silently do nothing.
                // (And I think actual jQuery would do the same thing.)
                return;
            }

            func(ev.data);
        },
    };

    return self;
};

exports.make_new_elem = function (selector, opts) {
    let html = 'never-been-set';
    let text = 'never-been-set';
    let value;
    let css;
    let shown = false;
    let focused = false;
    const find_results = new Map();
    let my_parent;
    const parents_result = new Map();
    const properties = new Map();
    const attrs = new Map();
    const classes = new Map();
    const event_store = exports.make_event_store(selector);

    const self = {
        addClass: function (class_name) {
            classes.set(class_name, true);
            return self;
        },
        attr: function (name, val) {
            if (val === undefined) {
                return attrs.get(name);
            }
            attrs.set(name, val);
            return self;
        },
        blur: function () {
            focused = false;
            return self;
        },
        click: function (arg) {
            event_store.generic_event('click', arg);
            return self;
        },
        data: function (name, val) {
            if (val === undefined) {
                const data_val = attrs.get('data-' + name);
                if (data_val === undefined) {
                    return;
                }
                return data_val;
            }
            attrs.set('data-' + name, val);
            return self;
        },
        delay: function () {
            return self;
        },
        debug: function () {
            return {
                value: value,
                shown: shown,
                selector: selector,
            };
        },
        empty: function (arg) {
            if (arg === undefined) {
                find_results.clear();
            }
            return self;
        },
        eq: function () {
            return self;
        },
        expectOne: function () {
            // silently do nothing
            return self;
        },
        fadeTo: noop,
        find: function (child_selector) {
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
            if (opts.silent) {
                return self;
            }
            throw Error("Cannot find " + child_selector + " in " + selector);
        },
        focus: function () {
            focused = true;
            return self;
        },
        focusin: function () {
            focused = true;
            return self;
        },
        focusout: function () {
            focused = false;
            return self;
        },
        get: function (idx) {
            // We have some legacy code that does $('foo').get(0).
            assert.equal(idx, 0);
            return selector;
        },
        get_on_handler: function (name, child_selector) {
            return event_store.get_on_handler(name, child_selector);
        },
        hasClass: function (class_name) {
            return classes.has(class_name);
        },
        height: noop,
        hide: function () {
            shown = false;
            return self;
        },
        html: function (arg) {
            if (arg !== undefined) {
                html = arg;
                return self;
            }
            return html;
        },
        is: function (arg) {
            if (arg === ':visible') {
                return shown;
            }
            if (arg === ':focus') {
                return focused;
            }
            return self;
        },
        is_focused: function () {
            // is_focused is not a jQuery thing; this is
            // for our testing
            return focused;
        },
        keydown: function (arg) {
            event_store.generic_event('keydown', arg);
            return self;
        },
        keyup: function (arg) {
            event_store.generic_event('keyup', arg);
            return self;
        },
        off: function (...args) {
            event_store.off(...args);
            return self;
        },
        on: function (...args) {
            event_store.on(...args);
            return self;
        },
        parent: function () {
            return my_parent;
        },
        parents: function (parents_selector) {
            const result = parents_result.get(parents_selector);
            assert(result, 'You need to call set_parents_result for ' +
                            parents_selector + ' in ' + selector);
            return result;
        },
        prop: function (name, val) {
            if (val === undefined) {
                return properties.get(name);
            }
            properties.set(name, val);
            return self;
        },
        removeAttr: function (name) {
            attrs.delete(name);
            return self;
        },
        removeClass: function (class_names) {
            class_names = class_names.split(' ');
            class_names.forEach(function (class_name) {
                classes.delete(class_name);
            });
            return self;
        },
        remove: function () {
            return self;
        },
        removeData: noop,
        replaceWith: function () {
            return self;
        },
        scrollTop: function () {
            return self;
        },
        select: function (arg) {
            event_store.generic_event('select', arg);
            return self;
        },
        set_find_results: function (find_selector, jquery_object) {
            find_results.set(find_selector, jquery_object);
        },
        show: function () {
            shown = true;
            return self;
        },
        serializeArray: function () {
            return self;
        },
        set_parent: function (parent_elem) {
            my_parent = parent_elem;
        },
        set_parents_result: function (selector, result) {
            parents_result.set(selector, result);
        },
        stop: function () {
            return self;
        },
        text: function (...args) {
            if (args.length !== 0) {
                if (args[0] !== undefined) {
                    text = args[0].toString();
                }
                return self;
            }
            return text;
        },
        trigger: function (ev) {
            event_store.trigger(ev);
            return self;
        },
        val: function (...args) {
            if (args.length === 0) {
                return value || '';
            }
            [value] = args;
            return self;
        },
        css: function (...args) {
            if (args.length === 0) {
                return css || {};
            }
            [css] = args;
            return self;
        },
        visible: function () {
            return shown;
        },
        slice: function () {
            return self;
        },
    };

    if (selector[0] === '<') {
        self.html(selector);
    }

    self[0] = 'you-must-set-the-child-yourself';

    self.selector = selector;

    self.length = 1;

    return self;
};

exports.make_zjquery = function (opts) {
    opts = opts || {};

    const elems = new Map();

    // Our fn structure helps us simulate extending jQuery.
    const fn = {};

    function new_elem(selector) {
        const elem = exports.make_new_elem(selector, {
            silent: opts.silent,
        });
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
                if (key === 'stack') {
                    const error = '\nInstead of doing equality checks on a full object, ' +
                        'do `assert_equal(foo.selector, ".some_class")\n';
                    throw Error(error);
                }

                const val = target[key];

                if (val === undefined) {
                    // For undefined values, we'll throw errors to devs saying
                    // they need to create stubs.  We ignore certain keys that
                    // are used for simply printing out the object.
                    if (typeof key === 'symbol') {
                        return;
                    }
                    if (key === 'inspect') {
                        return;
                    }

                    throw Error('You must create a stub for $("' + selector + '").' + key);
                }

                return val;
            },
        };

        const proxy = new Proxy(elem, handler);

        return proxy;
    }

    const zjquery = function (arg, arg2) {
        if (typeof arg === "function") {
            // If somebody is passing us a function, we emulate
            // jQuery's behavior of running this function after
            // page load time.  But there are no pages to load,
            // so we just call it right away.
            arg();
            return;
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
            throw Error("We only use one-argument variations of $(...) in Zulip code.");
        }

        const selector = arg;

        if (typeof selector !== "string") {
            console.info(arg);
            throw Error("zjquery does not know how to wrap this object yet");
        }

        const valid_selector =
            '<#.'.includes(selector[0]) ||
            selector === 'window-stub' ||
            selector === 'document-stub' ||
            selector === 'body' ||
            selector === 'html' ||
            selector.location ||
            selector.includes('#') ||
            selector.includes('.') ||
            selector.includes('[') && selector.indexOf(']') >= selector.indexOf('[');

        assert(valid_selector,
               'Invalid selector: ' + selector +
               ' Use $.create() maybe?');


        if (!elems.has(selector)) {
            const elem = new_elem(selector);
            elems.set(selector, elem);
        }
        return elems.get(selector);
    };

    zjquery.create = function (name)  {
        assert(!elems.has(name),
               'You already created an object with this name!!');
        const elem = new_elem(name);
        elems.set(name, elem);
        return elem;
    };

    zjquery.stub_selector = function (selector, stub) {
        elems.set(selector, stub);
    };

    zjquery.trim = function (s) { return s; };

    zjquery.state = function () {
        // useful for debugging
        let res = Array.from(elems.values(), v => v.debug());

        res = res.map(v => [v.selector, v.value, v.shown]);

        res.sort();

        return res;
    };

    zjquery.Event = function (name, data) {
        return {
            name: name,
            data: data,
        };
    };

    fn.after = function (s) {
        return s;
    };
    fn.before = function (s) {
        return s;
    };

    zjquery.fn = fn;

    zjquery.clear_all_elements = function () {
        elems.clear();
    };
    zjquery.escapeSelector = function (s) {
        return s;
    };

    return zjquery;
};
