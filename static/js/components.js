var components = (function () {

var exports = {};

/* USAGE:
    Toggle x = components.toggle({
        name: String toggle_name,
        selected: Integer selected_index,
        values: Array<Object> [
            { label: String title }
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
                var tab = $("<div class='ind-tab' data-tab-id='" + i + "'>" + value.label + "</div>");

                // add proper classes for styling in CSS.
                if (i === 0) {
                    tab.addClass("first");
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
        };

        (function () {
            var last_value = null;
            meta.$ind_tab.each(function () {
                $(this).click(function () {
                    meta.$ind_tab.removeClass("selected");
                    $(this).addClass("selected");
                    if (opts.callback) {
                        var id = +$(this).data("tab-id");
                        if (last_value !== opts.values[id].label) {
                            last_value = opts.values[id].label;
                            opts.callback(last_value);
                        }
                    }
                });
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
            goto: function (name) {
                var value = _.find(opts.values, function (o) {
                    return o.label === name;
                });

                var idx = opts.values.indexOf(value);

                if (idx !== -1) {
                    meta.$ind_tab.removeClass("selected");
                    meta.$ind_tab.filter("[data-tab-id='" + idx + "']").addClass("selected");

                    value.label = name;
                    opts.callback(name);
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
