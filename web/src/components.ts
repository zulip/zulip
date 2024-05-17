import $ from "jquery";

import * as blueslip from "./blueslip";
import * as keydown_util from "./keydown_util";

/* USAGE:
    Toggle x = components.toggle({
        selected: Integer selected_index,
        values: Array<Object> [
            {label: $t({defaultMessage: "String title"})}
        ],
        callback: function () {
            // .. on value change.
        },
    }).get();
*/

export type Toggle = {
    maybe_go_left: () => boolean;
    maybe_go_right: () => boolean;
    disable_tab: (name: string) => void;
    enable_tab: (name: string) => void;
    value: () => string | undefined;
    get: () => JQuery;
    goto: (name: string) => void;
};

export function toggle(opts: {
    html_class?: string;
    values: {label: string; label_html?: string; key: string}[];
    callback?: (label: string, value: string) => void;
    child_wants_focus?: boolean;
    selected?: number;
}): Toggle {
    const $component = $("<div>").addClass("tab-switcher");
    if (opts.html_class) {
        // add a check inside passed arguments in case some extra
        // classes need to be added for correct alignment or other purposes
        $component.addClass(opts.html_class);
    }
    for (const [i, value] of opts.values.entries()) {
        // create a tab with a tab-id so they don't have to be referenced
        // by text value which can be inconsistent.
        const $tab = $("<div>")
            .addClass("ind-tab")
            .attr({"data-tab-key": value.key, "data-tab-id": i, tabindex: 0});

        /* istanbul ignore if */
        if (value.label_html !== undefined) {
            const html = value.label_html;
            $tab.html(html);
        } else {
            $tab.text(value.label);
        }

        // add proper classes for styling in CSS.
        if (i === 0) {
            // this should be default selected unless otherwise specified.
            $tab.addClass("first selected");
        } else if (i === opts.values.length - 1) {
            $tab.addClass("last");
        } else {
            $tab.addClass("middle");
        }
        $component.append($tab);
    }

    const meta = {
        $ind_tab: $component.find(".ind-tab"),
        idx: -1,
    };

    // Returns false if the requested tab is disabled.
    function select_tab(idx: number): boolean {
        const $elem = meta.$ind_tab.eq(idx);
        if ($elem.hasClass("disabled")) {
            return false;
        }
        meta.$ind_tab.removeClass("selected");

        $elem.addClass("selected");

        meta.idx = idx;
        if (opts.callback) {
            opts.callback(opts.values[idx].label, opts.values[idx].key);
        }

        if (!opts.child_wants_focus) {
            $elem.trigger("focus");
        }
        return true;
    }

    function maybe_go_left(): boolean {
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

    function maybe_go_right(): boolean {
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

    meta.$ind_tab.on("click", function () {
        const idx = Number($(this).attr("data-tab-id"));
        select_tab(idx);
    });

    keydown_util.handle({
        $elem: meta.$ind_tab,
        handlers: {
            ArrowLeft: maybe_go_left,
            ArrowRight: maybe_go_right,
        },
    });

    // We should arguably default opts.selected to 0.
    if (typeof opts.selected === "number") {
        select_tab(opts.selected);
    }

    const prototype = {
        // Skip disabled tabs and go to the next one.
        maybe_go_left,
        maybe_go_right,

        disable_tab(name: string) {
            const value = opts.values.find((o) => o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

            const idx = opts.values.indexOf(value);
            meta.$ind_tab.eq(idx).addClass("disabled");
        },

        enable_tab(name: string) {
            const value = opts.values.find((o) => o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

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
            return $component;
        },
        // go through the process of finding the correct tab for a given name,
        // and when found, select that one and provide the proper callback.
        goto(name: string) {
            const value = opts.values.find((o) => o.label === name || o.key === name);
            if (!value) {
                blueslip.warn("Incorrect tab name given.");
                return;
            }

            const idx = opts.values.indexOf(value);

            if (idx >= 0) {
                select_tab(idx);
            }
        },
    };

    return prototype;
}
