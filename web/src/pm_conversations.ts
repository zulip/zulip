import * as echo_state from "./echo_state.ts";
import {FoldDict} from "./fold_dict.ts";
import type {Message} from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import * as people from "./people.ts";
import type {StateData} from "./state_data.ts";

type PMConversation = {
    user_ids_string: string;
    max_message_id: number;
    // A lower bound on the messages remaining in this conversation: the
    // ones we know about locally (we may not have loaded older history).
    // So a positive count proves the conversation is non-empty, while zero
    // only means it may be empty, in which case we confirm with the server.
    // Mirrors the `count` field stream_topic_history keeps per topic.
    message_count: number;
};

const partners = new Set<number>();

// pm_conversations_util.update_dm_last_message_id, set indirectly to
// avoid a circular dependency.
let update_dm_last_message_id: (user_ids_string: string) => void;
export function set_update_dm_last_message_id(f: (user_ids_string: string) => void): void {
    update_dm_last_message_id = f;
}

export let set_partner = (user_id: number): void => {
    partners.add(user_id);
};

export function get_partners(): number[] {
    return [...partners];
}

export function rewire_set_partner(value: typeof set_partner): void {
    set_partner = value;
}

export function is_partner(user_id: number): boolean {
    return partners.has(user_id);
}

function filter_muted_pms(conversation: PMConversation): boolean {
    // We hide muted users from the top left corner, as well as those direct
    // message groups in which all participants are muted.
    const recipients = people.split_to_ints(conversation.user_ids_string);

    if (recipients.every((id) => muted_users.is_user_muted(id))) {
        return false;
    }

    return true;
}

function get_user_ids_string(user_ids: number[]): string {
    if (user_ids.length === 0) {
        // The server sends [] for direct messages to oneself.
        user_ids = [people.my_current_user_id()];
    }
    return user_ids.toSorted((a, b) => a - b).join(",");
}

function conversation_has_unacked_message(user_ids_string: string): boolean {
    // A locally echoed message that hasn't been acked yet (including a
    // failed send the user can still retry) is visible in the conversation,
    // so it should keep the conversation in the sidebar.
    return echo_state.get_waiting_for_ack_private_messages().some((message) => {
        const user_ids = people.pm_with_user_ids(message);
        return user_ids !== undefined && get_user_ids_string(user_ids) === user_ids_string;
    });
}

class RecentDirectMessages {
    // This data structure keeps track of the sets of users you've had
    // recent conversations with, sorted by time (implemented via
    // `message_id` sorting, since that's how we time-sort messages).
    recent_message_ids = new FoldDict<PMConversation>(); // key is user_ids_string
    recent_private_messages: PMConversation[] = [];

    insert(user_ids: number[], message_id: number): void {
        const user_ids_string = get_user_ids_string(user_ids);
        let conversation = this.recent_message_ids.get(user_ids_string);

        if (conversation === undefined) {
            // This is a new user, so create a new object.
            conversation = {
                user_ids_string,
                max_message_id: message_id,
                message_count: 0,
            };
            this.recent_message_ids.set(user_ids_string, conversation);

            // Optimistically insert the new message at the front, since that
            // is usually where it belongs, but we'll re-sort.
            this.recent_private_messages.unshift(conversation);
        } else {
            if (conversation.max_message_id >= message_id) {
                // don't backdate our conversation.  This is the
                // common code path after initialization when
                // processing old messages, since we'll already have
                // the latest message_id for the conversation from
                // initialization.
                return;
            }

            // update our latest message_id
            conversation.max_message_id = message_id;
        }

        this.recent_private_messages.sort((a, b) => b.max_message_id - a.max_message_id);
    }

    increment_message_count(user_ids: number[]): void {
        const conversation = this.recent_message_ids.get(get_user_ids_string(user_ids));
        if (conversation === undefined) {
            return;
        }
        conversation.message_count += 1;
    }

    remove(user_ids_string: string): void {
        this.recent_message_ids.delete(user_ids_string);
        this.recent_private_messages = this.recent_private_messages.filter(
            (conversation) => conversation.user_ids_string !== user_ids_string,
        );
    }

    maybe_remove(user_ids: number[], num_messages: number): void {
        // If we still have locally-known messages left, the conversation is
        // definitely not empty and we just decrement.  Otherwise it may be
        // empty: optimistically remove it and ask the server to confirm,
        // re-adding it if messages actually remain (which also covers a new
        // message arriving mid-check).  Mirrors stream_topic_history.maybe_remove.
        const user_ids_string = get_user_ids_string(user_ids);
        const conversation = this.recent_message_ids.get(user_ids_string);
        if (conversation === undefined) {
            return;
        }

        if (conversation.message_count <= num_messages) {
            if (conversation_has_unacked_message(user_ids_string)) {
                // We know of no delivered messages, but an un-acked local
                // echo keeps the conversation non-empty, so leave it in the
                // sidebar.  Mirrors how stream_topic_history surfaces
                // locally-echoed topics.
                conversation.message_count = 0;
                return;
            }
            this.remove(user_ids_string);
            update_dm_last_message_id(user_ids_string);
        } else {
            conversation.message_count -= num_messages;
        }
    }

    get(): PMConversation[] {
        // returns array of structs with user_ids_string and
        // message_id
        return this.recent_private_messages.filter((pm) => filter_muted_pms(pm));
    }

    get_strings(): string[] {
        // returns array of structs with user_ids_string and
        // message_id
        return this.recent_private_messages
            .filter((pm) => filter_muted_pms(pm))
            .map((conversation) => conversation.user_ids_string);
    }

    has_conversation(user_ids_string: string): boolean {
        // Returns a boolean indicating whether we have a record proving
        // this particular direct message conversation exists.
        const recipient_ids_string = people.pm_lookup_key(user_ids_string);
        return this.recent_message_ids.get(recipient_ids_string) !== undefined;
    }

    initialize(params: StateData["pm_conversations"]): void {
        for (const conversation of params.recent_private_conversations) {
            this.insert(conversation.user_ids, conversation.max_message_id);
        }
    }
}

export let recent = new RecentDirectMessages();

export function process_message(message: Message, is_delivered_message: boolean): void {
    const user_ids = people.pm_with_user_ids(message);
    if (!user_ids) {
        return;
    }

    for (const user_id of user_ids) {
        set_partner(user_id);
    }

    recent.insert(user_ids, message.id);

    // Locally echoed messages are skipped here; a sent message is counted
    // on ack instead (echo.reify_message_id), to avoid counting it twice.
    if (is_delivered_message) {
        recent.increment_message_count(user_ids);
    }
}

export function clear_for_testing(): void {
    recent = new RecentDirectMessages();
    partners.clear();
}
