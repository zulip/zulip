var pm_conversations = (function () {

var exports = {};

var partners = new Dict();

exports.set_partner = function (user_id) {
    partners.set(user_id, true);
};

exports.is_partner = function (user_id) {
    return partners.get(user_id) || false;
};

exports.recent = (function () {
    var self = {};
    var recent_timestamps = new Dict({fold_case: true}); // key is user_ids_string
    var recent_private_messages = [];

    self.insert = function (user_ids_string, timestamp) {
        var conversation = recent_timestamps.get(user_ids_string);

        if (conversation === undefined) {
            // This is a new user, so create a new object.
            conversation = {
                user_ids_string: user_ids_string,
                timestamp: timestamp,
            };
            recent_timestamps.set(user_ids_string, conversation);

            // Optimistically insert the new message at the front, since that
            // is usually where it belongs, but we'll re-sort.
            recent_private_messages.unshift(conversation);
        } else {
            if (conversation.timestamp >= timestamp) {
                return; // don't backdate our conversation
            }

            // update our timestamp
            conversation.timestamp = timestamp;
        }

        recent_private_messages.sort(function (a, b) {
            return b.timestamp - a.timestamp;
        });
    };

    self.get = function () {
        // returns array of structs with user_ids_string and
        // timestamp
        return recent_private_messages;
    };

    self.get_strings = function () {
        // returns array of structs with user_ids_string and
        // timestamp
        return _.pluck(recent_private_messages, 'user_ids_string');
    };

    return self;
}());

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = pm_conversations;
}
window.pm_conversations = pm_conversations;
