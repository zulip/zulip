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

        // store once a copy of the tabs inside the parent in a jQuery object/array.
        var meta = {
            $ind_tab: component.find(".ind-tab"),
            last_value: null,
        };

        (function () {
            meta.$ind_tab.click(function () {
                meta.$ind_tab.removeClass("selected");
                $(this).addClass("selected");
                if (opts.callback) {
                    var id = +$(this).data("tab-id");

                    if (meta.last_value !== opts.values[id].label) {
                        meta.last_value = opts.values[id].label;
                        opts.callback(meta.last_value, opts.values[id].key, {});
                    }
                }
                $(this).focus();
            });

            meta.$ind_tab.keydown(function (e) {
                var key = e.which || e.keyCode;
                var idx = $(this).data("tab-id");

                if (key === 37) {
                    if (idx > 0) {
                        $(this).prev().click();
                    }
                } else if (key === 39) {
                    if (idx < opts.values.length - 1) {
                        $(this).next().click();
                    }
                }
            });
            if (typeof opts.selected === "number") {
                $(component).find(".ind-tab[data-tab-id='" + opts.selected + "']").click();
            }
        }());

        var prototype = {
            value: function () {
                // find whatever is visually selected in the tab switcher.
                var sel = component.find(".selected");

                if (sel.length > 0) {
                    var id = +sel.eq(0).data("tab-id");
                    return opts.values[id].label;
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
                var $this_tab = meta.$ind_tab.filter("[data-tab-id='" + idx + "']");

                if (idx !== -1 && idx !== meta.last_value) {
                    meta.$ind_tab.removeClass("selected");
                    $this_tab.addClass("selected");

                    opts.callback(value.label, value.key, payload || {});

                    meta.last_value = idx;
                }

                $this_tab.focus();
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
