import assert from "minimalistic-assert";

import {all_messages_data} from "./all_messages_data.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as unread from "./unread.ts";
import * as unread_ui from "./unread_ui.ts";

type DirectMessagePermissionHints = {
    is_known_empty_conversation: boolean;
    is_local_echo_safe: boolean;
};

export function do_unread_count_updates(messages: Message[], expect_no_new_unreads = false): void {
    const any_new_unreads = unread.process_loaded_messages(messages, expect_no_new_unreads);

    if (any_new_unreads) {
        // The following operations are expensive, and thus should
        // only happen if we found any unread messages justifying it.
        unread_ui.update_unread_counts();
    }
}

export function get_count_of_messages_in_topic_sent_after_current_message(
    stream_id: number,
    topic: string,
    message_id: number,
): number {
    const all_messages = get_loaded_messages_in_topic(stream_id, topic);
    return all_messages.filter((msg) => msg.id >= message_id).length;
}

export function get_loaded_messages_in_topic(stream_id: number, topic: string): Message[] {
    return all_messages_data
        .all_messages()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
}

export function get_messages_in_dm_conversations(user_ids_strings: Set<string>): Message[] {
    return all_messages_data
        .all_messages()
        .filter((x) => x.type === "private" && user_ids_strings.has(x.to_user_ids));
}

export function get_max_message_id_in_stream(stream_id: number): number {
    let max_message_id = 0;
    for (const msg of all_messages_data.all_messages()) {
        if (msg.type === "stream" && msg.stream_id === stream_id && msg.id > max_message_id) {
            max_message_id = msg.id;
        }
    }
    return max_message_id;
}

export function get_topics_for_message_ids(message_ids: number[]): Map<string, [number, string]> {
    const topics = new Map<string, [number, string]>(); // key = stream_id:topic
    for (const msg_id of message_ids) {
        // message_store still has data on deleted messages when this runs.
        const message = message_store.get(msg_id);
        if (message === undefined) {
            // We may not have the deleted message cached locally in
            // message_store; if so, we can just skip processing it.
            continue;
        }
        if (message.type === "stream") {
            // Create unique keys for stream_id and topic.
            const topic_key = message.stream_id + ":" + message.topic;
            topics.set(topic_key, [message.stream_id, message.topic]);
        }
    }
    return topics;
}

export function get_direct_message_permission_hints(
    recipient_ids_string: string,
): DirectMessagePermissionHints {
    // Check if there are any previous messages in the DM conversation.
    const have_conversation_in_cache =
        pm_conversations.recent.has_conversation(recipient_ids_string);
    if (have_conversation_in_cache) {
        return {is_known_empty_conversation: false, is_local_echo_safe: true};
    }

    // If not, we need to check if the current filter matches the DM view we
    // are composing to.
    const dm_conversation = message_lists.current?.data?.filter.operands("dm")[0];
    if (dm_conversation) {
        const current_user_ids_string = people.emails_strings_to_user_ids_string(dm_conversation);
        assert(current_user_ids_string !== undefined);
        // If it matches and the messages for the current filter are fetched,
        // then there are certainly no messages in the conversation.
        if (
            people.pm_lookup_key(recipient_ids_string) ===
                people.pm_lookup_key(current_user_ids_string) &&
            message_lists.current?.data?.fetch_status.has_found_newest()
        ) {
            return {is_known_empty_conversation: true, is_local_echo_safe: true};
        }
    }

    // If it does not match, then there can be messages in the DM conversation
    // which are not fetched locally and hence we disable local echo for clean
    // error handling in case there are no messages in the conversation and
    // user is not allowed to initiate DM conversations.
    return {is_known_empty_conversation: false, is_local_echo_safe: false};
}

export function user_can_send_direct_message(user_ids_string: string): boolean {
    return (
        (!get_direct_message_permission_hints(user_ids_string).is_known_empty_conversation ||
            people.user_can_initiate_direct_message_thread(user_ids_string)) &&
        people.user_can_direct_message(user_ids_string)
    );
}
