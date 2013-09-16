var compose_fade = (function () {

var exports = {};

var focused_recipient;
var normal_display = false;

exports.set_focused_recipient = function (msg_type) {
    if (msg_type === undefined) {
        focused_recipient = undefined;
    }

    // Construct focused_recipient as a mocked up element which has all the
    // fields of a message used by util.same_recipient()
    focused_recipient = {
        type: msg_type
    };

    if (focused_recipient.type === "stream") {
        focused_recipient.stream = $('#stream').val();
        focused_recipient.subject = $('#subject').val();
    } else {
        // Normalize the recipient list so it matches the one used when
        // adding the message (see add_message_metadata(), zulip.js).
        focused_recipient.reply_to = util.normalize_recipients(
                $('#private_message_recipient').val());
    }
};

function _display_messages_normally() {
    rows.get_table(current_msg_list.table_name).find(".recipient_row, .message_row")
                                               .removeClass("faded").removeClass("unfaded");

    normal_display = true;
    ui.update_floating_recipient_bar();
}

function _display_users_normally() {
    if (!feature_flags.fade_users_when_composing) {
        return;
    }
    $('.user_sidebar_entry').removeClass('faded').removeClass('unfaded');
}

function _fade_messages() {
    var i;
    var all_elts = rows.get_table(current_msg_list.table_name).find(".recipient_row, .message_row");
    var should_fade_message = false;

    normal_display = false;

    // Note: The below algorithm relies on the fact that all_elts is
    // sorted as it would be displayed in the message view
    for (i = 0; i < all_elts.length; i++) {
        var elt = $(all_elts[i]);
        if (elt.hasClass("recipient_row")) {
            should_fade_message = !util.same_recipient(focused_recipient, current_msg_list.get(rows.id(elt)));
        }

        if (should_fade_message) {
            elt.removeClass("unfaded").addClass("faded");
        } else {
            elt.removeClass("faded").addClass("unfaded");
        }
    }

    ui.update_floating_recipient_bar();
}

exports.would_receive_message = function (email) {
    // Given the current focused_recipient, this function returns true if
    // the user in question would definitely receive this message, false if
    // they would definitely not receive this message, and undefined if we
    // don't know (e.g. the recipient is a stream we're not subscribed to).
    //
    // Yes it's slightly weird to have three return values, but this will be
    // helpful if we want to emphasize the '.unfaded' class later (applied
    // to users who will definitely receive the message).

    if (email === page_params.email) {
        // We never want to fade you yourself, so pretend it's true even if
        // it's not.
        return true;
    }

    if (focused_recipient.type === 'stream') {
        return stream_data.user_is_subscribed(focused_recipient.stream, email);
    }

    // PM, so check if the given email is in the recipients list.
    var recipients = focused_recipient.reply_to.split(',');
    return recipients.indexOf(email) !== -1;
};

function _fade_users() {
    if (!feature_flags.fade_users_when_composing) {
        return;
    }
    _.forEach($('.user_sidebar_entry'), function (elt) {
        elt = $(elt);
        var would_receive = exports.would_receive_message(elt.attr('data-email'));
        if (would_receive === true) {
            elt.addClass('unfaded').removeClass('faded');
        } else if (would_receive === false) {
            elt.addClass('faded').removeClass('unfaded');
        } else {
            elt.removeClass('faded').removeClass('unfaded');
        }
    });
}

function _want_normal_display() {
    // If we're not composing show a normal display.
    if (focused_recipient === undefined) {
        return true;
    }

    // If the user really hasn't specified anything let, then we want a normal display
    if ((focused_recipient.type === "stream" && focused_recipient.subject === "") ||
        (focused_recipient.type === "private" && focused_recipient.reply_to === "")) {
        return true;
    }

    return false;
}

function _update_faded_messages() {
    // See also update_faded_messages(), which just wraps this with a debounce.
    // FIXME: This fades users too now, as well as messages, so should have
    // a better name.
    if (_want_normal_display()) {
        if (!normal_display) {
            _display_messages_normally();
            _display_users_normally();
        }
    }
    else {
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
    }
    else {
        _fade_messages();
    }
};

exports.update_rendered_messages = function (messages, get_elements) {
    if (_want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in _fade_messages, but an
    // important difference here is that we look at each message individually, whereas
    // the other code takes advantage of blocks beneath recipient bars.
    //
    // get_elements() is plural, because we can get up to two elements:
    //   the message (always)
    //   the recipient bar (sometimes)
    _.each(messages, function (message) {
        var elts = get_elements(message);
        var should_fade_message = !util.same_recipient(focused_recipient, message);

        _.each(elts, function (elt) {
            if (should_fade_message) {
                elt.removeClass("unfaded").addClass("faded");
            } else {
                elt.removeClass("faded").addClass("unfaded");
            }
        });
    });
};

$(function () {
    $(document).on('peer_subscribe.zulip', function (e) {
        exports.update_faded_users();
    });
    $(document).on('peer_unsubscribe.zulip', function (e) {
        exports.update_faded_users();
    });
});


return exports;

}());
