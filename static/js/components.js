var components = (function () {

var exports = {};

/* USAGE:
    Toggle x = components.toggle({
        name: String toggle_name,
        selected: Integer selected_index,
        values: Array<Object> [
            { label: i18n.t(String title) }
        ],
        callback: function () {
            // .. on value change.
        },
    }).get();
*/

exports.toggle = (function () {
    var keys = {};

    var __toggle = function (opts) {
        var component = (function render_component(opts) {
            var _component = $("<div class='tab-switcher'></div>");
            opts.values.forEach(function (value, i) {
                // create a tab with a tab-id so they don't have to be referenced
                // by text value which can be inconsistent.
                var tab = $("<div class='ind-tab' data-tab-key='" + value.key + "' data-tab-id='" + i + "' tabindex='0'>" + value.label + "</div>");

                // add proper classes for styling in CSS.
                if (i === 0) {
                    // this should be default selected unless otherwise specified.
                    tab.addClass("first selected");
                } else if (i === opts.values.length - 1) {
                    tab.addClass("last");
                } else {
                    tab.addClass("middle");
                }
                _component.append(tab);
            });
            return _component;
        }(opts));

        var meta = {
            $ind_tab: component.find(".ind-tab"),
            idx: -1,
        };

        function select_tab(idx, payload) {
            meta.$ind_tab.removeClass("selected");

            var elem = meta.$ind_tab.eq(idx);
            elem.addClass("selected");

            if (idx !== meta.idx) {
                if (opts.callback) {
                    opts.callback(
                        opts.values[idx].label,
                        opts.values[idx].key,
                        payload || {}
                    );
                }
            }

            meta.idx = idx;
            elem.focus();
        }

        function maybe_go_left() {
            if (meta.idx > 0) {
                select_tab(meta.idx - 1);
            }
        }

        function maybe_go_right() {
            if (meta.idx < opts.values.length - 1) {
                select_tab(meta.idx + 1);
            }
        }

        (function () {
            meta.$ind_tab.click(function () {
                var idx = $(this).data("tab-id");
                select_tab(idx);
            });

            meta.$ind_tab.keydown(function (e) {
                var key = e.which || e.keyCode;

                if (key === 37) {
                    maybe_go_left();
                } else if (key === 39) {
                    maybe_go_right();
                }
            });

            if (typeof opts.selected === "number") {
                select_tab(opts.selected);
            }
        }());

        var prototype = {
            value: function () {
                if (meta.idx >= 0) {
                    return opts.values[meta.idx].label;
                }
            },

            get: function () {
                return component;
            },
            // go through the process of finding the correct tab for a given name,
            // and when found, select that one and provide the proper callback.
            // supply a payload of data; since this is a custom event, we'll pass
            // the data through to the callback.
            goto: function (name, payload) {
                // there are cases in which you would want to set this tab, but
                // not to run the content inside the callback because it doesn't
                // need to be initialized.
                var value = _.find(opts.values, function (o) {
                    return o.label === name || o.key === name;
                });

                var idx = opts.values.indexOf(value);

                if (idx >= 0) {
                    select_tab(idx, payload);
                }
            },
        };

        if (opts.name) {
            keys[opts.name] = {
                opts: opts,
                component: component,
                value: prototype.value,
                goto: prototype.goto,
            };
        }

        return prototype;
    };

    // look up a toggle globally by the name you set it as and return
    // the prototype.
    __toggle.lookup = function (id) {
        return keys[id];
    };

    return __toggle;
}());

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = components;
}
