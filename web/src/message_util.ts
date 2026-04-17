import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";
import {recent_view_messages_data} from "./recent_view_messages_data.ts";
import {realm} from "./state_data.ts";
import * as unread from "./unread.ts";
import * as unread_ui from "./unread_ui.ts";
import * as user_groups from "./user_groups.ts";

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
    return recent_view_messages_data
        .all_messages_after_mute_filtering()
        .filter(
            (x) =>
                x.type === "stream" &&
                x.stream_id === stream_id &&
                x.topic.toLowerCase() === topic.toLowerCase(),
        );
}

export function get_messages_in_dm_conversations(user_ids_strings: Set<string>): Message[] {
    return recent_view_messages_data
        .all_messages_after_mute_filtering()
        .filter((x) => x.type === "private" && user_ids_strings.has(x.to_user_ids));
}

export function get_max_message_id_in_stream(stream_id: number): number {
    let max_message_id = 0;
    for (const msg of recent_view_messages_data.all_messages_after_mute_filtering()) {
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
    const dm_conversation =
        message_lists.current?.data?.filter.terms_with_operator("dm")[0]?.operand;
    if (dm_conversation) {
        const current_user_ids_string = String(dm_conversation);
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

// Returns a per user permission check if required for DM message to occur.
export function make_check_message_permission_for_dm_candidate(
    recipient_ids: number[],
): ((candidate_user_id: number) => boolean) | null {
    const current_user_id = people.my_current_user_id();
    const is_current_user_in_initiator_group = user_groups.is_user_in_setting_group(
        realm.realm_direct_message_initiator_group,
        current_user_id,
    );
    const is_current_user_in_permission_group = user_groups.is_user_in_setting_group(
        realm.realm_direct_message_permission_group,
        current_user_id,
    );

    // Current user is in both initiator and permission groups,
    // so they can message anyone.
    if (is_current_user_in_initiator_group && is_current_user_in_permission_group) {
        return null;
    }

    const recipient_is_in_permission_group = recipient_ids.some(
        (user_id) =>
            !people.is_valid_bot_user(user_id) &&
            user_id !== current_user_id &&
            user_groups.is_user_in_setting_group(
                realm.realm_direct_message_permission_group,
                user_id,
            ),
    );

    // Current user is in initiator group and at least one
    // human recipient is in the permission group.
    if (is_current_user_in_initiator_group && recipient_is_in_permission_group) {
        return null;
    }

    const all_recipients_are_bots = recipient_ids.every(
        (user_id) => people.is_valid_bot_user(user_id) || user_id === current_user_id,
    );

    const permission_group_user_ids = user_groups.get_user_ids_in_setting_group(
        realm.realm_direct_message_permission_group,
    );

    return (candidate_user_id: number): boolean => {
        // Include bots when all recipients are bots.
        if (all_recipients_are_bots && people.is_valid_bot_user(candidate_user_id)) {
            return true;
        }

        const is_candidate_in_permission_group = permission_group_user_ids.has(candidate_user_id);

        // Current user can initiate and the candidate is in the permission group.
        if (is_current_user_in_initiator_group && is_candidate_in_permission_group) {
            return true;
        }

        // A past conversation exists between the full group {sender, recipient_ids,
        // candidate} and at least one participant is in the permission group.
        const conversation_user_ids = [...recipient_ids, candidate_user_id];
        const conversation_user_ids_string = conversation_user_ids.join(",");
        const is_known_empty_conversation = get_direct_message_permission_hints(
            conversation_user_ids_string,
        ).is_known_empty_conversation;
        if (
            !is_known_empty_conversation &&
            (is_current_user_in_permission_group ||
                recipient_is_in_permission_group ||
                is_candidate_in_permission_group)
        ) {
            return true;
        }

        return false;
    };
}
