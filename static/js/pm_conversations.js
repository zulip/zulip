const Dict = require('./dict').Dict;

const partners = new Dict();

exports.set_partner = function (user_id) {
    partners.set(user_id, true);
};

exports.is_partner = function (user_id) {
    return partners.get(user_id) || false;
};

exports.recent = (function () {
    // This data structure keeps track of the sets of users you've had
    // recent conversations with, sorted by time (implemented via
    // `message_id` sorting, since that's how we time-sort messages).
    const self = {};
    const recent_message_ids = new Dict({fold_case: true}); // key is user_ids_string
    const recent_private_messages = [];

    self.insert = function (user_ids_string, message_id) {
        if (user_ids_string === '') {
            // The API uses '' for self-PMs; convert it to the string
            // containing the current user's ID, which is the format
            // the webapp expects.
            user_ids_string = people.my_current_user_id().toString();
        }
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
        return _.pluck(recent_private_messages, 'user_ids_string');
    };

    self.initialize = function () {
        _.each(page_params.recent_private_conversations, function (conversation) {
            const user_ids_string = conversation.user_ids.join(",");
            self.insert(user_ids_string, conversation.max_message_id);
        });
        delete page_params.recent_private_messages;
    };

    return self;
}());

window.pm_conversations = exports;
