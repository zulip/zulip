var stream_sort = (function () {

var exports = {};

var previous_pinned;
var previous_normal;
var previous_dormant;
var all_streams = [];

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

exports.sort_groups = function (search_term) {
    var streams = stream_data.subscribed_streams();
    if (streams.length === 0) {
        return;
    }

    streams = filter_streams_by_search(streams, search_term);

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

    pinned_streams.sort(util.strcmp);
    normal_streams.sort(util.strcmp);
    dormant_streams.sort(util.strcmp);

    var same_as_before =  (
        previous_pinned !== undefined &&
        util.array_compare(previous_pinned, pinned_streams) &&
        util.array_compare(previous_normal, normal_streams) &&
        util.array_compare(previous_dormant, dormant_streams));

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

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = stream_sort;
}
