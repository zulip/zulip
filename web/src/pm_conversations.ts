import {FoldDict} from "./fold_dict.ts";
import type {Message} from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import * as people from "./people.ts";
import type {StateData} from "./state_data.ts";

type PMConversation = {
    user_ids_string: string;
    max_message_id: number;
    count: number;
};

const partners = new Set<number>();

export let set_partner = (user_id: number): void => {
    partners.add(user_id);
};

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

class RecentDirectMessages {
    // This data structure keeps track of the sets of users you've had
    // recent conversations with, sorted by time (implemented via
    // `message_id` sorting, since that's how we time-sort messages).
    recent_message_ids = new FoldDict<PMConversation>(); // key is user_ids_string
    recent_private_messages: PMConversation[] = [];

    insert(user_ids: number[], message_id: number): void {
        if (user_ids.length === 0) {
            // The server sends [] for direct messages to oneself.
            user_ids = [people.my_current_user_id()];
        }
        user_ids.sort((a, b) => a - b);

        const user_ids_string = user_ids.join(",");
        let conversation = this.recent_message_ids.get(user_ids_string);

        if (conversation === undefined) {
            // This is a new user, so create a new object.
            conversation = {
                user_ids_string,
                max_message_id: message_id,
                count: 1,
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
            conversation.count += 1;
        }

        this.recent_private_messages.sort((a, b) => b.max_message_id - a.max_message_id);
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
            let user_ids = conversation.user_ids;
            if (user_ids.length === 0) {
                user_ids = [people.my_current_user_id()];
            }
            user_ids.sort((a, b) => a - b);
            const user_ids_string = user_ids.join(",");

            // Initialize with count: 0,
            // The count will be built up as messages are processed during
            // message_fetch.initialize(), which happens after this initialization.
            const pm_conversation = {
                user_ids_string,
                max_message_id: conversation.max_message_id,
                count: 0,
            };

            this.recent_message_ids.set(user_ids_string, pm_conversation);
            this.recent_private_messages.push(pm_conversation);
        }

        this.recent_private_messages.sort((a, b) => b.max_message_id - a.max_message_id);
    }

    maybe_remove(user_ids_string: string, num_messages: number): void {
        // Remove a PM conversation if it's now empty after deleting messages.
        const conversation = this.recent_message_ids.get(user_ids_string);
        if (!conversation) {
            // We don't have this conversation tracked, nothing to do.
            return;
        }

        // If count drops to zero or below, remove the conversation
        if (conversation.count <= num_messages) {
            this.recent_message_ids.delete(user_ids_string);
            this.recent_private_messages = this.recent_private_messages.filter(
                (pm) => pm.user_ids_string !== user_ids_string,
            );
            return;
        }
        conversation.count -= num_messages;
    }
}

export let recent = new RecentDirectMessages();

export function process_message(message: Message): void {
    const user_ids = people.pm_with_user_ids(message);
    if (!user_ids) {
        return;
    }

    for (const user_id of user_ids) {
        set_partner(user_id);
    }

    recent.insert(user_ids, message.id);
}

export function clear_for_testing(): void {
    recent = new RecentDirectMessages();
    partners.clear();
}
