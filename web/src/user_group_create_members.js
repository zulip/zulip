import $ from "jquery";

import render_new_user_group_user from "../templates/stream_settings/new_stream_user.hbs";
import render_new_user_group_users from "../templates/user_group_settings/new_user_group_users.hbs";

import * as add_subscribers_pill from "./add_subscribers_pill";
import * as ListWidget from "./list_widget";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_users from "./settings_users";
import * as user_group_create_members_data from "./user_group_create_members_data";

let pill_widget;
let all_users_list_widget;

export function get_principals() {
    return user_group_create_members_data.get_principals();
}

function redraw_member_list() {
    all_users_list_widget.replace_list_data(user_group_create_members_data.sorted_user_ids());
}

function add_user_ids(user_ids) {
    user_group_create_members_data.add_user_ids(user_ids);
    redraw_member_list();
}

function add_all_users() {
    const user_ids = user_group_create_members_data.get_all_user_ids();
    add_user_ids(user_ids);
}

function remove_user_ids(user_ids) {
    user_group_create_members_data.remove_user_ids(user_ids);
    redraw_member_list();
}

export function clear_member_list() {
    user_group_create_members_data.initialize_with_current_user();
    redraw_member_list();
}

function build_pill_widget({$parent_container}) {
    const $pill_container = $parent_container.find(".pill-container");
    const get_potential_members = user_group_create_members_data.get_potential_members;

    pill_widget = add_subscribers_pill.create({
        $pill_container,
        get_potential_subscribers: get_potential_members,
    });
}

export function create_handlers($container) {
    $container.on("click", ".add_all_users_to_user_group", (e) => {
        e.preventDefault();
        add_all_users();
        $(".add-user-list-filter").trigger("focus");
    });

    $container.on("click", ".remove_potential_subscriber", (e) => {
        e.preventDefault();
        const $elem = $(e.target);
        const user_id = Number.parseInt($elem.attr("data-user-id"), 10);
        remove_user_ids([user_id]);
    });

    function add_users({pill_user_ids}) {
        add_user_ids(pill_user_ids);
        pill_widget.clear();
    }

    add_subscribers_pill.set_up_handlers({
        get_pill_widget: () => pill_widget,
        $parent_container: $container,
        pill_selector: ".add_subscribers_container .input",
        button_selector: ".add_subscribers_container button.add-subscriber-button",
        action: add_users,
    });
}

export function build_widgets() {
    const $add_people_container = $("#people_to_add_in_group");
    $add_people_container.html(render_new_user_group_users({}));

    const $simplebar_container = $add_people_container.find(".member_list_container");

    build_pill_widget({$parent_container: $add_people_container});

    user_group_create_members_data.initialize_with_current_user();
    const current_user_id = page_params.user_id;

    all_users_list_widget = ListWidget.create($("#create_user_group_members"), [current_user_id], {
        name: "new_user_group_add_users",
        $parent_container: $add_people_container,
        get_item: people.get_by_user_id,
        sort_fields: {
            email: settings_users.sort_email,
            id: settings_users.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        modifier_html(user) {
            const item = {
                email: user.delivery_email,
                user_id: user.user_id,
                full_name: user.full_name,
                is_current_user: user.user_id === current_user_id,
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
}
