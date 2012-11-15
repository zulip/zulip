var narrow = (function () {

var exports = {};

// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// For narrowing based on a particular message
var target_id = 0;

var narrowdata = false;
var filter_function = false;

exports.active = function () {
    // Cast to bool
    return !!narrowdata;
};

exports.predicate = function () {
    if (filter_function) {
        return filter_function;
    } else {
        return function () { return true; };
    }
};

exports.narrowing_type = function () {
    if (narrowdata) {
        return narrowdata.type;
    } else {
        return '';
    }
};

exports.data = function () {
    return narrowdata;
};

function do_narrow(new_narrow, bar, new_filter) {
    var was_narrowed = exports.active();

    narrowdata = new_narrow;
    filter_function = new_filter;

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
    var new_narrow = {type: "all_huddles"};
    do_narrow(new_narrow, {icon: 'user', description: 'You and anyone else'}, function (other) {
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

    var new_narrow = {type: "subject", recipient_id: original.recipient_id,
                      subject: original.subject};
    var bar = {
        icon:        'bullhorn',
        description: original.display_recipient,
        subject:     original.subject
    };
    do_narrow(new_narrow, bar, function (other) {
        return ((other.type === 'stream') &&
                same_stream_and_subject(original, other));
    });
};

//TODO: There's probably some room to unify this code
//      with the hotkey-narrowing code below.
exports.by_stream_name = function (name) {
    var new_narrow = {type: "stream", stream: name};
    var bar = {icon: 'bullhorn', description: name};
    do_narrow(new_narrow, bar, function (other) {
        return (other.type === 'stream' &&
                name === other.display_recipient);
    });
};

exports.by_private_message_partner = function (their_name, their_email) {
    var new_narrow = {type: "huddle", one_on_one_email: their_email};
    var bar = {icon: 'user', description: "You and " + their_name};
    var my_email = email;
    do_narrow(new_narrow, bar, function (other) {
        return (other.type === 'personal') &&
            (((other.display_recipient.email === their_email)
              && (other.sender_email === my_email)) ||
             ((other.display_recipient.email === my_email)
              && (other.sender_email === their_email)));
    });
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    var bar;
    switch (message.type) {
    case 'personal':
        // Narrow to personals with a specific user
        var new_narrow = {type: "huddle", one_on_one_email: message.reply_to};
        bar = {icon: 'user', description: "You and " + message.display_reply_to};
        do_narrow(new_narrow, bar, function (other) {
            return (other.type === 'personal') &&
                (((other.display_recipient.email === message.display_recipient.email)
                    && (other.sender_email === message.sender_email)) ||
                 ((other.display_recipient.email === message.sender_email)
                    && (other.sender_email === message.display_recipient.email)));
        });
        break;

    case 'huddle':
        new_narrow = {type: "huddle", recipient_id: message.recipient_id};
        bar = {icon: 'user', description: "You and " + message.display_reply_to};
        do_narrow(new_narrow, bar, function (other) {
            return (other.type === "personal" || other.type === "huddle")
                && other.reply_to === message.reply_to;
        });
        break;

    case 'stream':
        new_narrow = {type: "stream", recipient_id: message.recipient_id};
        bar = {icon: 'bullhorn', description: message.display_recipient};
        do_narrow(new_narrow, bar, function (other) {
            return (other.type === 'stream' &&
                    message.recipient_id === other.recipient_id);
        });
        break;
    }
};

exports.show_all_messages = function () {
    if (!narrowdata) {
        return;
    }
    narrowdata = false;
    filter_function = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $(".narrowed_to_bar").hide();
    $("#load_more").show();
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
