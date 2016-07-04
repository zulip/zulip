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
        muting.mute_topic(stream, subject);
        muting_ui.persist_and_rerender();

        var new_row = templates.render("topic_muted", {topic: subject, stream: stream});
        var message_area = $("#topic_muted");
        message_area.append(new_row);
        muting.setup_mute_message_ui(message_area);
        message_area.show();
    } else {
        return;
    }
};

exports.hide_topic_muted_alert = function () {
    if ($('#topic_muted').children().length === 0) {
        $('#topic_muted').hide();
    }
};

exports.setup_mute_message_ui = function (message_area) {
    var message = message_area.children('.topic_muted').last();
    message.on('click', '.topic_muted_close', function (event) {
        message.remove();
        muting.hide_topic_muted_alert();
   });
    message.on('click', '.topic_unmute_link', function (event) {
        muting.unmute_topic(message.data('stream'), message.data('topic'));
        muting_ui.persist_and_rerender();
        message.remove();
        muting.hide_topic_muted_alert();
    });
    message.delay(5000).fadeOut(200, function () {
        $(this).remove();
        muting.hide_topic_muted_alert();
    });
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
