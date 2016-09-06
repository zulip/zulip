var muting = (function () {

var exports = {};

var muted_topics = new Dict({fold_case: true});

exports.mute_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (!sub_dict) {
        sub_dict = new Dict({fold_case: true});
        muted_topics.set(stream, sub_dict);
    }
    sub_dict.set(topic, true);
    unread.update_unread_counts();
};

exports.unmute_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (sub_dict) {
        sub_dict.del(topic);
    }
    unread.update_unread_counts();
};

exports.is_topic_muted = function (stream, topic) {
    if (stream === undefined) {
        return false;
    }
    var sub_dict = muted_topics.get(stream);
    return sub_dict && sub_dict.get(topic);
};

exports.get_muted_topics = function () {
    var topics = [];
    muted_topics.each(function (sub_dict, stream) {
        _.each(sub_dict.keys(), function (topic) {
            topics.push([stream, topic]);
        });
    });
    return topics;
};

exports.set_muted_topics = function (tuples) {
    muted_topics = new Dict({fold_case: true});

    _.each(tuples, function (tuple) {
        var stream = tuple[0];
        var topic = tuple[1];

        exports.mute_topic(stream, topic);
    });
};

exports.find_mute_message = function (stream, topic) {
    var found = $('#topic_muted .topic_muted').filter(function () {
        var elt = $(this);
        return elt.data('stream') === stream && elt.data('topic') === topic;
    });
    if (found.length === 0) {
        return null;
    } else {
        return found;
    }
};

exports.mute_message_topic = function () {
    var message;
    message = current_msg_list.selected_message();

    if (message === undefined) {
        return;
    }
    unread.mark_message_as_read(message);
    if (message.type === "stream") {
        var stream = message.stream;
        var subject = message.subject;
        muting.mute_topic(stream, subject);
        muting_ui.persist_and_rerender();
    } else {
        return;
    }
};

exports.unmute_message_topic = function () {
    var message;
    message = current_msg_list.selected_message();
    if (message === undefined) {
        return;
    }
    unread.mark_message_as_read(message);
    if (message.type === "stream") {
        var stream = message.stream;
        var subject = message.subject;
        var mute_message = muting.find_mute_message(stream, subject);
        if (mute_message !== null) {
            // dismiss the message:
            mute_message.remove();
            muting.hide_topic_muted_alert();
        }
        muting.unmute_topic(stream, subject);
        muting_ui.persist_and_rerender();
    } else {
        return;
    }
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting;
}
