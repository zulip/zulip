// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// Narrowing predicate, or 'false' for the home view.
var narrowed = false;

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
    $(".narrowcontent").show();
    $("#main_div").addClass("narrowed_view");
    $("#currently_narrowed_to").html(description).attr("title", description);
    $("#zhome").removeClass("focused_table");

    select_and_show_by_id(selected_message_id);
    scroll_to_selected();
}

function narrow_huddle() {
    var original = message_dict[selected_message_id];
    do_narrow("Huddles with " + original.reply_to, function (other) {
        return other.reply_to === original.reply_to;
    });
}

function narrow_all_personals() {
    do_narrow("All huddles with you", function (other) {
        return other.type === "personal" || other.type === "huddle";
    });
}

function narrow_personals() {
    // Narrow to personals with a specific user
    var original = message_dict[selected_message_id];
    var other_party;
    if (original.display_recipient.email === email) {
        other_party = original.sender_email;
    } else {
        other_party = original.display_recipient.email;
    }

    do_narrow("Huddles with " + other_party, function (other) {
        return (other.type === 'personal') &&
            (((other.display_recipient.email === original.display_recipient.email) && (other.sender_email === original.sender_email)) ||
             ((other.display_recipient.email === original.sender_email) && (other.sender_email === original.display_recipient.email)));
    });

}

function narrow_stream() {
    var original = message_dict[selected_message_id];
    var message = original.display_recipient;
    do_narrow(message, function (other) {
        return (other.type === 'stream' &&
                original.recipient_id === other.recipient_id);
    });
}

function narrow_subject() {
    var original = message_dict[selected_message_id];
    if (original.type !== 'stream')
        return;

    var message = original.display_recipient + " | " + original.subject;
    do_narrow(message, function (other) {
        return (other.type === 'stream' &&
                original.recipient_id === other.recipient_id &&
                original.subject === other.subject);
    });
}

// Called for the 'narrow by stream' hotkey.
function narrow_by_recipient() {
    switch (message_dict[selected_message_id].type) {
        case 'personal': narrow_personals(); break;
        case 'huddle':   narrow_huddle();    break;
        case 'stream':    narrow_stream();     break;
    }
}

function show_all_messages() {
    if (!narrowed) {
        return;
    }
    narrowed = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $(".narrowcontent").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");

    // Includes scrolling.
    select_and_show_by_id(persistent_message_id);

    scroll_to_selected();
}
