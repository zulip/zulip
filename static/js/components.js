var components = (function () {

var exports = {};

exports.toggle = (function () {
    var keys = {};

    var __toggle = function (opts) {
        var component = (function render_component(opts) {
            var _component = $("<div class='tab-switcher'></div>");
            opts.values.forEach(function (value, i) {
                var tab = $("<div class='ind-tab' data-tab-id='" + i + "'>" + value.label + "</div>");
                if (i === 0) {
                    tab.addClass("first");
                } else {
                    tab.addClass("second");
                }
                _component.append(tab);
            });
            return _component;
        }(opts));

        var meta = {
            retrieved: false,
            $ind_tab: component.find(".ind-tab")
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
                var sel = component.find(".selected");

                if (sel.length > 0) {
                    var id = +sel.eq(0).data("tab-id");
                    return opts.values[id].label;
                }
            },
            get: function () {
                return component;
            }
        };

        if (opts.name) {
            keys[opts.name] = {
                opts: opts,
                component: component,
                value: prototype.value
            };
        }

        return prototype;
    };

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
