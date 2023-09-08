import $ from "jquery";

import render_user_group_info_popover from "../templates/user_group_info_popover.hbs";
import render_user_group_info_popover_content from "../templates/user_group_info_popover_content.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as people from "./people";
import {hide_all, popover_items_handle_keyboard} from "./popovers";
import * as rows from "./rows";
import * as user_groups from "./user_groups";
import * as util from "./util";

let $current_user_group_popover_elem;

export function hide() {
    if (is_open()) {
        $current_user_group_popover_elem.popover("destroy");
        $current_user_group_popover_elem = undefined;
    }
}

export function is_open() {
    return $current_user_group_popover_elem !== undefined;
}

function get_user_group_popover_items() {
    if (!$current_user_group_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = $current_user_group_popover_elem.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $("li:not(.divider):visible a", popover_data.$tip);
}

export function handle_keyboard(key) {
    const $items = get_user_group_popover_items();
    popover_items_handle_keyboard(key, $items);
}

// element is the target element to pop off of;
// message_id is the message id containing it, which should be selected;
export function toggle_user_group_info_popover(element, message_id) {
    const $last_popover_elem = $current_user_group_popover_elem;
    hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    // hardcoded pixel height of the popover
    // note that the actual size varies (in group size), but this is about as big as it gets
    const popover_size = 390;
    const $elt = $(element);
    const user_group_id = Number.parseInt($elt.attr("data-user-group-id"), 10);
    const group = user_groups.get_user_group_from_id(user_group_id);

    message_lists.current.select_id(message_id);

    if ($elt.data("popover") === undefined) {
        const args = {
            group_name: group.name,
            group_description: group.description,
            members: sort_group_members(fetch_group_members([...group.members])),
        };
        $elt.popover({
            placement: calculate_info_popover_placement(popover_size, $elt),
            template: render_user_group_info_popover(),
            content: render_user_group_info_popover_content(args),
            html: true,
            trigger: "manual",
            fixed: true,
        });
        $elt.popover("show");
        $current_user_group_popover_elem = $elt;
    }
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

function calculate_info_popover_placement(size, $elt) {
    const ypos = $elt.get_offset_to_window().top;

    if (!(ypos + size / 2 < message_viewport.height() && ypos > size / 2)) {
        if (ypos + size < message_viewport.height()) {
            return "bottom";
        } else if (ypos > size) {
            return "top";
        }
    }

    return undefined;
}

// exporting these functions for testing purposes
export const _test_fetch_group_members = fetch_group_members;

export const _test_sort_group_members = sort_group_members;

export const _test_calculate_info_popover_placement = calculate_info_popover_placement;

export function initialize() {
    register_click_handlers();
}
