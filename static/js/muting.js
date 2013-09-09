var muting = (function () {

var exports = {};

var muted_topics = new Dict();

exports.mute_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (!sub_dict) {
        sub_dict = new Dict();
        muted_topics.set(stream, sub_dict);
    }
    sub_dict.set(topic, true);
};

exports.unmute_topic = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    if (sub_dict) {
        sub_dict.del(topic);
    }
};

exports.is_topic_muted = function (stream, topic) {
    var sub_dict = muted_topics.get(stream);
    return sub_dict && sub_dict.get(topic);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = muting;
}
