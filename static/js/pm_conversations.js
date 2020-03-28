const FoldDict = require('./fold_dict').FoldDict;

const partners = new Set();

exports.set_partner = function (user_id) {
    partners.add(user_id);
};

exports.is_partner = function (user_id) {
    return partners.has(user_id);
};

exports.recent = (function () {
    // This data structure keeps track of the sets of users you've had
    // recent conversations with, sorted by time (implemented via
    // `message_id` sorting, since that's how we time-sort messages).
    const self = {};
    const recent_message_ids = new FoldDict(); // key is user_ids_string
    const recent_private_messages = [];

    self.insert = function (user_ids, message_id) {
        if (user_ids.length === 0) {
            // The server sends [] for self-PMs.
            user_ids = [people.my_current_user_id()];
        }
        user_ids.sort((a, b) => a - b);

        const user_ids_string = user_ids.join(',');
        let conversation = recent_message_ids.get(user_ids_string);

        if (conversation === undefined) {
            // This is a new user, so create a new object.
            conversation = {
                user_ids_string: user_ids_string,
                max_message_id: message_id,
            };
            recent_message_ids.set(user_ids_string, conversation);

            // Optimistically insert the new message at the front, since that
            // is usually where it belongs, but we'll re-sort.
            recent_private_messages.unshift(conversation);
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

        recent_private_messages.sort(function (a, b) {
            return b.max_message_id - a.max_message_id;
        });
    };

    self.get = function () {
        // returns array of structs with user_ids_string and
        // message_id
        return recent_private_messages;
    };

    self.get_strings = function () {
        // returns array of structs with user_ids_string and
        // message_id
        return recent_private_messages.map(conversation => conversation.user_ids_string);
    };

    self.initialize = function (params) {
        for (const conversation of params.recent_private_conversations) {
            self.insert(conversation.user_ids, conversation.max_message_id);
        }
    };

    return self;
}());

window.pm_conversations = exports;
