import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_user_group_info_popover from "../templates/popovers/user_group_info_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as buddy_data from "./buddy_data.ts";
import * as hash_util from "./hash_util.ts";
import * as message_lists from "./message_lists.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import {current_user} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_groups from "./user_groups.ts";
import * as util from "./util.ts";

const MAX_ROWS_IN_POPOVER = 30;
let user_group_popover_instance: tippy.Instance | undefined;

type PopoverGroupMember = User & {user_circle_class: string; user_last_seen_time_status: string};

export function hide(): void {
    if (user_group_popover_instance !== undefined) {
        user_group_popover_instance.destroy();
        user_group_popover_instance = undefined;
    }
}

export function is_open(): boolean {
    return Boolean(user_group_popover_instance);
}

function get_user_group_popover_items(): JQuery | undefined {
    if (user_group_popover_instance === undefined) {
        blueslip.error("Trying to get menu items when user group popover is closed.");
        return undefined;
    }

    const $popover = $(user_group_popover_instance.popper);
    if (!$popover) {
        blueslip.error("Cannot find user group popover data");
        return undefined;
    }

    return $("li:not(.divider) a", $popover);
}

export function handle_keyboard(key: string): void {
    const $items = get_user_group_popover_items();
    popover_menus.popover_items_handle_keyboard(key, $items);
}

// element is the target element to pop off of;
// the element could be user group pill or mentions in a message;
// in case of message, message_id is the message id containing it;
// in case of user group pill, message_id is not used;
export function toggle_user_group_info_popover(
    element: tippy.ReferenceElement,
    message_id: number | undefined,
): void {
    if (is_open()) {
        hide();
        return;
    }
    const $elt = $(element);
    const user_group_id_str = $elt.attr("data-user-group-id");
    assert(user_group_id_str !== undefined);

    const user_group_id = Number.parseInt(user_group_id_str, 10);
    const group = user_groups.get_user_group_from_id(user_group_id);

    popover_menus.toggle_popover_menu(
        element,
        {
            theme: "popover-menu",
            placement: "right",
            popperOptions: {
                modifiers: [
                    {
                        name: "flip",
                        options: {
                            fallbackPlacements: ["left", "top", "bottom"],
                        },
                    },
                ],
            },
            onCreate(instance) {
                if (message_id) {
                    assert(message_lists.current !== undefined);
                    message_lists.current.select_id(message_id);
                }
                user_group_popover_instance = instance;
                const subgroups = user_groups.convert_name_to_display_name_for_groups(
                    user_groups
                        .get_direct_subgroups_of_group(group)
                        .sort(user_group_components.sort_group_member_name),
                );
                const members = sort_group_members(fetch_group_members([...group.members]));
                const all_individual_members = [...user_groups.get_recursive_group_members(group)];
                const has_bots =
                    group.is_system_group &&
                    all_individual_members.some((member_id) => {
                        const member = people.get_user_by_id_assert_valid(member_id);
                        return people.is_active_user_for_popover(member.user_id) && member.is_bot;
                    });
                const displayed_subgroups = subgroups.slice(0, MAX_ROWS_IN_POPOVER);
                const displayed_members =
                    subgroups.length < MAX_ROWS_IN_POPOVER
                        ? members.slice(0, MAX_ROWS_IN_POPOVER - subgroups.length)
                        : [];
                const display_all_subgroups_and_members =
                    subgroups.length + members.length <= MAX_ROWS_IN_POPOVER;
                const args = {
                    group_name: user_groups.get_display_group_name(group.name),
                    group_description: group.description,
                    group_edit_url: hash_util.group_edit_url(group, "general"),
                    is_guest: current_user.is_guest,
                    is_system_group: group.is_system_group,
                    deactivated: group.deactivated,
                    members_count: all_individual_members.length,
                    group_members_url: hash_util.group_edit_url(group, "members"),
                    display_all_subgroups_and_members,
                    has_bots,
                    displayed_subgroups,
                    displayed_members,
                };
                instance.setContent(ui_util.parse_html(render_user_group_info_popover(args)));
            },
            onHidden() {
                hide();
            },
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: false,
        },
    );
}

export function register_click_handlers(): void {
    $("#main_div").on("click", ".user-group-mention", function (this: HTMLElement, e) {
        e.stopPropagation();

        const $elt = $(this);
        const $row = $elt.closest(".message_row");
        const message_id = rows.id($row);

        assert(message_lists.current !== undefined);
        const message = message_lists.current.get(message_id);
        assert(message !== undefined);

        try {
            toggle_user_group_info_popover(this, message.id);
        } catch {
            // This user group has likely been deleted.
            blueslip.info("Unable to find user group in message" + message.sender_id);
        }
    });

    // Show the user_group_popover when pill clicked in subscriber settings.
    $("body").on(
        "click",
        ".person_picker .pill[data-user-group-id]",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            toggle_user_group_info_popover(this, undefined);
        },
    );

    // Show the user_group_popover in user invite section.
    $("body").on(
        "click",
        "#invite-user-group-container .pill-container .pill",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            toggle_user_group_info_popover(this, undefined);
        },
    );
    // Note: Message feeds and drafts have their own direct event listeners
    // that run before this one and call stopPropagation.
    $("body").on("click", ".messagebox .user-group-mention", function (this: HTMLElement, e) {
        e.stopPropagation();
        toggle_user_group_info_popover(this, undefined);
    });

    $("body").on("click", ".view_user_group", function (this: HTMLElement, e) {
        e.stopPropagation();
        toggle_user_group_info_popover(this, undefined);
    });
}

function fetch_group_members(member_ids: number[]): PopoverGroupMember[] {
    return (
        member_ids
            .map((m: number) => people.get_user_by_id_assert_valid(m))
            // We need to include inaccessible users here separately, since
            // we do not include them in active_user_dict, but we want to
            // show them in the popover as "Unknown user".
            .filter(
                (m: User) => people.is_active_user_for_popover(m.user_id) || m.is_inaccessible_user,
            )
            .map((p: User) => ({
                ...p,
                user_circle_class: buddy_data.get_user_circle_class(p.user_id),
                user_last_seen_time_status: buddy_data.user_last_seen_time_status(p.user_id),
            }))
    );
}

function sort_group_members(members: PopoverGroupMember[]): PopoverGroupMember[] {
    return members.sort((a: PopoverGroupMember, b: PopoverGroupMember) =>
        util.strcmp(a.full_name, b.full_name),
    );
}

// exporting these functions for testing purposes
export const _test_fetch_group_members = fetch_group_members;

export const _test_sort_group_members = sort_group_members;

export function initialize(): void {
    register_click_handlers();
}
