var compose_fade = (function () {

var exports = {};

var focused_recipient;
var normal_display = false;

exports.should_fade_message =  function (message) {
    return !util.same_recipient(focused_recipient, message);
};

exports.set_focused_recipient = function (msg_type) {
    if (msg_type === undefined) {
        focused_recipient = undefined;
    }

    // Construct focused_recipient as a mocked up element which has all the
    // fields of a message used by util.same_recipient()
    focused_recipient = {
        type: msg_type,
    };

    if (focused_recipient.type === "stream") {
        var stream_name = $('#stream_message_recipient_stream').val();
        focused_recipient.topic = $('#stream_message_recipient_topic').val();
        focused_recipient.stream = stream_name;
        var sub = stream_data.get_sub(stream_name);
        if (sub) {
            focused_recipient.stream_id = sub.stream_id;
        }
    } else {
        // Normalize the recipient list so it matches the one used when
        // adding the message (see message_store.add_message_metadata()).
        var reply_to = util.normalize_recipients(compose_state.recipient());
        focused_recipient.reply_to = reply_to;
        focused_recipient.to_user_ids = people.reply_to_to_user_ids_string(reply_to);
    }
};

function display_messages_normally() {
    var table = rows.get_table(current_msg_list.table_name);
    table.find('.recipient_row').removeClass("message-fade");

    normal_display = true;
    floating_recipient_bar.update();
}

function change_fade_state(elt, should_fade_group) {
    if (should_fade_group) {
        elt.addClass("message-fade");
    } else {
        elt.removeClass("message-fade");
    }
}

function fade_messages() {
    var i;
    var first_message;
    var first_row;
    var should_fade_group = false;
    var visible_groups = message_viewport.visible_groups(false);

    normal_display = false;

    // Update the visible messages first, before the compose box opens
    for (i = 0; i < visible_groups.length; i += 1) {
        first_row = rows.first_message_in_group(visible_groups[i]);
        first_message = current_msg_list.get(rows.id(first_row));
        should_fade_group = exports.should_fade_message(first_message);

        change_fade_state($(visible_groups[i]), should_fade_group);
    }

    // Defer updating all message groups so that the compose box can open sooner
    setTimeout(function (expected_msg_list, expected_recipient) {
        var all_groups = rows.get_table(current_msg_list.table_name).find(".recipient_row");

        if (current_msg_list !== expected_msg_list ||
            !compose_state.composing() ||
            compose_state.recipient() !== expected_recipient) {
            return;
        }

        should_fade_group = false;

        // Note: The below algorithm relies on the fact that all_elts is
        // sorted as it would be displayed in the message view
        for (i = 0; i < all_groups.length; i += 1) {
            var group_elt = $(all_groups[i]);
            should_fade_group = exports.should_fade_message(rows.recipient_from_group(group_elt));
            change_fade_state(group_elt, should_fade_group);
        }

        floating_recipient_bar.update();
    }, 0, current_msg_list, compose_state.recipient());
}

exports.would_receive_message = function (email) {
    if (focused_recipient.type === 'stream') {
        var user = people.get_active_user_for_email(email);
        var sub = stream_data.get_sub(focused_recipient.stream);
        if (!sub || !user) {
            // If the stream or user isn't valid, there is no risk of a mix
            // yet, so we sort of "lie" and say they would receive a
            // message.
            return true;
        }

        return stream_data.is_user_subscribed(focused_recipient.stream, user.user_id);
    }

    // PM, so check if the given email is in the recipients list.
    return util.is_pm_recipient(email, focused_recipient);
};

var user_fade_config = {
    get_user_id: function (li) {
        return buddy_list.get_key_from_li({li: li});
    },
    fade: function (li) {
        return li.addClass('user-fade');
    },
    unfade: function (li) {
        return li.removeClass('user-fade');
    },
};

function update_user_row_when_fading(li, conf) {
    var user_id = conf.get_user_id(li);
    var email = people.get_person_from_user_id(user_id).email;
    var would_receive = exports.would_receive_message(email);

    if (would_receive) {
        conf.unfade(li);
    } else {
        conf.fade(li);
    }
}

function display_users_normally(items, conf) {
    _.each(items, function (li) {
        conf.unfade(li);
    });
}

function fade_users(items, conf) {
    _.each(items, function (li) {
        update_user_row_when_fading(li, conf);
    });
}

function want_normal_display() {
    // If we're not composing show a normal display.
    if (focused_recipient === undefined) {
        return true;
    }

    // If the user really hasn't specified anything let, then we want a normal display
    if (focused_recipient.type === "stream") {
        // If a stream doesn't exist, there is no real chance of a mix, so fading
        // is just noise to the user.
        if (!stream_data.get_sub(focused_recipient.stream)) {
            return true;
        }

        // This is kind of debatable.  If the topic is empty, it could be that
        // the user simply hasn't started typing it yet, but disabling fading here
        // means the feature doesn't help realms where topics aren't mandatory
        // (which is most realms as of this writing).
        if (focused_recipient.topic === "") {
            return true;
        }
    }

    return focused_recipient.type === "private" && focused_recipient.reply_to === "";
}

function do_update_all() {
    var user_items = buddy_list.get_items();

    if (want_normal_display()) {
        if (!normal_display) {
            display_messages_normally();
            display_users_normally(user_items, user_fade_config);
        }
    } else {
        fade_messages();
        fade_users(user_items, user_fade_config);
    }
}

// This one only updates the users, not both, like update_faded_messages.
// This is for when new presence information comes in, redrawing the presence
// list.
exports.update_faded_users = function () {
    var user_items = buddy_list.get_items();

    exports.update_user_info(user_items, user_fade_config);
};

exports.update_user_info = function (items, conf) {
    if (want_normal_display()) {
        display_users_normally(items, conf);
    } else {
        fade_users(items, conf);
    }
};

// This gets called on keyup events, hence the throttling.
exports.update_all = _.debounce(do_update_all, 50);

exports.start_compose = function (msg_type) {
    exports.set_focused_recipient(msg_type);
    do_update_all();
};

exports.clear_compose = function () {
    focused_recipient = undefined;
    display_messages_normally();
    exports.update_faded_users();
};

exports.update_message_list = function () {
    if (want_normal_display()) {
        display_messages_normally();
    } else {
        fade_messages();
    }
};

exports.update_rendered_message_groups = function (message_groups, get_element) {
    if (want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in fade_messages, but an
    // important difference here is that we look at each message individually, whereas
    // the other code takes advantage of blocks beneath recipient bars.
    _.each(message_groups, function (message_group) {
        var elt = get_element(message_group);
        var first_message = message_group.message_containers[0].msg;
        var should_fade = exports.should_fade_message(first_message);
        change_fade_state(elt, should_fade);
    });
};

exports.initialize = function () {
    $(document).on('peer_subscribe.zulip', function () {
        exports.update_faded_users();
    });
    $(document).on('peer_unsubscribe.zulip', function () {
        exports.update_faded_users();
    });
};


return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = compose_fade;
}
window.compose_fade = compose_fade;
