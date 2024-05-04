import $ from "jquery";
import assert from "minimalistic-assert";

import * as buddy_data from "./buddy_data";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as sidebar_ui from "./sidebar_ui";

export class UserSearch {
    // This is mostly view code to manage the user search widget
    // above the buddy list.  We rely on other code to manage the
    // details of populating the list when we change.

    $widget = $("#user_search_section").expectOne();
    $input = $<HTMLInputElement>("input.user-list-filter").expectOne();
    _reset_items: () => void;
    _update_list: () => void;
    _on_focus: () => void;

    constructor(opts: {reset_items: () => void; update_list: () => void; on_focus: () => void}) {
        this._reset_items = opts.reset_items;
        this._update_list = opts.update_list;
        this._on_focus = opts.on_focus;

        $("#clear_search_people_button").on("click", () => {
            this.clear_search();
        });
        $("#userlist-header").on("click", () => {
            this.toggle_filter_displayed();
        });

        this.$input.on("input", () => {
            buddy_data.set_is_searching_users(this.$input.val() !== "");
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

    empty(): boolean {
        return this.text() === "";
    }

    // This clears search input but doesn't close
    // the search widget unless it was already empty.
    clear_search(): void {
        buddy_data.set_is_searching_users(false);

        if (this.empty()) {
            this.close_widget();
            return;
        }

        this.$input.val("");
        this.$input.trigger("blur");
        this._reset_items();
    }

    // This always clears and closes search.
    clear_and_hide_search(): void {
        this.clear_search();
        this._update_list();
        this.close_widget();
    }

    hide_widget(): void {
        this.$widget.addClass("notdisplayed");
        resize.resize_sidebars();
    }

    show_widget(): void {
        // Hide all the popovers.
        popovers.hide_all();
        this.$widget.removeClass("notdisplayed");
        resize.resize_sidebars();
    }

    widget_shown(): boolean {
        return this.$widget.hasClass("notdisplayed");
    }

    close_widget(): void {
        this.$input.trigger("blur");
        this.hide_widget();
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
        this.show_widget();
        // Needs to be called when input is visible after fix_invite_user_button_flicker.
        setTimeout(() => {
            this.$input.trigger("focus");
        }, 0);
    }

    toggle_filter_displayed(): void {
        if (this.widget_shown()) {
            this.initiate_search();
        } else {
            this.clear_and_hide_search();
        }
    }

    on_focus(e: JQuery.FocusEvent): void {
        this._on_focus();
        e.stopPropagation();
    }
}
