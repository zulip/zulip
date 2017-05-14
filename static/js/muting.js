var muting = (function () {

var exports = {};

var muted_topics = new Dict();

exports.add_muted_topic = function (stream, topic) {
    var stream_id = stream_data.get_stream_id(stream);

    if (!stream_id) {
        return;
    }

    var sub_dict = muted_topics.get(stream_id);
    if (!sub_dict) {
        sub_dict = new Dict({fold_case: true});
        muted_topics.set(stream_id, sub_dict);
    }
    sub_dict.set(topic, true);
};

exports.remove_muted_topic = function (stream, topic) {
    var stream_id = stream_data.get_stream_id(stream);

    if (!stream_id) {
        blueslip.warn('cannot unmute stream ' + stream);
        return;
    }

    var sub_dict = muted_topics.get(stream_id);
    if (sub_dict) {
        sub_dict.del(topic);
    }
};

exports.is_topic_muted = function (stream, topic) {
    if (stream === undefined) {
        return false;
    }

    var stream_id = stream_data.get_stream_id(stream);

    if (!stream_id) {
        return false;
    }

    var sub_dict = muted_topics.get(stream_id);
    return sub_dict && sub_dict.get(topic);
};

exports.get_muted_topics = function () {
    var topics = [];
    muted_topics.each(function (sub_dict, stream_id) {
        var sub = stream_data.get_sub_by_id(stream_id);

        if (!sub) {
            blueslip.error('cannot find stream ' + stream_id);
            return;
        }

        _.each(sub_dict.keys(), function (topic) {
            topics.push([sub.name, topic]);
        });
    });
    return topics;
};

exports.set_muted_topics = function (tuples) {
    muted_topics = new Dict();

    _.each(tuples, function (tuple) {
        var stream = tuple[0];
        var topic = tuple[1];

        exports.add_muted_topic(stream, topic);
    });
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting;
}
