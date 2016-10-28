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

exports.is_active = function (stream_name) {
    return exports.recent_subjects.has(stream_name);
};

exports.add_sub = function (stream_name, sub) {
    if (!_.has(sub, 'subscribers')) {
        sub.subscribers = Dict.from_array([], {fold_case: true});
    }

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

exports.update_subscribers_count = function (sub) {
    var count = sub.subscribers.num_items();
    sub.subscriber_count = count;
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

exports.add_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined') {
        blueslip.warn("We got an add_subscriber call for a non-existent stream.");
        return;
    }
    sub.subscribers.set(user_email, true);
};

exports.remove_subscriber = function (stream_name, user_email) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined') {
        blueslip.warn("We got a remove_subscriber call for a non-existent stream " + stream_name);
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

exports.create_streams = function (streams) {
    _.each(streams, function (stream) {
        var attrs = _.defaults(stream, {
            subscribed: false
        });
        exports.create_sub_from_server_data(stream.name, attrs);
    });
};

exports.create_sub_from_server_data = function (stream_name, attrs) {
    var sub = exports.get_sub(stream_name);
    if (sub !== undefined) {
        // We've already created this subscription, no need to continue.
        return sub;
    }

    if (!attrs.stream_id) {
        // fail fast (blueslip.fatal will throw an error on our behalf)
        blueslip.fatal("We cannot create a sub without a stream_id");
        return; // this line is never actually reached
    }

    // Our internal data structure for subscriptions is mostly plain dictionaries,
    // so we just reuse the attrs that are passed in to us, but we encapsulate how
    // we handle subscribers.
    var subscriber_emails = attrs.subscribers;
    var raw_attrs = _.omit(attrs, 'subscribers');

    sub = _.defaults(raw_attrs, {
        name: stream_name,
        render_subscribers: !page_params.is_zephyr_mirror_realm || attrs.invite_only === true,
        subscribed: true,
        in_home_view: true,
        invite_only: false,
        desktop_notifications: page_params.stream_desktop_notifications_enabled,
        audible_notifications: page_params.stream_sounds_enabled,
        description: ''
    });

    exports.set_subscribers(sub, subscriber_emails);

    if (!sub.color) {
        var used_colors = exports.get_colors();
        sub.color = stream_color.pick_color(used_colors);
    }

    exports.add_sub(stream_name, sub);

    return sub;
};

exports.receives_desktop_notifications = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.desktop_notifications;
};

exports.receives_audible_notifications = function (stream_name) {
    var sub = exports.get_sub(stream_name);
    if (sub === undefined) {
        return false;
    }
    return sub.audible_notifications;
};

exports.add_admin_options = function (sub) {
    return _.extend(sub, {
        'is_admin': page_params.is_admin,
        'can_make_public': page_params.is_admin && sub.invite_only && sub.subscribed,
        'can_make_private': page_params.is_admin && !sub.invite_only
    });
};

exports.process_message_for_recent_topics = function process_message_for_recent_topics(message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var stream = message.stream;
    var canon_subject = exports.canonicalized_name(message.subject);

    if (! exports.recent_subjects.has(stream)) {
        exports.recent_subjects.set(stream, []);
    } else {
        exports.recent_subjects.set(stream, _.filter(exports.recent_subjects.get(stream), function (item) {
            var is_duplicate = (item.canon_subject.toLowerCase() === canon_subject.toLowerCase());
            if (is_duplicate) {
                current_timestamp = item.timestamp;
                count = item.count;
            }
            return !is_duplicate;
        }));
    }

    var recents = exports.recent_subjects.get(stream);

    if (remove_message !== undefined) {
        count = count - 1;
    } else {
        count = count + 1;
    }

    if (count !== 0) {
        recents.push({subject: message.subject,
                      canon_subject: canon_subject,
                      count: count,
                      timestamp: Math.max(message.timestamp, current_timestamp)});
    }

    recents.sort(function (a, b) {
        return b.timestamp - a.timestamp;
    });

    exports.recent_subjects.set(stream, recents);
};

exports.get_streams_for_settings_page = function (public_streams) {
    // Build up our list of subscribed streams from the data we already have.
    var subscribed_rows = exports.subscribed_subs();

    // To avoid dups, build a set of names we already subscribed to.
    var subscribed_set = new Dict({fold_case: true});
    _.each(subscribed_rows, function (sub) {
        subscribed_set.set(sub.name, true);
    });

    // Right now the back end gives us all public streams; we really only
    // need to add the ones we haven't already subscribed to.
    var unsubscribed_streams = _.reject(public_streams.streams, function (stream) {
        return subscribed_set.has(stream.name);
    });

    // Build up our list of unsubscribed rows.
    var unsubscribed_rows = [];
    _.each(unsubscribed_streams, function (stream) {
        var sub = exports.get_sub(stream.name);
        if (!sub) {
            sub = exports.create_sub_from_server_data(
                    stream.name,
                    _.extend({subscribed: false}, stream));
        }
        unsubscribed_rows.push(sub);
    });

    // Sort and combine all our streams.
    function by_name(a,b) {
        return util.strcmp(a.name, b.name);
    }
    subscribed_rows.sort(by_name);
    unsubscribed_rows.sort(by_name);
    var all_subs = subscribed_rows.concat(unsubscribed_rows);

    // Add in admin options and stream counts.
    var sub_rows = [];
    _.each(all_subs, function (sub) {
        sub = exports.add_admin_options(sub);
        exports.update_subscribers_count(sub);
        sub_rows.push(sub);
    });

    return sub_rows;
};

exports.initialize_from_page_params = function () {
    function populate_subscriptions(subs, subscribed) {
        subs.forEach(function (sub) {
            var stream_name = sub.name;
            sub.subscribed = subscribed;

            // When we get subscriber lists from the back end,
            // they are sent as user ids to save bandwidth,
            // but the legacy JS code wants emails.
            if (sub.subscribers) {
                sub.subscribers = _.map(sub.subscribers, function (subscription) {
                    return page_params.email_dict[subscription];
                });
            }
            exports.create_sub_from_server_data(stream_name, sub);
        });
    }

    populate_subscriptions(page_params.subbed_info, true);
    populate_subscriptions(page_params.unsubbed_info, false);
    populate_subscriptions(page_params.neversubbed_info, false);

    // Garbage collect data structures that were only used for initialization.
    delete page_params.subbed_info;
    delete page_params.unsubbed_info;
    delete page_params.neversubbed_info;
    delete page_params.email_dict;
};

exports.get_recent_topics = function (stream_name) {
    return exports.recent_subjects.get(stream_name);
};

exports.populate_stream_topics_for_tests = function (stream_map) {
    // This is only used by tests.
    exports.recent_subjects = new Dict.from(stream_map, {fold_case: true});
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_data;
}
