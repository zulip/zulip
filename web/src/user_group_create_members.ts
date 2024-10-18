import $ from "jquery";

import render_new_user_group_user from "../templates/stream_settings/new_stream_user.hbs";
import render_new_user_group_subgroup from "../templates/user_group_settings/new_user_group_subgroup.hbs";
import render_new_user_group_users from "../templates/user_group_settings/new_user_group_users.hbs";

import * as add_group_members_pill from "./add_group_members_pill";
import * as add_subscribers_pill from "./add_subscribers_pill";
import * as ListWidget from "./list_widget";
import type {ListWidget as ListWidgetType} from "./list_widget";
import * as people from "./people";
import type {User} from "./people";
import {current_user} from "./state_data";
import type {CombinedPillContainer} from "./typeahead_helper";
import * as user_group_create_members_data from "./user_group_create_members_data";
import * as user_group_edit_members from "./user_group_edit_members";
import type {UserGroup} from "./user_groups";

let pill_widget: CombinedPillContainer;
let all_users_list_widget: ListWidgetType<User | UserGroup, User | UserGroup>;

export function get_principals(): number[] {
    return user_group_create_members_data.get_principals();
}

export function get_subgroups(): number[] {
    return user_group_create_members_data.get_subgroups();
}

function redraw_member_list(): void {
    all_users_list_widget.replace_list_data(user_group_create_members_data.sorted_members());
}

function add_members(user_ids: number[], subgroup_ids: number[]): void {
    user_group_create_members_data.add_user_ids(user_ids);
    user_group_create_members_data.add_subgroup_ids(subgroup_ids);
    redraw_member_list();
}

function add_all_users(): void {
    const user_ids = user_group_create_members_data.get_all_user_ids();
    add_members(user_ids, []);
}

function remove_user_ids(user_ids: number[]): void {
    user_group_create_members_data.remove_user_ids(user_ids);
    redraw_member_list();
}

function remove_subgroup_ids(subgroup_ids: number[]): void {
    user_group_create_members_data.remove_subgroup_ids(subgroup_ids);
    redraw_member_list();
}

export function clear_member_list(): void {
    user_group_create_members_data.initialize_with_current_user();
    redraw_member_list();
}

function build_pill_widget({$parent_container}: {$parent_container: JQuery}): void {
    const $pill_container = $parent_container.find(".pill-container");
    const get_potential_members = user_group_create_members_data.get_potential_members;

    pill_widget = add_subscribers_pill.create({
        $pill_container,
        get_potential_subscribers: get_potential_members,
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
        remove_user_ids([user_id]);
    });

    $container.on("click", ".remove_potential_subgroup", (e) => {
        e.preventDefault();
        const $elem = $(e.target);
        const subgroup_id = Number.parseInt($elem.attr("data-group-id")!, 10);
        remove_subgroup_ids([subgroup_id]);
    });

    function add_users({
        pill_user_ids,
        pill_group_ids,
    }: {
        pill_user_ids: number[];
        pill_group_ids: number[];
    }): void {
        add_members(pill_user_ids, pill_group_ids);
        pill_widget.clear();
    }

    add_group_members_pill.set_up_handlers({
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
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const initial_members = [people.get_by_user_id(current_user_id)] as (User | UserGroup)[];

    all_users_list_widget = ListWidget.create($("#create_user_group_members"), initial_members, {
        name: "new_user_group_add_users",
        $parent_container: $add_people_container,
        get_item: ListWidget.default_get_item,
        sort_fields: {
            email: user_group_edit_members.sort_group_member_email,
            name: user_group_edit_members.sort_group_member_name,
        },
        modifier_html(member: User | UserGroup) {
            if ("user_id" in member) {
                const item = {
                    email: member.delivery_email,
                    user_id: member.user_id,
                    full_name: member.full_name,
                    is_current_user: member.user_id === current_user_id,
                    img_src: people.small_avatar_url_for_person(member),
                };
                return render_new_user_group_user(item);
            }

            const item = {
                group_id: member.id,
                display_value: member.name,
            };
            return render_new_user_group_subgroup(item);
        },
        filter: {
            $element: $("#people_to_add_in_group .add-user-list-filter"),
            predicate(member, search_term) {
                return user_group_edit_members.build_group_member_matcher(search_term)(member);
            },
        },
        $simplebar_container,
    });
}
