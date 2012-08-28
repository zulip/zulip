import $ from "jquery";

import render_muted_user_ui_row from "../templates/muted_user_ui_row.hbs";

import * as ListWidget from "./list_widget.ts";
import * as muted_users from "./muted_users.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";

export let loaded = false;

type MutedUserItem = {
    user_id: number;
    user_name: string;
    date_muted: number;
    date_muted_str: string;
};

export function populate_list(): void {
    const all_muted_users = muted_users.get_muted_users().map((user) => {
        const muted_user = people.get_user_by_id_assert_valid(user.id);
        return {
            user_id: user.id,
            user_name: muted_user.full_name,
            date_muted: user.date_muted,
            date_muted_str: user.date_muted_str,
            can_unmute: !muted_user.is_inaccessible_user,
        };
    });
    const $muted_users_table = $("#muted_users_table");
    const $search_input = $<HTMLInputElement>("input#muted_users_search");

    ListWidget.create<MutedUserItem>($muted_users_table, all_muted_users, {
        name: "muted-users-list",
        get_item: ListWidget.default_get_item,
        modifier_html(muted_user) {
            return render_muted_user_ui_row({muted_user});
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.user_name.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                scroll_util.reset_scrollbar(
                    $muted_users_table.closest(".progressive-table-wrapper"),
                );
            },
        },
        sort_fields: {
            ...ListWidget.generic_sort_functions("alphabetic", ["user_name"]),
            ...ListWidget.generic_sort_functions("numeric", ["date_muted"]),
        },
        $parent_container: $("#muted-user-settings"),
        $simplebar_container: $("#muted-user-settings .progressive-table-wrapper"),
    });
}

export function set_up(): void {
    loaded = true;
    $("body").on("click", ".settings-unmute-user", function (e) {
        const $row = $(this).closest("tr");
        const user_id = Number.parseInt($row.attr("data-user-id")!, 10);

        e.stopPropagation();
        muted_users.unmute_user(user_id);
    });

    populate_list();
}

export function reset(): void {
    loaded = false;
}
