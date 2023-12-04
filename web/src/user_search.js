import $ from "jquery";

import * as buddy_data from "./buddy_data";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as sidebar_ui from "./sidebar_ui";

export class UserSearch {
    // This is mostly view code to manage the user search widget
    // above the buddy list.  We rely on other code to manage the
    // details of populating the list when we change.

    $widget = $("#user_search_section").expectOne();
    $input = $(".user-list-filter").expectOne();

    constructor(opts) {
        this._reset_items = opts.reset_items;
        this._update_list = opts.update_list;
        this._on_focus = opts.on_focus;

        $("#clear_search_people_button").on("click", () => this.clear_search());
        $("#userlist-header").on("click", () => this.toggle_filter_displayed());

        this.$input.on("input", () => {
            buddy_data.set_is_searching_users(this.$input.val() !== "");
            opts.update_list();
        });
        this.$input.on("focus", (e) => this.on_focus(e));
    }

    input_field() {
        return this.$input;
    }

    text() {
        return this.$input.val().trim();
    }

    searching() {
        return this.$input.is(":focus");
    }

    empty() {
        return this.text() === "";
    }

    // This clears search input but doesn't close
    // the search widget unless it was already empty.
    clear_search() {
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
    clear_and_hide_search() {
        this.clear_search();
        this._update_list();
        this.close_widget();
    }

    hide_widget() {
        this.$widget.addClass("notdisplayed");
        resize.resize_sidebars();
    }

    show_widget() {
        // Hide all the popovers.
        popovers.hide_all();
        this.$widget.removeClass("notdisplayed");
        resize.resize_sidebars();
    }

    widget_shown() {
        return this.$widget.hasClass("notdisplayed");
    }

    close_widget() {
        this.$input.trigger("blur");
        this.hide_widget();
        this._reset_items();
    }

    expand_column() {
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

    initiate_search() {
        this.expand_column();
        this.show_widget();
        this.$input.trigger("focus");
    }

    toggle_filter_displayed() {
        if (this.widget_shown()) {
            this.initiate_search();
        } else {
            this.clear_and_hide_search();
        }
    }

    on_focus(e) {
        this._on_focus();
        e.stopPropagation();
    }
}
