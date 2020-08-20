"use strict";

const render_typing_notifications = require("../templates/typing_notifications.hbs");

const people = require("./people");

// See docs/subsystems/typing-indicators.md for details on typing indicators.

// This code handles the inbound side of typing notifications.
// When another user is typing, we process the events here.
//
// We also handle the local event of re-narrowing.
// (For the outbound code, see typing.js.)

// How long before we assume a client has gone away
// and expire its typing status
const TYPING_STARTED_EXPIRY_PERIOD = 15000; // 15s

// Note!: There are also timing constants in typing_status.js
// that make typing indicators work.

function get_users_typing_for_narrow() {
    if (!narrow_state.narrowed_to_pms()) {
        // Narrow is neither pm-with nor is: private
        return [];
    }

    const first_term = narrow_state.operators()[0];
    if (first_term.operator === "pm-with") {
        // Get list of users typing in this conversation
        const narrow_emails_string = first_term.operand;
        // TODO: Create people.emails_strings_to_user_ids.
        const narrow_user_ids_string = people.reply_to_to_user_ids_string(narrow_emails_string);
        if (!narrow_user_ids_string) {
            return [];
        }
        const narrow_user_ids = narrow_user_ids_string
            .split(",")
            .map((user_id_string) => parseInt(user_id_string, 10));
        const group = narrow_user_ids.concat([page_params.user_id]);
        return typing_data.get_group_typists(group);
    }
    // Get all users typing (in all private conversations with current user)
    return typing_data.get_all_typists();
}

exports.render_notifications_for_narrow = function () {
    const user_ids = get_users_typing_for_narrow();
    const users_typing = user_ids.map(people.get_by_user_id);
    if (users_typing.length === 0) {
        $("#typing_notifications").hide();
    } else {
        $("#typing_notifications").html(render_typing_notifications({users: users_typing}));
        $("#typing_notifications").show();
    }
};

exports.hide_notification = function (event) {
    const recipients = event.recipients.map((user) => user.user_id);
    recipients.sort();

    typing_data.clear_inbound_timer(recipients);

    const removed = typing_data.remove_typist(recipients, event.sender.user_id);

    if (removed) {
        exports.render_notifications_for_narrow();
    }
};

exports.display_notification = function (event) {
    const recipients = event.recipients.map((user) => user.user_id);
    recipients.sort();

    const sender_id = event.sender.user_id;
    event.sender.name = people.get_by_user_id(sender_id).full_name;

    typing_data.add_typist(recipients, sender_id);

    exports.render_notifications_for_narrow();

    typing_data.kickstart_inbound_timer(recipients, TYPING_STARTED_EXPIRY_PERIOD, () => {
        exports.hide_notification(event);
    });
};
window.typing_events = exports;
