"use strict";

/* USAGE:
    Toggle x = components.toggle({
        selected: Integer selected_index,
        values: Array<Object> [
            { label: i18n.t("String title") }
        ],
        callback: function () {
            // .. on value change.
        },
    }).get();
*/

exports.toggle = function (opts) {
    const component = (function render_component(opts) {
        const _component = $("<div class='tab-switcher'></div>");
        if (opts.html_class) {
            // add a check inside passed arguments in case some extra
            // classes need to be added for correct alignment or other purposes
            _component.addClass(opts.html_class);
        }
        opts.values.forEach((value, i) => {
            // create a tab with a tab-id so they don't have to be referenced
            // by text value which can be inconsistent.
            const tab = $(
                "<div class='ind-tab' data-tab-key='" +
                    value.key +
                    "' data-tab-id='" +
                    i +
                    "' tabindex='0'>" +
                    value.label +
                    "</div>",
            );

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
    })(opts);

    const meta = {
        $ind_tab: component.find(".ind-tab"),
        idx: -1,
    };

    // Returns false if the requested tab is disabled.
    function select_tab(idx) {
        const elem = meta.$ind_tab.eq(idx);
        if (elem.hasClass("disabled")) {
            return false;
        }
        meta.$ind_tab.removeClass("selected");

        elem.addClass("selected");

        meta.idx = idx;
        if (opts.callback) {
            opts.callback(opts.values[idx].label, opts.values[idx].key);
        }

        if (!opts.child_wants_focus) {
            elem.trigger("focus");
        }
        return true;
    }

    function maybe_go_left() {
        // Select the first non-disabled tab to the left, if any.
        let i = 1;
        while (meta.idx - i >= 0) {
            if (select_tab(meta.idx - i)) {
                return true;
            }
            i += 1;
        }
        return false;
    }

    function maybe_go_right() {
        // Select the first non-disabled tab to the right, if any.
        let i = 1;
        while (meta.idx + i <= opts.values.length - 1) {
            if (select_tab(meta.idx + i)) {
                return true;
            }
            i += 1;
        }
        return false;
    }

    (function () {
        meta.$ind_tab.on("click", function () {
            const idx = $(this).data("tab-id");
            select_tab(idx);
        });

        keydown_util.handle({
            elem: meta.$ind_tab,
            handlers: {
                left_arrow: maybe_go_left,
                right_arrow: maybe_go_right,
            },
        });

        // We should arguably default opts.selected to 0.
        if (typeof opts.selected === "number") {
            select_tab(opts.selected);
        }
    })();

    const prototype = {
        // Skip disabled tabs and go to the next one.
        maybe_go_left,
        maybe_go_right,

        disable_tab(name) {
            const value = opts.values.find((o) => o.key === name);

            const idx = opts.values.indexOf(value);
            meta.$ind_tab.eq(idx).addClass("disabled");
        },

        enable_tab(name) {
            const value = opts.values.find((o) => o.key === name);

            const idx = opts.values.indexOf(value);
            meta.$ind_tab.eq(idx).removeClass("disabled");
        },

        value() {
            if (meta.idx >= 0) {
                return opts.values[meta.idx].label;
            }
            /* istanbul ignore next */
            return undefined;
        },

        get() {
            return component;
        },
        // go through the process of finding the correct tab for a given name,
        // and when found, select that one and provide the proper callback.
        goto(name) {
            const value = opts.values.find((o) => o.label === name || o.key === name);

            const idx = opts.values.indexOf(value);

            if (idx >= 0) {
                select_tab(idx);
            }
        },
    };

    return prototype;
};

window.components = exports;
