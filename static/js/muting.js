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
        var $muted_topic_notification = $('#unmute_muted_topic_notification');

        // if topic already muted notify the user. Else notify the
        // topic and stream muted by the user.
        if (exports.is_topic_muted(stream, subject) === true) {
            if ($muted_topic_notification.css("display") === "block") {
                $muted_topic_notification.hide();
            }
            muting_ui.persist_and_rerender();
            muting_ui.mute_notification(stream, subject, "already_muted_topic_notification", 1500);
        } else {
            muting.mute_topic(stream, subject);
            muting_ui.persist_and_rerender();
            popovers.topic_ops.mute(stream, subject);
        }
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
        var $muted_topic_notification = $("#unmute_muted_topic_notification");

        // hide the mute topic notification, if it exists
        if ($muted_topic_notification.css("display") === "block") {
            $muted_topic_notification.hide();
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
