var stream_data = (function () {

var exports = {};

var stream_info = new Dict(); // Maps lowercase stream name to stream properties object


exports.add_sub = function (stream_name, sub) {
    stream_info.set(stream_name.toLowerCase(), sub);
};

exports.get_sub = function (stream_name) {
    return stream_info.get(stream_name.toLowerCase());
};

exports.delete_sub = function (stream_name) {
    stream_info.del(stream_name.toLowerCase());
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

exports.get_name = function (stream_name) {
    // This returns the actual name of a stream if we are subscribed to
    // it (i.e "Denmark" vs. "denmark"), while falling thru to
    // stream_name if we don't have a subscription.  (Stream names
    // are case-insensitive, but we try to display the actual name
    // when we know it.)
    var sub = exports.get_sub(stream_name);
    if (sub === undefined) {
        return stream_name;
    }
    return sub.name;
};

exports.add_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (!sub.hasOwnProperty('subscribers')) {
        // FIXME: Temporary hack because this is not initialized.
        sub.subscribers = new Dict();
    }
    sub.subscribers.set(user_email, true);
};

exports.remove_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (!sub.hasOwnProperty('subscribers')) {
        // FIXME: Temporary hack because this is not initialized.
        return;
    }
    sub.subscribers.del(user_email);
};

exports.user_is_subscribed = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (!sub.hasOwnProperty('subscribers')) {
        // FIXME: Hack because this is not fully implemented.
        return undefined;
    }
    return sub.subscribers.has(user_email);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_data;
}
