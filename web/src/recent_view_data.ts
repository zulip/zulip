import assert from "minimalistic-assert";

import type {DisplayRecipientUser, Message} from "./message_store";
import * as people from "./people";
import {get_key_from_conversation_data} from "./recent_view_util";
import * as unread from "./unread";

export type ConversationData = {
    participated: boolean;
    unread_count: number;
    latest_message_timestamp: number;
    // `last_msg_id` should not be used for fetching messages, since
    // we might not have a message in the message store by that id.
    // There are two places we still use it to fetch messages for now:
    // (1) at the end of `get_focused_row_message` which is fine because
    // we can return undefined there.
    // (2) generating `last_msg_url` in `format_conversation`, which we
    // should eventually refactor to not need to do this.
    last_msg_id: number;
} & (
    | {
          type: "private";
          to_user_ids: string;
          display_recipient: DisplayRecipientUser[];
          display_reply_to: string;
          recipient_id: number;
          pm_with_url: string;
      }
    | {
          type: "stream";
          stream_id: number;
          topic: string;
      }
);
export const conversations = new Map<string, ConversationData>();
// For stream messages, key is stream-id:topic.
// For pms, key is the user IDs to whom the message is being sent.

function message_to_conversation_unread_count(msg: Message): number {
    if (msg.type === "private") {
        return unread.num_unread_for_user_ids_string(msg.to_user_ids);
    }
    return unread.num_unread_for_topic(msg.stream_id, msg.topic);
}

export function process_message(msg: Message): boolean {
    // Important: This function must correctly handle processing a
    // given message more than once; this happens during the loading
    // process because of how recent_view_message_list_data duplicates
    // all_messages_data.

    // Return whether any conversation data is updated.
    let conversation_data_updated = false;

    // Initialize conversation data
    const key = get_key_from_conversation_data(msg);
    let conversation_data = conversations.get(key);
    if (conversation_data === undefined) {
        const participated = false;
        const last_msg_id = -1;
        const latest_message_timestamp = msg.timestamp;
        const unread_count = message_to_conversation_unread_count(msg);

        if (msg.type === "private") {
            // Display recipient contains user information for DMs.
            assert(typeof msg.display_recipient !== "string");
            conversation_data = {
                participated,
                last_msg_id,
                latest_message_timestamp,
                unread_count,
                type: "private",
                to_user_ids: msg.to_user_ids,
                display_recipient: msg.display_recipient,
                display_reply_to: msg.display_reply_to,
                recipient_id: msg.recipient_id,
                pm_with_url: msg.pm_with_url,
            };
        } else {
            conversation_data = {
                participated,
                last_msg_id,
                latest_message_timestamp,
                unread_count,
                type: "stream",
                stream_id: msg.stream_id,
                topic: msg.topic,
            };
        }
        conversations.set(key, conversation_data);
        conversation_data_updated = true;
    }
    // Update conversation data
    if (conversation_data.last_msg_id < msg.id) {
        // NOTE: This also stores locally echoed msg_id which
        // has not been successfully received from the server.
        // We store it now and reify it when response is available
        // from server.
        conversation_data.last_msg_id = msg.id;
        conversation_data_updated = true;
    }
    // TODO: Add backend support for participated topics.
    // Currently participated === recently participated
    // i.e. Only those topics are participated for which we have the user's
    // message fetched in the topic. Ideally we would want this to be attached
    // to topic info fetched from backend, which is currently not a thing.
    if (!conversation_data.participated && people.is_my_user_id(msg.sender_id)) {
        conversation_data.participated = true;
        conversation_data_updated = true;
    }
    return conversation_data_updated;
}

function get_sorted_conversations(): Map<string | undefined, ConversationData> {
    // Sort all recent conversations by last message time.
    return new Map(
        [...conversations.entries()].sort((a, b) => b[1].last_msg_id - a[1].last_msg_id),
    );
}

export function get_conversations(): Map<string | undefined, ConversationData> {
    return get_sorted_conversations();
}

export function reify_message_id_if_available(opts: {old_id: number; new_id: number}): boolean {
    // We don't need to reify the message_id of the conversation
    // if a new message arrives in the conversation from another user,
    // since it replaces the last_msg_id of the conversation which
    // we were trying to reify.
    for (const value of conversations.values()) {
        if (value.last_msg_id === opts.old_id) {
            value.last_msg_id = opts.new_id;
            return true;
        }
    }
    return false;
}
