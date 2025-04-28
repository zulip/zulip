import $ from "jquery";

import render_new_user_group_user from "../templates/stream_settings/new_stream_user.hbs";
import render_new_user_group_subgroup from "../templates/user_group_settings/new_user_group_subgroup.hbs";
import render_new_user_group_users from "../templates/user_group_settings/new_user_group_users.hbs";

import * as add_group_members_pill from "./add_group_members_pill.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import {current_user} from "./state_data.ts";
import type {CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_group_create_members_data from "./user_group_create_members_data.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";

export let pill_widget: CombinedPillContainer;
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

function soft_remove_user_id(user_id: number): void {
    user_group_create_members_data.soft_remove_user_id(user_id);
    redraw_member_list();
}

function undo_soft_remove_user_id(user_id: number): void {
    user_group_create_members_data.undo_soft_remove_user_id(user_id);
    redraw_member_list();
}

function soft_remove_subgroup_id(subgroup_id: number): void {
    user_group_create_members_data.soft_remove_subgroup_id(subgroup_id);
    redraw_member_list();
}

function undo_soft_remove_subgroup_id(subgroup_id: number): void {
    user_group_create_members_data.undo_soft_remove_subgroup_id(subgroup_id);
    redraw_member_list();
}

export function clear_member_list(): void {
    user_group_create_members_data.initialize_with_current_user();
    user_group_create_members_data.reset_subgroups_data();
    redraw_member_list();
}

function sync_members(user_ids: number[], subgroup_ids: number[]): void {
    user_group_create_members_data.sync_user_ids(user_ids);
    user_group_create_members_data.sync_subgroup_ids(subgroup_ids);
    redraw_member_list();
}

function build_pill_widget({$parent_container}: {$parent_container: JQuery}): void {
    const $pill_container = $parent_container.find(".pill-container");

    pill_widget = add_group_members_pill.create({
        $pill_container,
        get_potential_members: user_group_create_members_data.get_potential_members,
        get_potential_groups: user_group_create_members_data.get_potential_subgroups,
        with_add_button: false,
        onPillCreateAction: add_members,
        // It is better to sync the current set of user and subgroup ids
        // in the input instead of removing them from the user_ids_set
        // and subgroup_id_set, otherwise we'll have to have more complex
        // logic of when to remove a user and when not to depending upon
        // their channel and individual pills.
        onPillRemoveAction: sync_members,
    });
}

export function create_handlers($container: JQuery): void {
    $container.on("click", ".remove_potential_subscriber", function (this: HTMLElement, e) {
        e.preventDefault();
        const $subscriber_row = $(this).closest(".settings-subscriber-row");
        const user_id = Number.parseInt($subscriber_row.attr("data-user-id")!, 10);
        soft_remove_user_id(user_id);
    });

    $container.on(
        "click",
        ".undo_soft_removed_potential_subscriber",
        function (this: HTMLElement, e) {
            e.preventDefault();
            const $subscriber_row = $(this).closest(".settings-subscriber-row");
            const user_id = Number.parseInt($subscriber_row.attr("data-user-id")!, 10);
            undo_soft_remove_user_id(user_id);
        },
    );

    $container.on("click", ".remove_potential_subgroup", function (this: HTMLElement, e) {
        e.preventDefault();
        const $user_group_subgroup_row = $(this).closest(".user-group-subgroup-row");
        const subgroup_id = Number.parseInt($user_group_subgroup_row.attr("data-group-id")!, 10);
        soft_remove_subgroup_id(subgroup_id);
    });

    $container.on(
        "click",
        ".undo_soft_removed_potential_subgroup",
        function (this: HTMLElement, e) {
            e.preventDefault();
            const $user_group_subgroup_row = $(this).closest(".user-group-subgroup-row");
            const subgroup_id = Number.parseInt(
                $user_group_subgroup_row.attr("data-group-id")!,
                10,
            );
            undo_soft_remove_subgroup_id(subgroup_id);
        },
    );
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
            email: user_group_components.sort_group_member_email,
            name: user_group_components.sort_group_member_name,
        },
        modifier_html(member: User | UserGroup) {
            if ("user_id" in member) {
                const item = {
                    email: member.delivery_email,
                    user_id: member.user_id,
                    full_name: member.full_name,
                    is_current_user: member.user_id === current_user_id,
                    img_src: people.small_avatar_url_for_person(member),
                    soft_removed: user_group_create_members_data.user_id_in_soft_remove_list(
                        member.user_id,
                    ),
                };
                return render_new_user_group_user(item);
            }

            const item = {
                group_id: member.id,
                display_value: user_groups.get_display_group_name(member.name),
                soft_removed: user_group_create_members_data.subgroup_id_in_soft_remove_list(
                    member.id,
                ),
            };
            return render_new_user_group_subgroup(item);
        },
        filter: {
            $element: $("#people_to_add_in_group .add-user-list-filter"),
            predicate(member, search_term) {
                return user_group_components.build_group_member_matcher(search_term)(member);
            },
        },
        $simplebar_container,
    });
    const current_person = people.get_by_user_id(current_user.user_id);
    user_pill.append_user(current_person, pill_widget);
}
