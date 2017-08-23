var noop = function () {};

var exports = {};

exports.make_zjquery = function () {

    var elems = {};

    function new_elem(selector) {
        var html = 'never-been-set';
        var text = 'never-been-set';
        var value;
        var shown = false;
        var focused = false;
        var find_results = new Dict();
        var my_parent;
        var parents_result = new Dict();
        var properties = new Dict();
        var attrs = new Dict();
        var classes = new Dict();
        var on_functions = new Dict();
        var child_on_functions = new Dict();

        function generic_event(event_name, arg) {
            if (typeof(arg) === 'function') {
                on_functions.set(event_name, arg);
            } else {
                var handler = on_functions.get(event_name);
                assert(handler);
                handler(arg);
            }
        }

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
                generic_event('click', arg);
                return self;
            },
            css: noop,
            data: noop,
            debug: function () {
                return {
                    value: value,
                    shown: shown,
                    selector: selector,
                };
            },
            empty: noop,
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

                throw Error("Cannot find " + child_selector + " in " + selector);
            },
            focus: function () {
                focused = true;
                return self;
            },
            get: function (idx) {
                // We have some legacy code that does $('foo').get(0).
                assert.equal(idx, 0);
                return selector;
            },
            get_on_handler: function (name, child_selector) {
                var funcs = self.get_on_handlers(name, child_selector);
                assert.equal(funcs.length, 1, 'We expected to have exactly one handler here.');
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
            is_focused: function () {
                // is_focused is not a jQuery thing; this is
                // for our testing
                return focused;
            },
            keydown: function (arg) {
                generic_event('keydown', arg);
                return self;
            },
            keyup: function (arg) {
                generic_event('keyup', arg);
                return self;
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
                    assert.equal(typeof(sel), 'string', 'String selectors expected here.');
                    assert.equal(typeof(handler), 'function', 'An handler function expected here.');
                    var child_on = child_on_functions.setdefault(sel, new Dict());
                    funcs = child_on.setdefault(event_name, []);
                    funcs.push(handler);
                }
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
            removeClass: function (class_name) {
                classes.del(class_name);
                return self;
            },
            remove: function () {
                return self;
            },
            removeData: noop,
            select: function (arg) {
                generic_event('select', arg);
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
                var funcs = on_functions.get(ev.name) || [];

                // The following assertion is temporary.  It can be
                // legitimate for code to trigger multiple handlers.
                // But up until now, we haven't needed this, and if
                // you come across this assertion, it's possible that
                // you can sselfify your tests by just doing your own
                // mocking of trigger().  If you really know what you
                // are doing, you can remove this limitation.
                assert(funcs.length <= 1, 'multiple functions set up');

                _.each(funcs, function (f) {
                    f(ev.data);
                });
                return self;
            },
            val: function () {
                if (arguments.length === 0) {
                    return value || '';
                }
                value = arguments[0];
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

        return self;
    }

    var zjquery = function (arg) {
        if (typeof arg === "function") {
            // If somebody is passing us a function, we emulate
            // jQuery's behavior of running this function after
            // page load time.  But there are no pages to load,
            // so we just call it right away.
            arg();
            return;
        } else if (typeof arg === "object") {
            // If somebody is passing us an element, we return
            // the element itself if it's been created with
            // zjquery.
            // This may happen in cases like $(this).
            if (arg.debug) {
                var this_selector = arg.debug().selector;
                if (elems[this_selector]) {
                    return arg;
                }
            }
        }

        var selector = arg;

        var valid_selector =
            ('<#.'.indexOf(selector[0]) >= 0) ||
            (selector === 'window-stub') ||
            (selector === 'document-stub') ||
            (selector === 'html') ||
            (selector.location) ||
            (selector.indexOf('#') >= 0) ||
            (selector.indexOf('.') >= 0);

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

    return zjquery;
};

module.exports = exports;
