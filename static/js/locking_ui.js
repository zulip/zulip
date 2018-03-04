var locking_ui = (function () {
var exports = {};

exports.rerender = function () {
    stream_list.update_streams_sidebar();
};

exports.persist_lock = function (stream_id, topic_name) {
    var data = {
        stream: stream_id,
        topic: topic_name,
        op: 'add',
    };
    channel.patch({
        url: '/json/lock_topic',
        idempotent: true,
        data: data,
    });
};

exports.persist_unlock = function (stream_id, topic_name) {
    var data = {
        stream: stream_id,
        topic: topic_name,
        op: 'remove',
    };
    channel.patch({
        url: '/json/lock_topic',
        idempotent: true,
        data: data,
    });
};

exports.lock_topic = function (stream_id, topic) {
    stream_popover.hide_topic_popover();
    locking.add_locked_topic(stream_id, topic);
    exports.persist_lock(stream_id, topic);
    exports.rerender();
};

exports.unlock_topic = function (stream_id, topic) {
    stream_popover.hide_topic_popover();
    locking.remove_locked_topic(stream_id, topic);
    exports.persist_unlock(stream_id, topic);
    exports.rerender();
};

exports.handle_updates = function (locked_topics) {
    locking.set_locked_topics(locked_topics);
    exports.rerender();
    current_msg_list.update_locked_bookend();
};
$(function () {
    exports.handle_updates(page_params.locked_topics);
});
return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = locking_ui;
}
