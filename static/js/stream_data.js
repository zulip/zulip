var stream_data = (function () {

var exports = {};


// The stream_info variable maps stream names to stream properties objects
// Call clear_subscriptions() to initialize it.
var stream_info;
var subs_by_stream_id;
var recent_topics = new Dict({fold_case: true});

exports.clear_subscriptions = function () {
    stream_info = new Dict({fold_case: true});
    subs_by_stream_id = new Dict();
};

exports.clear_subscriptions();

exports.is_active = function (stream_name) {
    return recent_topics.has(stream_name);
};

exports.rename_sub = function (sub, new_name) {
    var old_name = sub.name;
    sub.name = new_name;
    stream_info.del(old_name);
    stream_info.set(new_name, sub);
};

exports.subscribe_myself = function (sub) {
    var user_id = people.my_current_user_id();
    exports.add_subscriber(sub.name, user_id);
    sub.subscribed = true;
};

exports.unsubscribe_myself = function (sub) {
    // Remove user from subscriber's list
    var user_id = people.my_current_user_id();
    exports.remove_subscriber(sub.name, user_id);
    sub.subscribed = false;
};

exports.add_sub = function (stream_name, sub) {
    if (!_.has(sub, 'subscribers')) {
        sub.subscribers = Dict.from_array([]);
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

exports.delete_sub = function (stream_id) {
    var sub = subs_by_stream_id.get(stream_id);
    if (!sub) {
        blueslip.warn('Failed to delete stream ' + stream_id);
        return;
    }
    subs_by_stream_id.del(stream_id);
    stream_info.del(sub.name);
};

exports.subscribed_subs = function () {
    return _.where(stream_info.values(), {subscribed: true});
};

exports.unsubscribed_subs = function () {
    return _.where(stream_info.values(), {subscribed: false});
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
        return sub.in_home_view;
    });
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

exports.set_subscribers = function (sub, user_ids) {
    sub.subscribers = Dict.from_array(user_ids || []);
};

exports.set_subscriber_emails = function (sub, emails) {
    _.each(emails, function (email) {
        var user_id = people.get_user_id(email);
        if (!user_id) {
            blueslip.error("We tried to set invalid subscriber: " + email);
        } else {
            sub.subscribers.set(user_id, true);
        }
    });
};

exports.add_subscriber = function (stream_name, user_id) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined') {
        blueslip.warn("We got an add_subscriber call for a non-existent stream.");
        return false;
    }
    var person = people.get_person_from_user_id(user_id);
    if (person === undefined) {
        blueslip.error("We tried to add invalid subscriber: " + user_id);
        return false;
    }
    sub.subscribers.set(user_id, true);

    return true;
};

exports.remove_subscriber = function (stream_name, user_id) {
    var sub = exports.get_sub(stream_name);
    if (typeof sub === 'undefined') {
        blueslip.warn("We got a remove_subscriber call for a non-existent stream " + stream_name);
        return false;
    }
    if (!sub.subscribers.has(user_id)) {
        blueslip.warn("We tried to remove invalid subscriber: " + user_id);
        return false;
    }

    sub.subscribers.del(user_id);

    return true;
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
    var user_id = people.get_user_id(user_email);
    if (!user_id) {
        blueslip.warn("Bad email passed to user_is_subscribed: " + user_email);
        return false;
    }

    return sub.subscribers.has(user_id);
};

exports.create_streams = function (streams) {
    _.each(streams, function (stream) {
        // We handle subscriber stuff in other events.
        var attrs = _.defaults(stream, {
            subscribers: [],
            subscribed: false,
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
    var subscriber_user_ids = attrs.subscribers;
    var raw_attrs = _.omit(attrs, 'subscribers');

    sub = _.defaults(raw_attrs, {
        name: stream_name,
        render_subscribers: !page_params.is_zephyr_mirror_realm || attrs.invite_only === true,
        subscribed: true,
        in_home_view: true,
        invite_only: false,
        desktop_notifications: page_params.stream_desktop_notifications_enabled,
        audible_notifications: page_params.stream_sounds_enabled,
        description: '',
    });

    exports.set_subscribers(sub, subscriber_user_ids);

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
        is_admin: page_params.is_admin,
        can_make_public: page_params.is_admin && sub.invite_only && sub.subscribed,
        can_make_private: page_params.is_admin && !sub.invite_only,
    });
};

exports.process_message_for_recent_topics = function process_message_for_recent_topics(
                                                message, remove_message) {
    var current_timestamp = 0;
    var count = 0;
    var stream = message.stream;
    var canon_subject = exports.canonicalized_name(message.subject);

    if (! recent_topics.has(stream)) {
        recent_topics.set(stream, []);
    } else {
        recent_topics.set(stream, _.filter(recent_topics.get(stream), function (item) {
            var is_duplicate = (item.canon_subject.toLowerCase() === canon_subject.toLowerCase());
            if (is_duplicate) {
                current_timestamp = item.timestamp;
                count = item.count;
            }
            return !is_duplicate;
        }));
    }

    var recents = recent_topics.get(stream);

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

    recent_topics.set(stream, recents);
};

exports.get_streams_for_settings_page = function () {
    // Build up our list of subscribed streams from the data we already have.
    var subscribed_rows = exports.subscribed_subs();
    var unsubscribed_rows = exports.unsubscribed_subs();

    // Sort and combine all our streams.
    function by_name(a,b) {
        return util.strcmp(a.name, b.name);
    }
    subscribed_rows.sort(by_name);
    unsubscribed_rows.sort(by_name);
    var all_subs = unsubscribed_rows.concat(subscribed_rows);

    // Add in admin options and stream counts.
    var sub_rows = [];
    _.each(all_subs, function (sub) {
        sub = exports.add_admin_options(sub);
        sub.preview_url = narrow.by_stream_uri(sub.name);
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
};

exports.get_recent_topics = function (stream_name) {
    return recent_topics.get(stream_name);
};

exports.populate_stream_topics_for_tests = function (stream_map) {
    // This is only used by tests.
    recent_topics = Dict.from(stream_map, {fold_case: true});
};

exports.get_newbie_stream = function () {
    // This is the stream that we narrow folks to after the tutorial.

    if (exports.is_subscribed("new members")) {
        return "new members";
    } else if (exports.in_home_view(page_params.notifications_stream)) {
        return page_params.notifications_stream;
    }
    return undefined;
};

exports.remove_default_stream = function (stream_id) {
    page_params.realm_default_streams = _.reject(page_params.realm_default_streams,
        function (stream) {
            return stream.stream_id === stream_id;
        }
    );
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_data;
}
