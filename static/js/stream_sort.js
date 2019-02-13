var stream_sort = (function () {

var exports = {};

var previous_pinned;
var previous_normal;
var previous_dormant;
var all_streams = [];
var stream_latest_message_id = {}; //key name gives the id of the latest message
var recent_streams = false;

exports.get_streams = function () {
    // Right now this is only used for testing, but we should
    // use it for things like hotkeys that cycle through streams.
    return all_streams;
};

function filter_streams_by_search(streams, search_term) {
    if (search_term === '') {
        return streams;
    }

    var search_terms = search_term.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var filtered_streams = _.filter(streams, function (stream) {
        return _.any(search_terms, function (search_term) {
            var lower_stream_name = stream.toLowerCase();
            var cands = lower_stream_name.split(" ");
            cands.push(lower_stream_name);
            return _.any(cands, function (name) {
                return name.indexOf(search_term) === 0;
            });
        });
    });

    return filtered_streams;
}

function sort_streams_by_recency(streams) {
    streams.sort(function (a, b) {
        var a_id;
        var b_id;
        if (stream_latest_message_id.hasOwnProperty(b)) {
            b_id = stream_latest_message_id[b];
        } else {
            b_id = 0;
        }
        if (stream_latest_message_id.hasOwnProperty(a)) {
            a_id = stream_latest_message_id[a];
        } else {
            a_id = 0;
        }
        return b_id - a_id;
    });
    return streams;
}

exports.set_stream_latest_message_id = function (name, message_id) {
    stream_latest_message_id[name] = message_id;
};

exports.set_sort_streams_by_recency = function () {
    recent_streams = !recent_streams;
};

exports.sort_groups = function (search_term) {
    var streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    streams = filter_streams_by_search(streams, search_term);
    if (recent_streams) {
        streams = sort_streams_by_recency(streams);
    }

    function is_normal(sub) {
        return stream_data.is_active(sub);
    }

    var pinned_streams = [];
    var normal_streams = [];
    var dormant_streams = [];

    _.each(streams, function (stream) {
        var sub = stream_data.get_sub(stream);
        var pinned = sub.pin_to_top;
        if (pinned) {
            pinned_streams.push(stream);
        } else if (is_normal(sub)) {
            normal_streams.push(stream);
        } else {
            dormant_streams.push(stream);
        }
    });

    if (!recent_streams) {
        pinned_streams.sort(util.strcmp);
        normal_streams.sort(util.strcmp);
        dormant_streams.sort(util.strcmp);
    }

    var same_as_before =
        previous_pinned !== undefined &&
        util.array_compare(previous_pinned, pinned_streams) &&
        util.array_compare(previous_normal, normal_streams) &&
        util.array_compare(previous_dormant, dormant_streams);

    if (!same_as_before) {
        previous_pinned = pinned_streams;
        previous_normal = normal_streams;
        previous_dormant = dormant_streams;

        all_streams = pinned_streams.concat(normal_streams, dormant_streams);
    }

    return {
        same_as_before: same_as_before,
        pinned_streams: pinned_streams,
        normal_streams: normal_streams,
        dormant_streams: dormant_streams,
    };
};

function pos(stream_id) {
    var sub = stream_data.get_sub_by_id(stream_id);
    var name = sub.name;
    var i = all_streams.indexOf(name);

    if (i < 0) {
        return;
    }

    return i;
}

function maybe_get_stream_id(i) {
    if (i < 0 || i >= all_streams.length) {
        return;
    }

    var name = all_streams[i];
    var stream_id = stream_data.get_stream_id(name);
    return stream_id;
}

exports.first_stream_id = function () {
    return maybe_get_stream_id(0);
};

exports.prev_stream_id = function (stream_id) {
    var i = pos(stream_id);

    if (i === undefined) {
        return;
    }

    return maybe_get_stream_id(i - 1);
};

exports.next_stream_id = function (stream_id) {
    var i = pos(stream_id);

    if (i === undefined) {
        return;
    }

    return maybe_get_stream_id(i + 1);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = stream_sort;
}
window.stream_sort = stream_sort;
