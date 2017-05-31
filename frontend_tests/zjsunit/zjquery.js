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
        var children = new Dict();
        var my_parent;
        var classes = new Dict();

        var self = {
            val: function () {
                if (arguments.length === 0) {
                    return value || '';
                }
                value = arguments[0];
            },
            css: noop,
            data: noop,
            empty: noop,
            height: noop,
            removeAttr: noop,
            removeData: noop,
            trigger: noop,
            blur: function () {
                focused = false;
            },
            html: function (arg) {
                if (arg !== undefined) {
                    html = arg;
                } else {
                    return html;
                }
            },
            text: function (arg) {
                if (arg !== undefined) {
                    text = arg;
                } else {
                    return text;
                }
            },
            focus: function () {
                focused = true;
            },
            show: function () {
                shown = true;
            },
            hide: function () {
                shown = false;
            },
            addClass: function (class_name) {
                classes.set(class_name, true);
                return self;
            },
            removeClass: function (class_name) {
                classes.del(class_name);
                return self;
            },
            hasClass: function (class_name) {
                return classes.has(class_name);
            },
            debug: function () {
                return {
                    value: value,
                    shown: shown,
                    selector: selector,
                };
            },
            visible: function () {
                return shown;
            },
            is_focused: function () {
                // is_focused is not a jQuery thing; this is
                // for our testing
                return focused;
            },
            find: function (child_selector) {
                var child = children.get(child_selector);
                if (child) {
                    return child;
                }

                throw Error("Cannot find " + child_selector + " in " + selector);
            },
            add_child: function (child_selector, child_elem) {
                child_elem.set_parent(self);
                children.set(child_selector, child_elem);
            },
            remove_child: function (child_selector) {
                children.del(child_selector);
            },
            set_parent: function (parent_elem) {
                my_parent = parent_elem;
            },
            parent: function () {
                return my_parent;
            },
            expectOne: function () {
                // silently do nothing
                return self;
            },
            on: function () {
                return self;
            },
            remove: function () {
                if (my_parent) {
                    my_parent.remove_child(selector);
                }
            },
        };
        return self;
    }

    function jquery_array(elem) {
        var result = [elem];

        for (var attr in elem) {
            if (Object.prototype.hasOwnProperty.call(elem, attr)) {
                result[attr] = elem[attr];
            }
        }

        return result;
    }

    var zjquery = function (arg) {
        if (typeof arg === "function") {
            // If somebody is passing us a function, we emulate
            // jQuery's behavior of running this function after
            // page load time.  But there are no pages to load,
            // so we just call it right away.
            arg();
            return;
        }

        var selector = arg;
        if (elems[selector] === undefined) {
            var elem = new_elem(selector);
            elems[selector] = jquery_array(elem);
        }
        return elems[selector];
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

    zjquery.Event = noop;

    return zjquery;
};

module.exports = exports;
