import $ from "jquery";

import * as typing_status from "../shared/src/typing_status";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as stream_data from "./stream_data";
import {user_settings} from "./user_settings";

// This module handles the outbound side of typing indicators.
// We detect changes in the compose box and notify the server
// when we are typing.  For the inbound side see typing_events.js.
// See docs/subsystems/typing-indicators.md for more details.

function send_typing_notification_ajax(data) {
    channel.post({
        url: "/json/typing",
        data,
        success() {},
        error(xhr) {
            if (xhr.readyState !== 0) {
                blueslip.warn("Failed to send typing event: " + xhr.responseText);
            }
        },
    });
}

function send_direct_message_typing_notification(user_ids_array, operation) {
    const data = {
        to: JSON.stringify(user_ids_array),
        op: operation,
    };
    send_typing_notification_ajax(data);
}

function send_stream_typing_notification(stream_id, topic, operation) {
    const data = {
        type: "stream",
        stream_id: JSON.stringify(stream_id),
        topic,
        op: operation,
    };
    send_typing_notification_ajax(data);
}

function send_typing_notification_based_on_message_type(to, operation) {
    if (to.message_type === "direct" && user_settings.send_private_typing_notifications) {
        send_direct_message_typing_notification(to.ids, operation);
    } else if (to.message_type === "stream" && user_settings.send_stream_typing_notifications) {
        send_stream_typing_notification(to.stream_id, to.topic, operation);
    }
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

function notify_server_start(to) {
    send_typing_notification_based_on_message_type(to, "start");
}

function notify_server_stop(to) {
    send_typing_notification_based_on_message_type(to, "stop");
}

export function get_recipient() {
    const message_type = compose_state.get_message_type();
    if (message_type === "private") {
        return {
            message_type: "direct",
            ids: get_user_ids_array(),
        };
    }
    if (message_type === "stream") {
        const stream_name = compose_state.stream_name();
        const stream_id = stream_data.get_stream_id(stream_name);
        const topic = compose_state.topic();
        return {
            message_type: "stream",
            stream_id,
            topic,
        };
    }
    return null;
}

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
            page_params.server_typing_started_wait_period_milliseconds,
            page_params.server_typing_stopped_wait_period_milliseconds,
        );
    });

    // We send a stop-typing notification immediately when compose is
    // closed/cancelled
    $(document).on("compose_canceled.zulip compose_finished.zulip", () => {
        typing_status.update(
            worker,
            null,
            page_params.server_typing_started_wait_period_milliseconds,
            page_params.server_typing_stopped_wait_period_milliseconds,
        );
    });
}
