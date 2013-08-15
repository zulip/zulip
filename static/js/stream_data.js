var stream_data = (function () {

var exports = {};

var stream_info = new Dict(); // Maps lowercase stream name to stream properties object


exports.add_sub = function (stream_name, sub) {
    stream_info.set(stream_name.toLowerCase(), sub);
};

exports.get_sub = function (stream_name) {
    return stream_info.get(stream_name.toLowerCase());
};

exports.set_stream_info = function (new_stream_info) {
    stream_info = new_stream_info;
};

exports.get_stream_info = function () {
    return stream_info;
};

// List subscribed streams.
// Internal version returns the full stream info object for each stream.
function subscribed_streams() {
    return _.where(stream_info.values(), {subscribed: true});
}

exports.subscribed_streams = function () {
    return _.pluck(subscribed_streams(), 'name');
};

exports.get_colors = function () {
    return _.pluck(subscribed_streams(), 'color');
};

exports.all_subscribed_streams_are_in_home_view = function () {
    return _.every(subscribed_streams(), function (sub) {
        return sub.in_home_view; }
    );
};

exports.clear_subscriptions = function () {
    stream_info = new Dict();
};

exports.canonicalized_name = function (stream_name) {
   return stream_name.toString().toLowerCase();
};

exports.get_color = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    if (sub === undefined) {
        return stream_color.default_color;
    }
    return sub.color;
};

exports.in_home_view = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    return sub !== undefined && sub.in_home_view;
};

exports.is_subscribed = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    return sub !== undefined && sub.subscribed;
};

exports.get_invite_only = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.invite_only;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_data;
}
