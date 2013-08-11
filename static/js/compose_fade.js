var compose_fade = (function () {

var exports = {};

var focused_recipient;
var any_messages_faded = false;

exports.set_focused_recipient = function (recipient) {
    focused_recipient = recipient;
};

exports.unfade_messages = function (clear_state) {
    if (focused_recipient === undefined) {
        return;
    }

    if (!any_messages_faded) {
        return;
    }

    rows.get_table(current_msg_list.table_name).find(".recipient_row, .message_row")
                                               .removeClass("faded").addClass("unfaded");

    any_messages_faded = false;

    if (clear_state === true) {
        focused_recipient = undefined;
    }
    ui.update_floating_recipient_bar();
};

function _update_faded_messages() {
    // See also update_faded_messages(), which just wraps this with a debounce.
    if (focused_recipient === undefined) {
        return;
    }

    if ((focused_recipient.type === "stream" && focused_recipient.subject === "") ||
        (focused_recipient.type === "private" && focused_recipient.reply_to === "")) {
        exports.unfade_messages();
        return;
    }

    var i;
    var all_elts = rows.get_table(current_msg_list.table_name).find(".recipient_row, .message_row");
    var should_fade_message = false;
    // Note: The below algorithm relies on the fact that all_elts is
    // sorted as it would be displayed in the message view
    for (i = 0; i < all_elts.length; i++) {
        var elt = $(all_elts[i]);
        if (elt.hasClass("recipient_row")) {
            should_fade_message = !util.same_recipient(focused_recipient, current_msg_list.get(rows.id(elt)));
        }

        // Usually we are not actually switching up the classes here, so the hasClass()
        // calls here will usually short circuit two function calls that are more expensive.
        // So, while the hasClass() checks are semantically unnecessary, they should improve
        // performance.  See trac #1633 for more context.
        if (should_fade_message) {
            if (!elt.hasClass("faded")) {
                elt.removeClass("unfaded").addClass("faded");
            }
            any_messages_faded = true;
        } else {
            if (!elt.hasClass("unfaded")) {
                elt.removeClass("faded").addClass("unfaded");
            }
        }
    }

    ui.update_floating_recipient_bar();
}

// See trac #1633.  For fast typists, calls to _update_faded_messages can
// cause typing sluggishness.
exports.update_faded_messages = _.debounce(_update_faded_messages, 150);

return exports;

}());
