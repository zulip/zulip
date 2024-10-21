import $ from "jquery";

import render_new_user_group_user from "../templates/stream_settings/new_stream_user.hbs";
import render_new_user_group_users from "../templates/user_group_settings/new_user_group_users.hbs";

import * as add_subscribers_pill from "./add_subscribers_pill";
import * as ListWidget from "./list_widget";
import type {ListWidget as ListWidgetType} from "./list_widget";
import * as people from "./people";
import {current_user} from "./state_data";
import type {CombinedPillContainer} from "./typeahead_helper";
import * as user_group_create_members_data from "./user_group_create_members_data";
import * as user_sort from "./user_sort";

let pill_widget: CombinedPillContainer;
let all_users_list_widget: ListWidgetType<number, people.User>;

export function get_principals(): number[] {
    return user_group_create_members_data.get_principals();
}

function redraw_member_list(): void {
    all_users_list_widget.replace_list_data(user_group_create_members_data.sorted_user_ids());
}

function add_user_ids(user_ids: number[]): void {
    user_group_create_members_data.add_user_ids(user_ids);
    redraw_member_list();
}

function add_all_users(): void {
    const user_ids = user_group_create_members_data.get_all_user_ids();
    add_user_ids(user_ids);
}

function soft_remove_user_id(user_id: number): void {
    user_group_create_members_data.soft_remove_user_id(user_id);
    redraw_member_list();
}

function undo_soft_remove_user_id(user_id: number): void {
    user_group_create_members_data.undo_soft_remove_user_id(user_id);
    redraw_member_list();
}

export function clear_member_list(): void {
    user_group_create_members_data.initialize_with_current_user();
    redraw_member_list();
}

function sync_user_ids(user_ids: number[]): void {
    user_group_create_members_data.sync_user_ids(user_ids);
    redraw_member_list();
}

function build_pill_widget({$parent_container}: {$parent_container: JQuery}): void {
    const $pill_container = $parent_container.find(".pill-container");
    const get_potential_members = user_group_create_members_data.get_potential_members;

    pill_widget = add_subscribers_pill.create_without_add_button({
        $pill_container,
        get_potential_subscribers: get_potential_members,
        onPillCreateAction: add_user_ids,
        // It is better to sync the current set of user ids in the input
        // instead of removing user_ids from the user_ids_set, otherwise
        // we'll have to have more complex logic of when to remove
        // a user and when not to depending upon their group, channel
        // and individual pills.
        onPillRemoveAction: sync_user_ids,
    });
}

export function create_handlers($container: JQuery): void {
    $container.on("click", ".add_all_users_to_user_group", (e) => {
        e.preventDefault();
        add_all_users();
        $(".add-user-list-filter").trigger("focus");
    });

    $container.on("click", ".remove_potential_subscriber", (e) => {
        e.preventDefault();
        const $elem = $(e.target);
        const user_id = Number.parseInt($elem.attr("data-user-id")!, 10);
        soft_remove_user_id(user_id);
    });

    $container.on("click", ".undo_soft_removed_potential_subscriber", (e) => {
        e.preventDefault();
        const $elem = $(e.target);
        const user_id = Number.parseInt($elem.attr("data-user-id")!, 10);
        undo_soft_remove_user_id(user_id);
    });

    function add_users({pill_user_ids}: {pill_user_ids: number[]}): void {
        add_user_ids(pill_user_ids);
        pill_widget.clear();
    }

    add_subscribers_pill.set_up_handlers({
        get_pill_widget: () => pill_widget,
        $parent_container: $container,
        pill_selector: ".add_members_container .input",
        button_selector: ".add_members_container button.add-member-button",
        action: add_users,
    });
}

export function build_widgets(): void {
    const $add_people_container = $("#people_to_add_in_group");
    $add_people_container.html(render_new_user_group_users({}));

    const $simplebar_container = $add_people_container.find(".member_list_container");

    build_pill_widget({$parent_container: $add_people_container});

    user_group_create_members_data.initialize_with_current_user();
    const current_user_id = current_user.user_id;

    all_users_list_widget = ListWidget.create($("#create_user_group_members"), [current_user_id], {
        name: "new_user_group_add_users",
        $parent_container: $add_people_container,
        get_item: people.get_by_user_id,
        sort_fields: {
            email: user_sort.sort_email,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        modifier_html(user) {
            const item = {
                email: user.delivery_email,
                user_id: user.user_id,
                full_name: user.full_name,
                is_current_user: user.user_id === current_user_id,
                img_src: people.small_avatar_url_for_person(user),
                soft_removed: user_group_create_members_data.user_id_in_soft_remove_list(
                    user.user_id,
                ),
            };
            return render_new_user_group_user(item);
        },
        filter: {
            $element: $("#people_to_add_in_group .add-user-list-filter"),
            predicate(user, search_term) {
                return people.build_person_matcher(search_term)(user);
            },
        },
        $simplebar_container,
        html_selector(user) {
            return $(`#${CSS.escape("user_checkbox_" + user.user_id)}`);
        },
    });
    pill_widget.appendValue(current_user.email);
}
