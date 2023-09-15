import $ from "jquery";

import render_user_group_info_popover from "../templates/user_group_info_popover.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import {media_breakpoints_num} from "./css_variables";
import * as message_lists from "./message_lists";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";
import {popover_items_handle_keyboard} from "./popovers";
import * as rows from "./rows";
import * as ui_util from "./ui_util";
import * as user_groups from "./user_groups";
import * as util from "./util";

let user_group_popover_instance;

export function hide() {
    if (is_open()) {
        user_group_popover_instance.destroy();
        user_group_popover_instance = undefined;
    }
}

export function is_open() {
    return Boolean(user_group_popover_instance);
}

function get_user_group_popover_items() {
    if (!is_open()) {
        blueslip.error("Trying to get menu items when user group popover is closed.");
        return undefined;
    }

    const $popover = $(user_group_popover_instance.popper);
    if (!$popover) {
        blueslip.error("Cannot find user group popover data");
        return undefined;
    }

    return $("li:not(.divider):visible a", $popover);
}

export function handle_keyboard(key) {
    const $items = get_user_group_popover_items();
    popover_items_handle_keyboard(key, $items);
}

// element is the target element to pop off of;
// message_id is the message id containing it, which should be selected;
export function toggle_user_group_info_popover(element, message_id) {
    if (is_open()) {
        hide();
        return;
    }
    const $elt = $(element);
    const user_group_id = Number.parseInt($elt.attr("data-user-group-id"), 10);
    const group = user_groups.get_user_group_from_id(user_group_id);

    let show_as_overlay = false;

    // If the window is mobile-sized, we will render the
    // user group popover centered on the screen with the overlay.
    if (window.innerWidth <= media_breakpoints_num.md) {
        show_as_overlay = true;
    }

    popover_menus.toggle_popover_menu(
        element,
        {
            placement: "right",
            arrow: false,
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
                popovers.hide_all_except_sidebars();
                if (message_id) {
                    message_lists.current.select_id(message_id);
                }
                user_group_popover_instance = instance;
                const $popover = $(instance.popper);
                $popover.addClass("user-group-popover-root");
                const args = {
                    group_name: group.name,
                    group_description: group.description,
                    members: sort_group_members(fetch_group_members([...group.members])),
                };
                instance.setContent(ui_util.parse_html(render_user_group_info_popover(args)));
            },
            onHidden() {
                hide();
            },
        },
        {show_as_overlay},
    );
}

export function register_click_handlers() {
    $("#main_div").on("click", ".user-group-mention", (e) => {
        e.stopPropagation();

        const $elt = $(e.currentTarget);
        const $row = $elt.closest(".message_row");
        const message = message_lists.current.get(rows.id($row));

        try {
            toggle_user_group_info_popover(e.currentTarget, message.id);
        } catch {
            // This user group has likely been deleted.
            blueslip.info("Unable to find user group in message" + message.sender_id);
        }
    });
}

function fetch_group_members(member_ids) {
    return member_ids
        .map((m) => people.maybe_get_user_by_id(m))
        .filter((m) => m !== undefined)
        .map((p) => ({
            ...p,
            user_circle_class: buddy_data.get_user_circle_class(p.user_id),
            is_active: people.is_active_user_for_popover(p.user_id),
            user_last_seen_time_status: buddy_data.user_last_seen_time_status(p.user_id),
        }));
}

function sort_group_members(members) {
    return members.sort((a, b) => util.strcmp(a.full_name, b.fullname));
}

// exporting these functions for testing purposes
export const _test_fetch_group_members = fetch_group_members;

export const _test_sort_group_members = sort_group_members;

export function initialize() {
    register_click_handlers();
}
