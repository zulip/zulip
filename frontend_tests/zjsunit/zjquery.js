var noop = function () {};

var exports = {};

exports.make_event_store = (selector) => {
    /*

       This function returns an event_store object that
       simulates the behavior of .on and .off from jQuery.

       It also has methods to retrieve handlers that have
       been set via .on (or similar methods), which can
       be useful for tests that want to test the actual
       handlers.

    */
    var on_functions = new Dict();
    var child_on_functions = new Dict();

    function generic_event(event_name, arg) {
        if (typeof arg === 'function') {
            on_functions.set(event_name, arg);
        } else {
            var handler = on_functions.get(event_name);
            if (!handler) {
                var error = 'Cannot find ' + event_name + ' handler for ' + selector;
                throw Error(error);
            }
            handler(arg);
        }
    }

    var self = {
        generic_event: generic_event,

        get_on_handler: function (name, child_selector) {
            var funcs = self.get_on_handlers(name, child_selector);
            var handler_name = name + ' with ' + child_selector;
            if (funcs.length === 0) {
                throw Error('Could not find handler for ' + handler_name);
            }
            if (funcs.length > 1) {
                var remedy = "\nMaybe clear zjquery between tests?";
                throw Error('Found too many handlers for ' + handler_name + remedy);
            }
            return funcs[0];
        },

        get_on_handlers: function (name, child_selector) {
            if (child_selector === undefined) {
                return on_functions.get(name) || [];
            }

            var child_on = child_on_functions.get(child_selector) || {};
            if (!child_on) {
                return [];
            }

            return child_on.get(name) || [];
        },

        off: function () {
            var event_name;

            if (arguments.length === 2) {
                event_name = arguments[0];
                on_functions[event_name] = [];
            } else if (arguments.length === 3) {
                event_name = arguments[0];
                var sel = arguments[1];
                var child_on = child_on_functions.setdefault(sel, new Dict());
                child_on[event_name] = [];
            }
        },

        on: function () {
            // parameters will either be
            //    (event_name, handler) or
            //    (event_name, sel, handler)
            var event_name;
            var sel;
            var handler;

            // For each event_name (or event_name/sel combo), we will store an
            // array of functions that are mapped to the event (or event/selector).
            //
            // Usually funcs is an array of just one element, but not always.
            var funcs;

            if (arguments.length === 2) {
                event_name = arguments[0];
                handler = arguments[1];
                funcs = on_functions.setdefault(event_name, []);
                funcs.push(handler);
            } else if (arguments.length === 3) {
                event_name = arguments[0];
                sel = arguments[1];
                handler = arguments[2];
                assert.equal(typeof sel, 'string', 'String selectors expected here.');
                assert.equal(typeof handler, 'function', 'An handler function expected here.');
                var child_on = child_on_functions.setdefault(sel, new Dict());
                funcs = child_on.setdefault(event_name, []);
                funcs.push(handler);
            }
        },

        trigger: function (ev) {
            var ev_name = typeof ev === 'string' ? ev : ev.name;
            var funcs = on_functions.get(ev_name) || [];
            // The following assertion is temporary.  It can be
            // legitimate for code to trigger multiple handlers.
            // But up until now, we haven't needed this, and if
            // you come across this assertion, it's possible that
            // you can simplify your tests by just doing your own
            // mocking of trigger().  If you really know what you
            // are doing, you can remove this limitation.
            assert(funcs.length <= 1, 'multiple functions set up');

            _.each(funcs, function (f) {
                f(ev.data);
            });
        },
    };

    return self;
};

