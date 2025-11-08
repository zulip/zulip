import $ from "jquery";
import assert from "minimalistic-assert";

import * as typing_status from "../shared/src/typing_status.ts";
import type {EditingStatusWorker, Recipient} from "../shared/src/typing_status.ts";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as message_store from "./message_store.ts";
import * as people from "./people.ts";
import * as rows from "./rows.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import {user_settings} from "./user_settings.ts";

let edit_box_worker: EditingStatusWorker;

type TypingAPIRequest = {op: "start" | "stop"} & (
    | {
          type: string;
          to: string;
      }
    | {
          type: string;
          stream_id: string;
          topic: string;
      }
);

// This module handles the outbound side of typing indicators.
// We detect changes in the compose box and notify the server
// when we are typing.  For the inbound side see typing_events.ts.
// See docs/subsystems/typing-indicators.md for more details.

function send_typing_notification_ajax(data: TypingAPIRequest): void {
    void channel.post({
        url: "/json/typing",
        data,
        error(xhr) {
            if (xhr.readyState !== 0) {
                blueslip.warn("Failed to send typing event: " + xhr.responseText);
            }
        },
    });
}

function send_message_edit_typing_notification_ajax(
    message_id: number,
    operation: "start" | "stop",
): void {
    const data = {
        op: operation,
    };
    void channel.post({
        url: `/json/messages/${message_id}/typing`,
        data,
        error(xhr) {
            if (xhr.readyState !== 0) {
                blueslip.warn("Failed to send message edit typing event: " + xhr.responseText);
            }
        },
    });
}

function send_direct_message_typing_notification(
    user_ids_array: number[],
    operation: "start" | "stop",
): void {
    const data = {
        to: JSON.stringify(user_ids_array),
        type: "direct",
        op: operation,
    };
    send_typing_notification_ajax(data);
}

function send_stream_typing_notification(
    stream_id: number,
    topic: string,
    operation: "start" | "stop",
): void {
    const stream = stream_data.get_sub_by_id(stream_id)!;
    if (!stream_data.can_post_messages_in_stream(stream)) {
        return;
    }
    const data = {
        type: "stream",
        stream_id: JSON.stringify(stream_id),
        topic,
        op: operation,
    };
    send_typing_notification_ajax(data);
}

function send_typing_notification_based_on_message_type(
    to: Recipient,
    operation: "start" | "stop",
): void {
    assert(to.notification_event_type === "typing");
    if (to.message_type === "direct" && user_settings.send_private_typing_notifications) {
        send_direct_message_typing_notification(to.ids, operation);
    } else if (to.message_type === "stream" && user_settings.send_stream_typing_notifications) {
        send_stream_typing_notification(to.stream_id, to.topic, operation);
    }
}

function message_edit_typing_notifications_enabled(message_id: number): boolean {
    const message = message_store.get(message_id);
    assert(message !== undefined);
    if (message.type === "stream") {
        return user_settings.send_stream_typing_notifications;
    }
    return user_settings.send_private_typing_notifications;
}

function send_typing_notifications_for_message_edit(
    message_id: number,
    operation: "start" | "stop",
): void {
    if (message_edit_typing_notifications_enabled(message_id)) {
        send_message_edit_typing_notification_ajax(message_id, operation);
    }
}

function get_user_ids_array(): number[] | null {
    const user_ids_string = compose_pm_pill.get_user_ids_string();
    if (user_ids_string === "") {
        return null;
    }

    return people.user_ids_string_to_ids_array(user_ids_string);
}

function is_valid_conversation(): boolean {
    const compose_empty = !compose_state.has_message_content();
    if (compose_empty) {
        return false;
    }

    return true;
}

function get_current_time(): number {
    return Date.now();
}

function notify_server_start(to: Recipient): void {
    send_typing_notification_based_on_message_type(to, "start");
}

function notify_server_stop(to: Recipient): void {
    send_typing_notification_based_on_message_type(to, "stop");
}

function notify_server_editing_start(to: Recipient): void {
    assert(to.notification_event_type === "typing_message_edit");
    send_typing_notifications_for_message_edit(to.message_id, "start");
}

function notify_server_editing_stop(to: Recipient): void {
    assert(to.notification_event_type === "typing_message_edit");
    send_typing_notifications_for_message_edit(to.message_id, "stop");
}

export function get_recipient(): Recipient | null {
    const message_type = compose_state.get_message_type();
    if (message_type === "private") {
        const user_ids = get_user_ids_array();
        // compose box with no valid user pills.
        if (user_ids === null) {
            return null;
        }
        return {
            message_type: "direct",
            notification_event_type: "typing",
            ids: user_ids,
        };
    }
    if (message_type === "stream") {
        const stream_name = compose_state.stream_name();
        const stream_id = stream_data.get_stream_id(stream_name);
        if (stream_id === undefined) {
            // compose box with no stream selected.
            return null;
        }
        const topic = compose_state.topic();
        if (!stream_data.can_use_empty_topic(stream_id) && topic === "") {
            // compose box with empty topic string.
            return null;
        }
        return {
            message_type: "stream",
            notification_event_type: "typing",
            stream_id,
            topic,
        };
    }
    return null;
}

function get_message_edit_recipient(message_id: number): Recipient {
    return {
        notification_event_type: "typing_message_edit",
        message_id,
    };
}
export function stop_message_edit_notifications(message_id: number): void {
    const recipient = get_message_edit_recipient(message_id);
    typing_status.update_editing_status(
        edit_box_worker,
        recipient,
        "stop",
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );
}

export function initialize(): void {
    const worker = {
        get_current_time,
        notify_server_start,
        notify_server_stop,
    };

    edit_box_worker = {
        get_current_time,
        notify_server_editing_start,
        notify_server_editing_stop,
    };

    $(document).on("input", "#compose-textarea", () => {
        // If our previous state was no typing notification, send a
        // start-typing notice immediately.
        const new_recipient = is_valid_conversation() ? get_recipient() : null;
        typing_status.update(
            worker,
            new_recipient,
            realm.server_typing_started_wait_period_milliseconds,
            realm.server_typing_stopped_wait_period_milliseconds,
        );
    });

    $("body").on("input", ".message_edit_content", function (this: HTMLElement) {
        const $message_row = $(this).closest(".message_row");
        const message_id = rows.id($message_row);
        const new_recipient = get_message_edit_recipient(message_id);
        typing_status.update_editing_status(
            edit_box_worker,
            new_recipient,
            "start",
            realm.server_typing_started_wait_period_milliseconds,
            realm.server_typing_stopped_wait_period_milliseconds,
        );
    });

    // We send a stop-typing notification immediately when compose is
    // closed/cancelled
    $(document).on("compose_canceled.zulip compose_finished.zulip", () => {
        typing_status.update(
            worker,
            null,
            realm.server_typing_started_wait_period_milliseconds,
            realm.server_typing_stopped_wait_period_milliseconds,
        );
    });
}
