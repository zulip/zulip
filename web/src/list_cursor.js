import $ from "jquery";

import * as blueslip from "./blueslip";
import * as scroll_util from "./scroll_util";

export class ListCursor {
    constructor({highlight_class, list}) {
        const config_ok =
            highlight_class &&
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

        this.highlight_class = highlight_class;
        this.list = list;
    }

    clear() {
        if (this.curr_key === undefined) {
            return;
        }
        const row = this.get_row(this.curr_key);
        if (row) {
            row.clear();
        }
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
            highlight: () => {
                $li.addClass(this.highlight_class);
                this.adjust_scroll($li);
            },
            clear: () => {
                $li.removeClass(this.highlight_class);
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
        this.clear();
        const row = this.get_row(key);
        if (row === undefined) {
            blueslip.error("Cannot highlight key for ListCursor", {key});
            return;
        }
        this.curr_key = key;
        row.highlight();
    }

    reset() {
        this.clear();
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
            // leave the current key
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
}