exports.make_new_elem = function (selector, opts) {
    var html = 'never-been-set';
    var text = 'never-been-set';
    var value;
    var css;
    var shown = false;
    var focused = false;
    var find_results = new Dict();
    var my_parent;
    var parents_result = new Dict();
    var properties = new Dict();
    var attrs = new Dict();
    var classes = new Dict();
    var event_store = exports.make_event_store(selector);

    var self = {
        add_child: function () {
            // TODO: Remove this once some in-flight PRs
            //       get merged.
            assert(false, 'Use set_find_results instead.');
        },
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
        data: noop,
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
            var child = find_results.get(child_selector);
            if (child) {
                return child;
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
        get_on_handlers: function (name, child_selector) {
            return event_store.get_on_handlers(name, child_selector);
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
        off: function () {
            event_store.off.apply(undefined, arguments);
            return self;
        },
        on: function () {
            event_store.on.apply(undefined, arguments);
            return self;
        },
        parent: function () {
            return my_parent;
        },
        parents: function (parents_selector) {
            var result = parents_result.get(parents_selector);
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
            attrs.del(name);
            return self;
        },
        removeClass: function (class_names) {
            class_names = class_names.split(' ');
            class_names.forEach(function (class_name) {
                classes.del(class_name);
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
        set_parent: function (parent_elem) {
            my_parent = parent_elem;
        },
        set_parents_result: function (selector, result) {
            parents_result.set(selector, result);
        },
        stop: function () {
            return self;
        },
        text: function (arg) {
            if (arg !== undefined) {
                text = arg;
                return self;
            }
            return text;
        },
        trigger: function (ev) {
            event_store.trigger(ev);
            return self;
        },
        val: function () {
            if (arguments.length === 0) {
                return value || '';
            }
            value = arguments[0];
            return self;
        },
        css: function () {
            if (arguments.length === 0) {
                return css || {};
            }
            css = arguments[0];
            return self;
        },
        visible: function () {
            return shown;
        },
    };

    if (selector[0] === '<') {
        self.html(selector);
    }

    self[0] = 'you-must-set-the-child-yourself';

    self.selector = selector;

    return self;
};

exports.make_zjquery = function (opts) {
    opts = opts || {};

    var elems = {};

    // Our fn structure helps us simulate extending jQuery.
    var fn = {};

    function add_extensions(obj) {
        _.each(fn, (v, k) => {
            obj[k] = v;
        });
    }

    function new_elem(selector) {
        var elem = exports.make_new_elem(selector, {
            silent: opts.silent,
        });
        add_extensions(elem);
        return elem;
    }

    var zjquery = function (arg, arg2) {
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
        if (arg.selector) {
            if (elems[arg.selector]) {
                return arg;
            }
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

        var selector = arg;

        if (typeof selector !== "string") {
            console.info(arg);
            throw Error("zjquery does not know how to wrap this object yet");
        }

        var valid_selector =
            '<#.'.indexOf(selector[0]) >= 0 ||
            selector === 'window-stub' ||
            selector === 'document-stub' ||
            selector === 'body' ||
            selector === 'html' ||
            selector.location ||
            selector.indexOf('#') >= 0 ||
            selector.indexOf('.') >= 0 ||
            selector.indexOf('[') >= 0 && selector.indexOf(']') >= selector.indexOf('[');

        assert(valid_selector,
               'Invalid selector: ' + selector +
               ' Use $.create() maybe?');


        if (elems[selector] === undefined) {
            var elem = new_elem(selector);
            elems[selector] = elem;
        }
        return elems[selector];
    };

    zjquery.create = function (name)  {
        assert(!elems[name],
               'You already created an object with this name!!');
        var elem = new_elem(name);
        elems[name] = elem;
        return elems[name];
    };

    zjquery.stub_selector = function (selector, stub) {
        elems[selector] = stub;
    };

    zjquery.trim = function (s) { return s; };

    zjquery.state = function () {
        // useful for debugging
        var res =  _.map(elems, function (v) {
            return v.debug();
        });

        res = _.map(res, function (v) {
            return [v.selector, v.value, v.shown];
        });

        res.sort();

        return res;
    };

    zjquery.Event = function (name, data) {
        return {
            name: name,
            data: data,
        };
    };

    zjquery.extend = function (content, container) {
        return _.extend(content, container);
    };

    zjquery.fn = fn;

    zjquery.clear_all_elements = function () {
        elems = {};
    };

    return zjquery;
};

module.exports = exports;
