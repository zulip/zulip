var stream_data = (function () {

var exports = {};


// The stream_info variable maps stream names to stream properties objects
// Call clear_subscriptions() to initialize it.
var stream_info;
var subs_by_stream_id;

exports.clear_subscriptions = function () {
    stream_info = new Dict({fold_case: true});
    subs_by_stream_id = new Dict();
};

exports.recent_subjects = new Dict({fold_case: true});
exports.clear_subscriptions();


exports.add_sub = function (stream_name, sub) {
    stream_info.set(stream_name, sub);
    subs_by_stream_id.set(sub.stream_id, sub);
};

exports.get_sub = function (stream_name) {
    return stream_info.get(stream_name);
};

exports.get_sub_by_id = function (stream_id) {
    return subs_by_stream_id.get(stream_id);
};

exports.delete_sub = function (stream_name) {
    stream_info.del(stream_name);
};

exports.subscribed_subs = function () {
    return _.where(stream_info.values(), {subscribed: true});
};

exports.subscribed_streams = function () {
    return _.pluck(exports.subscribed_subs(), 'name');
};

exports.get_colors = function () {
    return _.pluck(exports.subscribed_subs(), 'color');
};

exports.all_subscribed_streams_are_in_home_view = function () {
    return _.every(exports.subscribed_subs(), function (sub) {
        return sub.in_home_view; }
    );
};

exports.home_view_stream_names = function () {
    var home_view_subs = _.filter(exports.subscribed_subs(), function (sub) {
            return sub.in_home_view;
        }
    );
    return _.map(home_view_subs, function (sub) {
        return sub.name;
    });
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

exports.set_subscribers = function (sub, emails) {
    sub.subscribers = Dict.from_array(emails || [], {fold_case: true});
};

// NOTE: If you do anything with the `subscribers` attribute on the stream
// properties object, first make sure `is_subscribed` is true (i.e., the local
// user is subscribed). Otherwise we don't and can't update the subscribers
// list.
//
// The accessor functions below know to check for that case.

exports.add_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined' || !sub.subscribed) {
        // If we're not subscribed, we don't track this, and shouldn't
        // get these events. Likewise, if we don't know about the stream,
        // we don't want to track this.
        blueslip.warn("We got an add_subscriber call for a non-existent or unsubscribed stream.");
        return;
    }
    sub.subscribers.set(user_email, true);
};

exports.remove_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined' || !sub.subscribed) {
        // If we're not subscribed, we don't track this, and shouldn't
        // get these events. Likewise, if we don't know about the stream,
        // we don't want to track this.
        blueslip.warn("We got a remove_subscriber call for a non-existent or unsubscribed stream.");
        return;
    }
    sub.subscribers.del(user_email);
};

exports.user_is_subscribed = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined' || !sub.subscribed) {
        // If we don't know about the stream, or we ourselves are not
        // subscribed, we can't keep track of the subscriber list in general,
        // so we return undefined (treated as falsy if not explicitly handled).
        blueslip.warn("We got a user_is_subscribed call for a non-existent or unsubscribed stream.");
        return undefined;
    }
    return sub.subscribers.has(user_email);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_data;
}
