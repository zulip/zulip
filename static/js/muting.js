var muting = (function () {

var exports = {};

var muted_topics = new Dict({fold_case: true});

exports.add_muted_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (!sub_dict) {
        sub_dict = new Dict({fold_case: true});
        muted_topics.set(stream, sub_dict);
    }
    sub_dict.set(topic, true);
};

exports.remove_muted_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (sub_dict) {
        sub_dict.del(topic);
    }
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

        exports.add_muted_topic(stream, topic);
    });
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting;
}
