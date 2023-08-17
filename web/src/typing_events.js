import $ from "jquery";

import render_typing_notifications from "../templates/typing_notifications.hbs";

import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as typing_data from "./typing_data";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

// This code handles the inbound side of typing notifications.
// When another user is typing, we process the events here.
//
// We also handle the local event of re-narrowing.
// (For the outbound code, see typing.js.)
//
// How long before we assume a client has gone away
// and expire the active typing indicator.
const typing_started_expiry_period = page_params.server_typing_started_expiry_period_milliseconds;

// If number of users typing exceed this,
// we render "Several people are typing..."
const MAX_USERS_TO_DISPLAY_NAME = 3;

// Note!: There are also timing constants in typing_status.js
// that make typing indicators work.

function get_users_typing_for_narrow() {
    if (!narrow_state.narrowed_to_pms()) {
        // Narrow is neither "dm:" nor "is:dm".
        return [];
    }

    const first_term = narrow_state.operators()[0];
    if (first_term.operator === "dm") {
        // Get list of users typing in this conversation
        const narrow_emails_string = first_term.operand;
        // TODO: Create people.emails_strings_to_user_ids.
        const narrow_user_ids_string = people.reply_to_to_user_ids_string(narrow_emails_string);
        if (!narrow_user_ids_string) {
            return [];
        }
        const narrow_user_ids = narrow_user_ids_string
            .split(",")
            .map((user_id_string) => Number.parseInt(user_id_string, 10));
        const group = [...narrow_user_ids, page_params.user_id];
        return typing_data.get_group_typists(group);
    }
    // Get all users typing (in all private conversations with current user)
    return typing_data.get_all_typists();
}

export function render_notifications_for_narrow() {
    const user_ids = get_users_typing_for_narrow();
    const users_typing = user_ids.map((user_id) => people.get_by_user_id(user_id));
    const num_of_users_typing = users_typing.length;

    if (num_of_users_typing === 0) {
        $("#typing_notifications").hide();
    } else {
        $("#typing_notifications").html(
            render_typing_notifications({
                users: users_typing,
                several_users: num_of_users_typing > MAX_USERS_TO_DISPLAY_NAME,
            }),
        );
        $("#typing_notifications").show();
    }
}

export function hide_notification(event) {
    const recipients = event.recipients.map((user) => user.user_id);
    recipients.sort();

    typing_data.clear_inbound_timer(recipients);

    const removed = typing_data.remove_typist(recipients, event.sender.user_id);

    if (removed) {
        render_notifications_for_narrow();
    }
}

export function display_notification(event) {
    const recipients = event.recipients.map((user) => user.user_id);
    recipients.sort();

    const sender_id = event.sender.user_id;
    event.sender.name = people.get_by_user_id(sender_id).full_name;

    typing_data.add_typist(recipients, sender_id);

    render_notifications_for_narrow();

    typing_data.kickstart_inbound_timer(recipients, typing_started_expiry_period, () => {
        hide_notification(event);
    });
}
