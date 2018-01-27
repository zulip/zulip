var locking = (function () {

var exports = {};

var locked_topics = new Dict({fold_case: true});

exports.add_locked_topic = function (stream, topic) {
    var sub_dict = locked_topics.get(stream);
    if (!sub_dict) {
        sub_dict = new Dict({fold_case: true});
        locked_topics.set(stream, sub_dict);
    }
    sub_dict.set(topic, true);
};

exports.remove_locked_topic = function (stream, topic) {
    var sub_dict = locked_topics.get(stream);
    if (sub_dict) {
        sub_dict.del(topic);
    }
};

exports.set_locked_topics = function (tuples) {
    locked_topics = new Dict({fold_case: true});

    _.each(tuples, function (tuple) {
        var stream = tuple[0];
        var topic = tuple[1];

        exports.add_locked_topic(stream, topic);
    });
};

exports.can_lock_topic = function (stream, topic) {
    if (stream === undefined || topic === undefined) {
        return false;
    }
    if (!page_params.is_admin) {
        return false;
    }
    var sub_dict = locked_topics.get(stream);
    return !sub_dict || !sub_dict.get(topic);
};

exports.can_unlock_topic = function (stream, topic) {
    if (!page_params.is_admin || stream === undefined || topic === undefined) {
        return false;
    }
    return !exports.can_lock_topic(stream, topic);
};

exports.is_topic_locked = function (stream, topic) {
    if (stream === undefined || topic === undefined) {
        return false;
    }
    var sub_dict = locked_topics.get(stream);
    return sub_dict && sub_dict.get(topic);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = locking;
}
