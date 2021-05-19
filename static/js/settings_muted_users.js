import $ from "jquery";

import render_muted_user_ui_row from "../templates/muted_user_ui_row.hbs";

import * as ListWidget from "./list_widget";
import * as muting from "./muting";
import * as muting_ui from "./muting_ui";
import * as people from "./people";
import * as ui from "./ui";

export let loaded = false;

export function populate_list() {
    const muted_users = muting.get_muted_users().map((user) => ({
        user_id: user.id,
        user_name: people.get_full_name(user.id),
        date_muted_str: user.date_muted_str,
    }));
    const muted_users_table = $("#muted_users_table");
    const $search_input = $("#muted_users_search");

    ListWidget.create(muted_users_table, muted_users, {
        name: "muted-users-list",
        modifier(muted_users) {
            return render_muted_user_ui_row({muted_users});
        },
        filter: {
            element: $search_input,
            predicate(item, value) {
                return item.user_name.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar(muted_users_table.closest(".progressive-table-wrapper"));
            },
        },
        parent_container: $("#muted-user-settings"),
        simplebar_container: $("#muted-user-settings .progressive-table-wrapper"),
    });
}

export function set_up() {
    loaded = true;
    $("body").on("click", ".settings-unmute-user", function (e) {
        const $row = $(this).closest("tr");
        const user_id = Number.parseInt($row.attr("data-user-id"), 10);

        e.stopPropagation();
        muting_ui.unmute_user(user_id);
    });

    populate_list();
}

export function reset() {
    loaded = false;
}
