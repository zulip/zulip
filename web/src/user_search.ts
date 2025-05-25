import $ from "jquery";
import assert from "minimalistic-assert";

import * as buddy_data from "./buddy_data.ts";
import * as popovers from "./popovers.ts";
import * as sidebar_ui from "./sidebar_ui.ts";

export class UserSearch {
    // This is mostly view code to manage the user search widget
    // above the buddy list.  We rely on other code to manage the
    // details of populating the list when we change.

    $widget = $("#userlist-header-search").expectOne();
    $input = $<HTMLInputElement>("input.user-list-filter").expectOne();
    _reset_items: () => void;
    _update_list: () => void;
    _on_focus: () => void;

    constructor(opts: {reset_items: () => void; update_list: () => void; on_focus: () => void}) {
        this._reset_items = opts.reset_items;
        this._update_list = opts.update_list;
        this._on_focus = opts.on_focus;

        $("#userlist-header-search .input-button").on("click", () => {
            this.clear_search();
        });

        this.$input.on("input", () => {
            const input_is_empty = this.$input.val() === "";
            buddy_data.set_is_searching_users(!input_is_empty);
            opts.update_list();
        });
        this.$input.on("focus", (e) => {
            this.on_focus(e);
        });
    }

    input_field(): JQuery {
        return this.$input;
    }

    text(): string {
        const input_val = this.$input.val();
        assert(input_val !== undefined);
        return input_val.trim();
    }

    searching(): boolean {
        return this.$input.is(":focus");
    }

    // This clears search input but doesn't close
    // the search widget unless it was already empty.
    clear_search(): void {
        buddy_data.set_is_searching_users(false);

        this.$input.val("");
        this.$input.trigger("blur");
        this._reset_items();
    }

    expand_column(): void {
        const $column = this.$input.closest(".app-main [class^='column-']");
        if (!$column.hasClass("expanded")) {
            popovers.hide_all();
            if ($column.hasClass("column-left")) {
                sidebar_ui.show_streamlist_sidebar();
            } else if ($column.hasClass("column-right")) {
                sidebar_ui.show_userlist_sidebar();
            }
        }
    }

    initiate_search(): void {
        this.expand_column();
        // Needs to be called when input is visible after fix_invite_user_button_flicker.
        setTimeout(() => {
            this.$input.trigger("focus");
        }, 0);
    }

    on_focus(e: JQuery.FocusEvent): void {
        this._on_focus();
        e.stopPropagation();
    }
}
