import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import {get_key_from_message} from "./recent_view_util.ts";

export type ConversationData = {
    last_msg_id: number;
    participated: boolean;
    type: "private" | "stream";
};
export const conversations = new Map<string, ConversationData>();
// For stream messages, key is stream-id:topic.
// For pms, key is the user IDs to whom the message is being sent.

export function process_message(msg: Message): boolean {
    // Important: This function must correctly handle processing a
    // given message more than once; this happens during the loading
    // process because of how recent_view_message_list_data duplicates
    // all_messages_data.

    // Return whether any conversation data is updated.
    let conversation_data_updated = false;

    // Initialize conversation data
    const key = get_key_from_message(msg);
    let conversation_data = conversations.get(key);
    if (conversation_data === undefined) {
        conversation_data = {
            last_msg_id: -1,
            participated: false,
            type: msg.type,
        };
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
