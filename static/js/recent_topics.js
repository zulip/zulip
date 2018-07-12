var recent_topics = (function () {

// Keeps track of conversations that the user has participated in
// and might want to keep track of future replies in.
// Usage: recent_topics.get_relevant() to get unread conversations
// as a Dict().

var exports = {};

var topics = new Dict(); // Key is stream-id:subject.

exports.process_all_messages = function () {
    exports.process_messages(message_list.all.all_messages());
};

exports.process_messages = function (messages) {
    messages.forEach(exports.process_message);
};

var reduce_message = function (msg) {
    return {
        id: msg.id,
        timestamp: msg.timestamp,
        stream_id: msg.stream_id,
        subject: msg.subject,
        sender_id: msg.sender_id,
        unread: msg.unread,
        type: msg.type,
    };
};

exports.process_message = function (msg) {
    var is_ours = people.is_my_user_id(msg.sender_id);
    var is_relevant = is_ours && msg.type === 'stream';
    var key = msg.stream_id + ':' + msg.subject;
    var topic = topics.get(key);
    if (topic === undefined && !is_relevant) {
        return false;
    }
    if (!topic) {
        topics.set(key, {
            our_last_msg: reduce_message(msg),
            last_msg: reduce_message(msg),
            read: true,
        });
        return true;
    }
    // Update last messages sent to topic.
    if (is_ours && topic.our_last_msg.timestamp <= msg.timestamp) {
        topic.our_last_msg = reduce_message(msg);
    }
    if (topic.last_msg.timestamp <= msg.timestamp) {
        topic.last_msg = reduce_message(msg);
        if (msg.unread) {
            topic.read = false;
        } else {
            topic.read = true;
        }
    }
    topics.set(key, topic);
    return true;
};

var get_sorted_topics = function () {
    // Sort all recent topics by last message time.
    topics.values().sort(function (a,b) {
        if (a.last_msg.timestamp > b.last_msg.timestamp) {
            return 1;
        }
        if (a.last_msg.timestamp < b.last_msg.timestamp) {
            return -1;
        }
        return 0;
    });
    return topics;
};

var map_topics = function (topics) {
    var mapped_topics = new Dict();
    topics.each(function (elem, key) {
        mapped_topics.set(key, {
            read: elem.read,
            our_last_msg_id: elem.our_last_msg.id,
            last_msg_id: elem.last_msg.id,
        });
    });
    return mapped_topics;
};

exports.get = function () {
    return map_topics(get_sorted_topics());
};

exports.get_relevant = function () {
    // Return only those topics where someone else has replied.
    var all_topics = get_sorted_topics();
    var updated_topics = new Dict();
    all_topics.each(function (elem, key) {
        if (elem.last_msg !== elem.our_last_msg && !elem.read) {
            updated_topics.set(key,elem);
        }
    });
    return map_topics(updated_topics);
};

exports._topics = topics;
exports._print = function (all) {
    var data;
    if (all) {
        data = exports.get();
    } else {
        data = exports.get_relevant();
    }
    data.each(function (elem, key) {
        var sub = stream_data.get_sub_by_id(key.split(':')[0]);
        var narrow = sub.name + " > " + key.split(':',2)[1];
        var msg = message_store.get(elem.last_msg_id);
        blueslip.log(narrow, {
            key: key,
            read: elem.read,
            sender: msg.sender_email,
            content: msg.content.substring(0,15),
        });
    });
};

exports.is_message_recent = function is_message_recent(msg) {
    // return boolean for whether we have a message indexed or not.
    var key = msg.stream_id + ':' + msg.subject;
    return exports.get().has(key);
}

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = recent_topics;
}
window.recent_topics = recent_topics;
