const Dict = require('./dict').Dict;

let muted_topics = new Dict();

exports.add_muted_topic = function (stream_id, topic) {
    let sub_dict = muted_topics.get(stream_id);
    if (!sub_dict) {
        sub_dict = new Dict({fold_case: true});
        muted_topics.set(stream_id, sub_dict);
    }
    sub_dict.set(topic, true);
};

exports.remove_muted_topic = function (stream_id, topic) {
    const sub_dict = muted_topics.get(stream_id);
    if (sub_dict) {
        sub_dict.del(topic);
    }
};

exports.is_topic_muted = function (stream_id, topic) {
    if (stream_id === undefined) {
        return false;
    }
    const sub_dict = muted_topics.get(stream_id);
    return sub_dict && sub_dict.get(topic);
};

exports.get_muted_topics = function () {
    const topics = [];
    muted_topics.each(function (sub_dict, stream_id) {
        _.each(sub_dict.keys(), function (topic) {
            topics.push([stream_id, topic]);
        });
    });
    return topics;
};

exports.set_muted_topics = function (tuples) {
    muted_topics = new Dict();

    _.each(tuples, function (tuple) {
        const stream_name = tuple[0];
        const topic = tuple[1];

        const stream_id = stream_data.get_stream_id(stream_name);

        if (!stream_id) {
            blueslip.warn('Unknown stream in set_muted_topics: ' + stream_name);
            return;
        }

        exports.add_muted_topic(stream_id, topic);
    });
};

exports.initialize = function () {
    exports.set_muted_topics(page_params.muted_topics);
};

window.muting = exports;
