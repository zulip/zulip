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

    var message = original.display_recipient + " | " + original.subject;
    do_narrow(message, function (other) {
        return (other.type === 'stream' &&
                original.recipient_id === other.recipient_id &&
                original.subject === other.subject);
    });
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var original, message;
    switch (message_dict[selected_message_id].type) {
    case 'personal':
        // Narrow to personals with a specific user
        original = message_dict[target_id];

        do_narrow("Huddles with " + original.display_replay_to, function (other) {
            return (other.type === 'personal') &&
                (((other.display_recipient.email === original.display_recipient.email)
                    && (other.sender_email === original.sender_email)) ||
                 ((other.display_recipient.email === original.sender_email)
                    && (other.sender_email === original.display_recipient.email)));
        });
        break;

    case 'huddle':
        original = message_dict[target_id];
        do_narrow("Huddles with " + original.display_reply_to, function (other) {
            return (other.type === "personal" || other.type === "huddle")
                && other.reply_to === original.reply_to;
        });
        break;

    case 'stream':
        original = message_dict[target_id];
        message = original.display_recipient;
        do_narrow(message, function (other) {
            return (other.type === 'stream' &&
                    original.recipient_id === other.recipient_id);
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
