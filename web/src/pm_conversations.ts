import assert from "minimalistic-assert";

import {FoldDict} from "./fold_dict";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import * as muted_users from "./muted_users";
import * as people from "./people";
import type {StateData} from "./state_data";

type PMConversation = {
    user_ids_string: string;
    max_message_id: number;
};

const partners = new Set<number>();

export function set_partner(user_id: number): void {
    partners.add(user_id);
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

    has_conversation(user_ids_string: string): boolean | undefined {
        const recipient_ids_string = people.pm_lookup_key(user_ids_string);
        // Check if there are any previous messages in the conversation.
        // If there are, then return `true`.
        if (this.recent_message_ids.get(recipient_ids_string) !== undefined) {
            return true;
        }

        // If not, then check if the current filter matches the DM view we
        // are composing to.
        const emails_string = message_lists.current?.data.filter.operands("dm")[0];
        if (emails_string) {
            const current_user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
            assert(current_user_ids_string !== undefined);
            // If it matches the DM view, return `false` as there are no previous messages
            // in the conversation.
            if (recipient_ids_string === people.pm_lookup_key(current_user_ids_string)) {
                return false;
            }
        }
        // If none of the above conditions are satisfied, there may or may not be
        // messages in the conversation since we have not narrowed to the view and
        // there can be messages which are not fetched yet.
        return undefined;
    }

    initialize(params: StateData["pm_conversations"]): void {
        for (const conversation of params.recent_private_conversations) {
            this.insert(conversation.user_ids, conversation.max_message_id);
        }
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
