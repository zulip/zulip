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
        var stream_name = $('#stream').val();
        focused_recipient.subject = $('#subject').val();
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

function _display_messages_normally() {
    var table = rows.get_table(current_msg_list.table_name);
    table.find('.recipient_row').removeClass("message-fade");

    normal_display = true;
    floating_recipient_bar.update();
}

function _display_users_normally() {
    $('.user_sidebar_entry').removeClass('user-fade');
}

function change_fade_state(elt, should_fade_group) {
    if (should_fade_group) {
        elt.addClass("message-fade");
    } else {
        elt.removeClass("message-fade");
    }
}

function _fade_messages() {
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
    // Given the current focused_recipient, this function returns true if
    // the user in question would definitely receive this message, false if
    // they would definitely not receive this message, and undefined if we
    // don't know (e.g. the recipient is a stream we're not subscribed to).
    //
    // The distinction between undefined and true is historical.  We really
    // only ever fade stuff if would_receive_message() returns false; i.e.
    // we are **sure** that you would **not** receive the message.

    if (people.is_current_user(email)) {
        // We never want to fade you yourself, so pretend it's true even if
        // it's not.
        return true;
    }

    if (focused_recipient.type === 'stream') {
        var user = people.get_active_user_for_email(email);
        var sub = stream_data.get_sub(focused_recipient.stream);
        if (!sub || !user) {
            // If the stream or user isn't valid, there is no risk of a mix
            // yet, so don't fade.
            return;
        }

        if (user && user.is_bot && !sub.invite_only) {
            // Bots may receive messages on public streams even if they are
            // not subscribed.
            return;
        }
        return stream_data.is_user_subscribed(focused_recipient.stream, user.user_id);
    }

    // PM, so check if the given email is in the recipients list.
    return util.is_pm_recipient(email, focused_recipient);
};

function update_user_row_when_fading(elt) {
    var user_id = elt.attr('data-user-id');
    var email = people.get_person_from_user_id(user_id).email;
    var would_receive = exports.would_receive_message(email);
    if (would_receive === false) {
        elt.addClass('user-fade');
    } else {
        // would_receive is either true (so definitely don't fade) or
        // undefined (in which case we don't presume to fade)
        elt.removeClass('user-fade');
    }
}

function _fade_users() {
    _.forEach($('.user_sidebar_entry'), function (elt) {
        elt = $(elt);
        update_user_row_when_fading(elt);
    });
}

function _want_normal_display() {
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
        if (focused_recipient.subject === "") {
            return true;
        }
    }

    return focused_recipient.type === "private" && focused_recipient.reply_to === "";
}

exports.update_one_user_row = function (elt) {
    if (_want_normal_display()) {
        elt.removeClass('user-fade');
    } else {
        update_user_row_when_fading(elt);
    }
};

function _update_faded_messages() {
    // See also update_faded_messages(), which just wraps this with a debounce.
    // FIXME: This fades users too now, as well as messages, so should have
    // a better name.
    if (_want_normal_display()) {
        if (!normal_display) {
            _display_messages_normally();
            _display_users_normally();
        }
    } else {
        _fade_messages();
        _fade_users();
    }
}

// This one only updates the users, not both, like update_faded_messages.
// This is for when new presence information comes in, redrawing the presence
// list.
exports.update_faded_users = function () {
    if (_want_normal_display()) {
        _display_users_normally();
    } else {
        _fade_users();
    }
};

// See trac #1633.  For fast typists, calls to _update_faded_messages can
// cause typing sluggishness.
exports.update_faded_messages = _.debounce(_update_faded_messages, 50);

exports.start_compose = function (msg_type) {
    exports.set_focused_recipient(msg_type);
    _update_faded_messages();
};

exports.clear_compose = function () {
    focused_recipient = undefined;
    _display_messages_normally();
    _display_users_normally();
};

exports.update_message_list = function () {
    if (_want_normal_display()) {
       _display_messages_normally();
    } else {
        _fade_messages();
    }
};

exports.update_rendered_message_groups = function (message_groups, get_element) {
    if (_want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in _fade_messages, but an
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
