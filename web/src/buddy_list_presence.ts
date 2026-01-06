import $ from "jquery";
import assert from "minimalistic-assert";

import * as buddy_data from "./buddy_data";
import * as people from "./people";

// Update all presence indicators on the page
export function update_indicators(): void {
    $("[data-presence-indicator-user-id]").each(function () {
        const user_id = Number.parseInt($(this).attr("data-presence-indicator-user-id") ?? "", 10);
        assert(!Number.isNaN(user_id));

        const is_deactivated = !people.is_active_user_for_popover(user_id || 0);
        const user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
        const user_circle_class_with_icon = ${user_circle_class} zulip-icon-${user_circle_class};

        $(this)
            .removeClass(
                "user-circle-active zulip-icon-user-circle-active " +
                "user-circle-idle zulip-icon-user-circle-idle " +
                "user-circle-offline zulip-icon-user-circle-offline"
            )
            .addClass(user_circle_class_with_icon);
    });
}

// Update a single user's presence indicator
export function update_user_indicator(user_id: number): void {
    const safe_user_id = user_id.toString().replace(/'/g, "\\'");
    const $el = $([data-presence-indicator-user-id='${safe_user_id}']);
    if ($el.length === 0) return;

    const is_deactivated = !people.is_active_user_for_popover(user_id);
    const user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
    const user_circle_class_with_icon = ${user_circle_class} zulip-icon-${user_circle_class};

    $el
        .removeClass(
            "user-circle-active zulip-icon-user-circle-active " +
            "user-circle-idle zulip-icon-user-circle-idle " +
            "user-circle-offline zulip-icon-user-circle-offline"
        )
        .addClass(user_circle_class_with_icon);
}

// Update multiple users' presence indicators
export function update_multiple_indicators(user_ids: number[]): void {
    for (const user_id of user_ids) {
        update_user_indicator(user_id);
    }
}

// Get the presence class of a user
export function get_presence_class(user_id: number): string {
    const is_deactivated = !people.is_active_user_for_popover(user_id);
    return buddy_data.get_user_circle_class(user_id, is_deactivated);
}
}