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
    if (_want_normal_display()) {
        if (!normal_display) {
            _display_messages_normally();
        }
    }
    else {
        _fade_messages();
    }
}

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
};

exports.update_message_list = function () {
    if (_want_normal_display()) {
       _display_messages_normally();
    }
    else {
        _fade_messages();
    }
};

exports.update_rendered_messages = function (messages, get_element) {
    if (_want_normal_display()) {
        return;
    }

    // This loop is superficially similar to some code in _fade_messages, but an
    // important difference here is that we look at each message individually, whereas
    // the other code takes advantage of blocks beneath recipient bars.
    _.each(messages, function (message) {
        var elt = get_element(message);
        var should_fade_message = !util.same_recipient(focused_recipient, message);

        if (should_fade_message) {
            elt.removeClass("unfaded").addClass("faded");
        } else {
            elt.removeClass("faded").addClass("unfaded");
        }
    });
};

return exports;

}());
