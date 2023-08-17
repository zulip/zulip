import $ from "jquery";

import * as typing_status from "../shared/src/typing_status";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import {page_params} from "./page_params";
import * as people from "./people";
import {user_settings} from "./user_settings";

// This module handles the outbound side of typing indicators.
// We detect changes in the compose box and notify the server
// when we are typing.  For the inbound side see typing_events.js.
// See docs/subsystems/typing-indicators.md for more details.

// How frequently 'start' notifications are sent to extend
// the expiry of active typing indicators.
const typing_started_wait_period = page_params.server_typing_started_wait_period_milliseconds;
// How long after someone stops editing in the compose box
// do we send a 'stop' notification.
const typing_stopped_wait_period = page_params.server_typing_stopped_wait_period_milliseconds;

function send_typing_notification_ajax(user_ids_array, operation) {
    channel.post({
        url: "/json/typing",
        data: {
            to: JSON.stringify(user_ids_array),
            op: operation,
        },
        success() {},
        error(xhr) {
            if (xhr.readyState !== 0) {
                blueslip.warn("Failed to send typing event: " + xhr.responseText);
            }
        },
    });
}

function get_user_ids_array() {
    const user_ids_string = compose_pm_pill.get_user_ids_string();
    if (user_ids_string === "") {
        return null;
    }

    return people.user_ids_string_to_ids_array(user_ids_string);
}

function is_valid_conversation() {
    const compose_empty = !compose_state.has_message_content();
    if (compose_empty) {
        return false;
    }

    return true;
}

function get_current_time() {
    return Date.now();
}

function notify_server_start(user_ids_array) {
    if (user_settings.send_private_typing_notifications) {
        send_typing_notification_ajax(user_ids_array, "start");
    }
}

function notify_server_stop(user_ids_array) {
    if (user_settings.send_private_typing_notifications) {
        send_typing_notification_ajax(user_ids_array, "stop");
    }
}

export const get_recipient = get_user_ids_array;

export function initialize() {
    const worker = {
        get_current_time,
        notify_server_start,
        notify_server_stop,
    };

    $(document).on("input", "#compose-textarea", () => {
        // If our previous state was no typing notification, send a
        // start-typing notice immediately.
        const new_recipient = is_valid_conversation() ? get_recipient() : null;
        typing_status.update(
            worker,
            new_recipient,
            typing_started_wait_period,
            typing_stopped_wait_period,
        );
    });

    // We send a stop-typing notification immediately when compose is
    // closed/cancelled
    $(document).on("compose_canceled.zulip compose_finished.zulip", () => {
        typing_status.update(worker, null, typing_started_wait_period, typing_stopped_wait_period);
    });
}
