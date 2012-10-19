var narrow = (function () {

var exports = {};

// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// For narrowing based on a particular message
var target_id = 0;

// Narrowing predicate, or 'false' for the home view.
var narrowed = false;

exports.active = function () {
    // Cast to bool
    return !!narrowed;
};

exports.predicate = function () {
    if (narrowed) {
        return narrowed;
    } else {
        return function () { return true; };
    }
};

function do_narrow(description, filter_function) {
    narrowed = filter_function;

    // Your pointer isn't changed when narrowed.
    persistent_message_id = selected_message_id;

    // Empty the filtered table right before we fill it again
    clear_table('zfilt');
    add_to_table(message_array, 'zfilt', filter_function, 'bottom');

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    $("#show_all_messages").removeAttr("disabled");
    $(".narrowed_to_bar").show();
    $("#main_div").addClass("narrowed_view");
    $("#currently_narrowed_to").html(description).attr("title", description);
    $("#zhome").removeClass("focused_table");

    // Indicate both which message is persistently selected and which
    // is temporarily selected
    select_and_show_by_id(selected_message_id);
    selected_message_class = "narrowed_selected_message";
    select_and_show_by_id(target_id);
    scroll_to_selected();
}

// This is the message we're about to select, within the narrowed view.
// But it won't necessarily be selected once the user un-narrows.
//
// FIXME: We probably don't need this variable, selected_message_id, *and*
// persistent_message_id.
exports.target = function (id) {
    target_id = id;
};

exports.all_personals = function () {
    do_narrow("All huddles with you", function (other) {
        return other.type === "personal" || other.type === "huddle";
    });
};

exports.by_subject = function () {
    var original = message_dict[target_id];
    if (original.type !== 'stream')
        return;

    var message = "<i class='icon-bullhorn'></i> " + original.display_recipient + " | " + original.subject;
    do_narrow(message, function (other) {
        return (other.type === 'stream' &&
                original.recipient_id === other.recipient_id &&
                original.subject === other.subject);
    });
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    switch (message.type) {
    case 'personal':
        // Narrow to personals with a specific user
        do_narrow("<i class='icon-user'></i> " + message.display_reply_to, function (other) {
            return (other.type === 'personal') &&
                (((other.display_recipient.email === message.display_recipient.email)
                    && (other.sender_email === message.sender_email)) ||
                 ((other.display_recipient.email === message.sender_email)
                    && (other.sender_email === message.display_recipient.email)));
        });
        break;

    case 'huddle':
        do_narrow("<i class='icon-user'></i> " + message.display_reply_to, function (other) {
            return (other.type === "personal" || other.type === "huddle")
                && other.reply_to === message.reply_to;
        });
        break;

    case 'stream':
        do_narrow("<i class='icon-bullhorn'></i> " + message.display_recipient, function (other) {
            return (other.type === 'stream' &&
                    message.recipient_id === other.recipient_id);
        });
        break;
    }
};

exports.show_all_messages = function () {
    if (!narrowed) {
        return;
    }
    narrowed = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $(".narrowed_to_bar").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");

    selected_message_class = "selected_message";
    // Includes scrolling.
    select_and_show_by_id(persistent_message_id);

    scroll_to_selected();
};

return exports;

}());
