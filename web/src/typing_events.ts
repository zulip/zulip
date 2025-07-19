import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_editing_notifications from "../templates/editing_notifications.hbs";
import render_typing_notifications from "../templates/typing_notifications.hbs";

import * as message_lists from "./message_lists.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import {current_user, realm} from "./state_data.ts";
import * as typing_data from "./typing_data.ts";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

// This code handles the inbound side of typing notifications.
// When another user is typing, we process the events here.
//
// We also handle the local event of re-narrowing.
// (For the outbound code, see typing.ts.)

// If number of users typing exceed this,
// we render "Several people are typing..."
const MAX_USERS_TO_DISPLAY_NAME = 3;

// Note!: There are also timing constants in typing_status.ts
// that make typing indicators work.

export const typing_user_schema = z.object({
    email: z.string(),
    user_id: z.number(),
});

export const typing_event_schema = z.intersection(
    z.object({
        id: z.number(),
        op: z.enum(["start", "stop"]),
        type: z.literal("typing"),
    }),
    z.discriminatedUnion("message_type", [
        z.object({
            message_type: z.literal("stream"),
            sender: typing_user_schema,
            stream_id: z.number(),
            topic: z.string(),
        }),
        z.object({
            message_type: z.literal("direct"),
            recipients: z.array(typing_user_schema),
            sender: typing_user_schema,
        }),
    ]),
);
type TypingEvent = z.output<typeof typing_event_schema>;

export const typing_edit_message_event_schema = z.object({
    message_id: z.number(),
    op: z.enum(["start", "stop"]),
    type: z.literal("typing_edit_message"),
    sender_id: z.number(),
    recipient: z.discriminatedUnion("type", [
        z.object({
            type: z.literal("channel"),
            channel_id: z.number(),
            topic: z.string(),
        }),
        z.object({
            type: z.literal("direct"),
            user_ids: z.array(z.number()),
        }),
    ]),
});

type TypingMessageEditEvent = z.output<typeof typing_edit_message_event_schema>;

function get_users_typing_for_narrow(): number[] {
    if (narrow_state.narrowed_by_topic_reply()) {
        const current_stream_id = narrow_state.stream_id(narrow_state.filter(), true);
        const current_topic = narrow_state.topic();
        if (current_stream_id === undefined) {
            // Narrowed to a channel which doesn't exist.
            return [];
        }
        assert(current_topic !== undefined);
        return typing_data.get_topic_typists(current_stream_id, current_topic);
    }

    if (!narrow_state.narrowed_to_pms()) {
        // Narrow is neither "dm:" nor "is:dm" nor topic.
        return [];
    }

    const terms = narrow_state.search_terms();
    if (terms[0] === undefined) {
        return [];
    }

    const first_term = terms[0];
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
        const group = [...narrow_user_ids, current_user.user_id];
        return typing_data.get_group_typists(group);
    }
    // Get all users typing (in all direct message conversations with current user)
    return typing_data.get_all_direct_message_typists();
}

export function render_notifications_for_narrow(): void {
    const user_ids = get_users_typing_for_narrow();
    const users_typing = user_ids
        .map((user_id) => people.get_user_by_id_assert_valid(user_id))
        .filter((person) => !person.is_inaccessible_user);
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

function apply_message_edit_notifications($row: JQuery, is_typing: boolean): void {
    const $editing_notifications = $row.find(".edit-notifications");
    if (is_typing) {
        $row.find(".message_edit_notice").addClass("hide");
        $editing_notifications.html(render_editing_notifications());
    } else {
        $row.find(".message_edit_notice").removeClass("hide");
        $editing_notifications.html("");
    }
}

export function render_message_editing_typing(message_id: number, is_typing: boolean): void {
    const $row = message_lists.current?.get_row(message_id);
    if ($row !== undefined) {
        apply_message_edit_notifications($row, is_typing);
    }
}

function get_key(event: TypingEvent): string {
    if (event.message_type === "stream") {
        return typing_data.get_topic_key(event.stream_id, event.topic);
    }
    if (event.message_type === "direct") {
        const recipients = event.recipients.map((user) => user.user_id);
        recipients.sort();
        return typing_data.get_direct_message_conversation_key(recipients);
    }
    throw new Error("Invalid typing notification type", event);
}

export function hide_notification(event: TypingEvent): void {
    const key = get_key(event);
    typing_data.clear_inbound_timer(key);

    const removed = typing_data.remove_typist(key, event.sender.user_id);

    if (removed) {
        render_notifications_for_narrow();
    }
}

export function hide_message_edit_notification(event: TypingMessageEditEvent): void {
    const message_id = event.message_id;
    const key = JSON.stringify(message_id);
    typing_data.clear_inbound_timer(key);
    const removed = typing_data.remove_edit_message_typing_id(message_id);
    if (removed) {
        render_message_editing_typing(message_id, false);
    }
}

export function display_notification(event: TypingEvent): void {
    const sender_id = event.sender.user_id;

    const key = get_key(event);
    typing_data.add_typist(key, sender_id);

    render_notifications_for_narrow();

    typing_data.kickstart_inbound_timer(
        key,
        realm.server_typing_started_expiry_period_milliseconds,
        () => {
            hide_notification(event);
        },
    );
}

export function display_message_edit_notification(event: TypingMessageEditEvent): void {
    const message_id = event.message_id;
    const key = JSON.stringify(message_id);
    typing_data.add_edit_message_typing_id(message_id);
    render_message_editing_typing(message_id, true);
    typing_data.kickstart_inbound_timer(
        key,
        realm.server_typing_started_expiry_period_milliseconds,
        () => {
            hide_message_edit_notification(event);
        },
    );
}

export function disable_typing_notification(): void {
    typing_data.clear_typing_data();
    render_notifications_for_narrow();
}
