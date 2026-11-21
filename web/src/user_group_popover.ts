import {$} from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_user_group_info_popover from "../templates/popovers/user_group_info_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as hash_util from "./hash_util.ts";
import * as message_lists from "./message_lists.ts";
import * as mouse_drag from "./mouse_drag.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import {current_user} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import * as user_groups from "./user_groups.ts";
import * as util from "./util.ts";

// How many members to name before summarizing the rest as "and N more".
const MAX_NAMES_IN_POPOVER = 2;
let user_group_popover_instance: tippy.Instance | undefined;

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
                // Only members the current user can see, so the names and
                // count match the members list.
                const member_ids = [...user_groups.get_recursive_group_members(group)];
                const accessible_members = sort_group_members(fetch_group_members(member_ids));
                const displayed_member_names = accessible_members
                    .slice(0, MAX_NAMES_IN_POPOVER)
                    .map((member) => member.full_name);
                const num_other_members = accessible_members.length - displayed_member_names.length;
                const args = {
                    group_name: user_groups.get_display_group_name(group.name),
                    group_description: group.description,
                    group_edit_url: hash_util.group_edit_url(group, "general"),
                    group_members_url: hash_util.group_edit_url(group, "members"),
                    // Guests and spectators have no settings or members page to open.
                    can_open_settings: !current_user.is_guest && !page_params.is_spectator,
                    deactivated: group.deactivated,
                    displayed_member_names,
                    num_other_members,
                    has_members: accessible_members.length > 0,
                    has_other_members: num_other_members > 0,
                    // Members exist but none are visible to this user; hide the
                    // section rather than claiming the group is empty.
                    show_member_section: accessible_members.length > 0 || member_ids.length === 0,
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
        if (mouse_drag.is_drag(e)) {
            return;
        }

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
        if (mouse_drag.is_drag(e)) {
            return;
        }
        toggle_user_group_info_popover(this, undefined);
    });

    $("body").on("click", ".view_user_group", function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();
        toggle_user_group_info_popover(this, undefined);
    });
}

function fetch_group_members(member_ids: number[]): User[] {
    return (
        member_ids
            .map((m: number) => people.maybe_get_user_by_id(m, true))
            .filter((m: User | undefined): m is User => m !== undefined)
            // Only include users that the current user is allowed to see.
            .filter(
                (m: User) =>
                    people.is_active_user_or_system_bot(m.user_id) && !m.is_inaccessible_user,
            )
    );
}

function sort_group_members(members: User[]): User[] {
    return members.toSorted((a: User, b: User) => util.strcmp(a.full_name, b.full_name));
}

// exporting these functions for testing purposes
export const _test_fetch_group_members = fetch_group_members;

export const _test_sort_group_members = sort_group_members;

export function initialize(): void {
    register_click_handlers();
}
