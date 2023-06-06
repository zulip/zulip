import $ from "jquery";

import * as blueslip from "./blueslip";
import * as keydown_util from "./keydown_util";
import * as scroll_util from "./scroll_util";

export class ListCursor {
    constructor({list, $search_input, on_select, vdot_icon_class}) {
        const config_ok =
            list &&
            list.scroll_container_sel &&
            list.find_li &&
            list.first_key &&
            list.prev_key &&
            list.next_key;
        if (!config_ok) {
            blueslip.error("Programming error");
            return;
        }

        this.list = list;
        this.$search_input = $search_input;
        this._on_select = on_select;
        this.vdot_icon_class = vdot_icon_class;
    }

    clear() {
        this.curr_key = undefined;
    }

    get_key() {
        return this.curr_key;
    }

    get_row(key) {
        // TODO: The list class should probably do more of the work
        //       here, so we're not so coupled to jQuery, and
        //       so we instead just get back a widget we can say
        //       something like widget.trigger("select") on.  This will
        //       be especially important if we do lazy rendering.
        //       It would also give the caller more flexibility on
        //       the actual styling.
        if (key === undefined) {
            return undefined;
        }

        const $li = this.list.find_li({
            key,
            force_render: true,
        });

        if (!$li || $li.length === 0) {
            return undefined;
        }

        return {
            $li,
            highlight: () => {
                $li.trigger("focus");
                this.adjust_scroll($li);
            },
        };
    }

    adjust_scroll($li) {
        const $scroll_container = $(this.list.scroll_container_sel);
        scroll_util.scroll_element_into_container($li, $scroll_container);
    }

    redraw() {
        // We should only call this for situations like the buddy
        // list where we redraw the whole list without necessarily
        // changing it, so we just want to re-highlight the current
        // row in the new DOM.  If you are filtering, for now you
        // should call the 'reset()' method.
        const row = this.get_row(this.curr_key);

        if (row === undefined) {
            return;
        }
        row.highlight();
    }

    go_to(key) {
        if (key === undefined) {
            blueslip.error("Caller is not checking keys for ListCursor.go_to");
            return;
        }
        if (key === this.curr_key) {
            return;
        }
        const row = this.get_row(key);
        if (row === undefined) {
            blueslip.error("Cannot highlight key for ListCursor", {key});
            return;
        }
        this.curr_key = key;
        row.highlight();
    }

    reset() {
        const key = this.list.first_key();
        if (key === undefined) {
            this.curr_key = undefined;
            return;
        }
        this.go_to(key);
    }

    prev() {
        if (this.curr_key === undefined) {
            return;
        }
        const key = this.list.prev_key(this.curr_key);
        if (key === undefined) {
            // leave the current key and focus search input
            this.$search_input.trigger("focus");
            return;
        }
        this.go_to(key);
    }

    next() {
        if (this.curr_key === undefined) {
            // This is sort of a special case where we went from
            // an empty filter to having data.
            this.reset();
            return;
        }
        const key = this.list.next_key(this.curr_key);
        if (key === undefined) {
            // leave the current key
            return;
        }
        this.go_to(key);
    }

    focus_vdot_icon() {
        if (this.curr_key !== undefined && this.vdot_icon_class !== undefined) {
            const row = this.get_row(this.curr_key);
            const $vdot_icon = row.$li.find(`.${CSS.escape(this.vdot_icon_class)}`);

            $vdot_icon.trigger("focus");
        }
    }

    on_select(key) {
        const row = this.get_row(key);
        let is_vdot_icon_focused = false;
        let $vdot_icon;
        if (this.vdot_icon_class !== undefined) {
            $vdot_icon = row.$li.find(`.${CSS.escape(this.vdot_icon_class)}`);
            is_vdot_icon_focused = $vdot_icon.is(":focus");
        }

        if (is_vdot_icon_focused) {
            $vdot_icon.trigger("click");
        } else {
            this._on_select(key);
        }
    }

    handle_navigation() {
        this.$search_input.on("focus", () => this.clear());

        keydown_util.handle({
            $elem: this.$search_input,
            handlers: {
                ArrowDown: () => {
                    this.next();
                    return true;
                },
            },
        });

        keydown_util.handle({
            $elem: this.list.$container,
            handlers: {
                ArrowDown: () => {
                    this.next();
                    return true;
                },
                ArrowUp: () => {
                    this.prev();
                    return true;
                },
                Enter: () => {
                    if (this.curr_key !== undefined) {
                        this.on_select(this.curr_key);
                    }
                    return true;
                },
                Tab: () => {
                    this.focus_vdot_icon();
                    return true;
                },
            },
        });
    }
}
