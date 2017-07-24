var topic_data = (function () {

var exports = {};

var recent_topics = new Dict(); // stream_id -> array of objects

exports.stream_has_topics = function (stream_id) {
    return recent_topics.has(stream_id);
};

exports.process_message = function (message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var stream_id = message.stream_id;
    var canon_topic = message.subject.toLowerCase();

    var recents = recent_topics.get(stream_id) || [];

    recents = _.filter(recents, function (item) {
        var is_duplicate = (
            item.name.toLowerCase() === canon_topic);
        if (is_duplicate) {
            current_timestamp = item.timestamp;
            count = item.count;
        }
        return !is_duplicate;
    });

    if (remove_message !== undefined) {
        count = count - 1;
    } else {
        count = count + 1;
    }

    if (count !== 0) {
        recents.push({name: message.subject,
                      count: count,
                      timestamp: Math.max(message.timestamp, current_timestamp)});
    }

    recents.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });

    recent_topics.set(stream_id, recents);
};

exports.get_recent_names = function (stream_id) {
    var topic_objs = recent_topics.get(stream_id);

    if (!topic_objs) {
        return [];
    }

    return _.map(topic_objs, function (obj) {
        return obj.name;
    });
};

exports.populate_for_tests = function (stream_map) {
    // This is only used by tests.
    recent_topics = Dict.from(stream_map);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = topic_data;
}
