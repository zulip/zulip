import $ from "jquery";
import assert from "minimalistic-assert";

import * as buddy_data from "./buddy_data.ts";
import * as people from "./people.ts";

export function update_indicators(): void {
    $("[data-presence-indicator-user-id]").each(function () {
        const user_id = Number.parseInt($(this).attr("data-presence-indicator-user-id") ?? "", 10);
        const is_deactivated = !people.is_active_user_for_popover(user_id || 0);
        assert(!Number.isNaN(user_id));
        const user_circle_class = buddy_data.get_user_circle_class(user_id, is_deactivated);
        const user_circle_class_with_icon = `${user_circle_class} zulip-icon-${user_circle_class}`;
        $(this)
            .removeClass(
                `
                user-circle-active zulip-icon-user-circle-active
                user-circle-idle zulip-icon-user-circle-idle
                user-circle-offline zulip-icon-user-circle-offline
                user-circle-bot zulip-icon-user-circle-bot
            `,
            )
            .addClass(user_circle_class_with_icon);
    });
}
