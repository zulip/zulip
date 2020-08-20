"use strict";

const FoldDict = require("./fold_dict").FoldDict;
const people = require("./people");

const partners = new Set();

exports.set_partner = function (user_id) {
    partners.add(user_id);
};

exports.is_partner = function (user_id) {
    return partners.has(user_id);
};

class RecentPrivateMessages {
    // This data structure keeps track of the sets of users you've had
    // recent conversations with, sorted by time (implemented via
    // `message_id` sorting, since that's how we time-sort messages).
    recent_message_ids = new FoldDict(); // key is user_ids_string
    recent_private_messages = [];

    insert(user_ids, message_id) {
        if (user_ids.length === 0) {
            // The server sends [] for self-PMs.
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

    get() {
        // returns array of structs with user_ids_string and
        // message_id
        return this.recent_private_messages;
    }

    get_strings() {
        // returns array of structs with user_ids_string and
        // message_id
        return this.recent_private_messages.map((conversation) => conversation.user_ids_string);
    }

    initialize(params) {
        for (const conversation of params.recent_private_conversations) {
            this.insert(conversation.user_ids, conversation.max_message_id);
        }
    }
}

exports.recent = new RecentPrivateMessages();
