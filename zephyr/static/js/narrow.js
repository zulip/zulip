var narrow = (function () {

var exports = {};

// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// For narrowing based on a particular message
var target_id = 0;

// Narrowing predicate, or 'false' for the home view.
var narrowed = false;

// What sort of narrowing is currently active
var narrow_type = '';

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

exports.narrowing_type = function () {
    return narrow_type;
};

function do_narrow(bar, filter_function) {
    var was_narrowed = exports.active();

    narrowed = filter_function;

    // Your pointer isn't changed when narrowed.
    if (! was_narrowed) {
        persistent_message_id = selected_message_id;
    }

    // Before we clear the table, check if anything was highlighted.
    var highlighted = search.something_is_highlighted();

    // Empty the filtered table right before we fill it again
    clear_table('zfilt');
    add_to_table(message_array, 'zfilt', filter_function, 'bottom');

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    $("#show_all_messages").removeAttr("disabled");
    $(".narrowed_to_bar").show();
    $("#loading_control").hide();
    $("#top_narrowed_whitespace").show();
    $("#main_div").addClass("narrowed_view");
    $("#searchbox").addClass("narrowed_view");
    $("#currently_narrowed_to").remove();
    $("#narrowlabel").append(templates.narrowbar(bar));

    $("#zhome").removeClass("focused_table");
    // Indicate both which message is persistently selected and which
    // is temporarily selected
    select_message_by_id(persistent_message_id,
                         {then_scroll: false, update_server: false,
                          for_narrow: false});
    select_message_by_id(target_id,
                         {then_scroll: true, update_server: false});

    // If anything was highlighted before, try to rehighlight it.
    if (highlighted) {
        search.update_highlight_on_narrow();
    }
}

// This is the message we're about to select, within the narrowed view.
// But it won't necessarily be selected once the user un-narrows.
//
// FIXME: We probably don't need this variable, selected_message_id, *and*
// persistent_message_id.
exports.target = function (id) {
    target_id = id;
};

exports.all_huddles = function () {
    narrow_type = "all_huddles";
    do_narrow({icon: 'user', description: 'You and anyone else'}, function (other) {
        return other.type === "personal" || other.type === "huddle";
    });
};

exports.by_subject = function () {
    var original = message_dict[target_id];
    if (original.type !== 'stream') {
        // Only stream messages have subjects, but the
        // user wants us to narrow in some way.
        exports.by_recipient();
        return;
    }

    narrow_type = "subject";
    var bar = {
        icon:        'bullhorn',
        description: original.display_recipient,
        subject:     original.subject
    };
    do_narrow(bar, function (other) {
        return ((other.type === 'stream') &&
                same_stream_and_subject(original, other));
    });
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    var bar;
    switch (message.type) {
    case 'personal':
        // Narrow to personals with a specific user
        narrow_type = "huddle";
        bar = {icon: 'user', description: "You and " + message.display_reply_to};
        do_narrow(bar, function (other) {
            return (other.type === 'personal') &&
                (((other.display_recipient.email === message.display_recipient.email)
                    && (other.sender_email === message.sender_email)) ||
                 ((other.display_recipient.email === message.sender_email)
                    && (other.sender_email === message.display_recipient.email)));
        });
        break;

    case 'huddle':
        narrow_type = "huddle";
        bar = {icon: 'user', description: "You and " + message.display_reply_to};
        do_narrow(bar, function (other) {
            return (other.type === "personal" || other.type === "huddle")
                && other.reply_to === message.reply_to;
        });
        break;

    case 'stream':
        narrow_type = "stream";
        bar = {icon: 'bullhorn', description: message.display_recipient};
        do_narrow(bar, function (other) {
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
    narrow_type = "";

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $(".narrowed_to_bar").hide();
    $("#loading_control").show();
    $("#top_narrowed_whitespace").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#searchbox").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").empty();
    // Includes scrolling.
    select_message_by_id(persistent_message_id, {then_scroll: true});

    scroll_to_selected();

    search.update_highlight_on_narrow();
};

exports.restore_home_state = function() {
    // If we click on the Home link while already at Home, unnarrow.
    // If we click on the Home link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the Home pane.
    if ($('#sidebar li[title="Home"]').hasClass("active")) {
        exports.show_all_messages();
    }
};

return exports;

}());
