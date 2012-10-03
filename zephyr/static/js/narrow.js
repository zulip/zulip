/*jslint browser: true, devel: true, sloppy: true,
    plusplus: true, white: true, undef: true */
/*global $: false */

// Narrowing predicate, or 'false' for the home view.
var narrowed = false;

function do_narrow(description, filter_function) {
    narrowed = filter_function;

    // Your pointer isn't changed when narrowed.
    persistent_zephyr_id = selected_zephyr_id;

    // We want the zephyr on which the narrow happened to stay in the same place if possible.
    var old_top = $("#main_div").offset().top - selected_zephyr.offset().top;
    var parent;

    // Empty the filtered table right before we fill it again
    clear_table('zfilt');
    add_to_table(zephyr_array, 'zfilt', filter_function, 'bottom');

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    $("#show_all_messages").removeAttr("disabled");
    $("#narrowbox").show();
    $("#main_div").addClass("narrowed_view");
    $("#currently_narrowed_to").html(description);
    $("#zhome").removeClass("focused_table");

    select_and_show_by_id(selected_zephyr_id);
    scroll_to_selected();
}

function narrow_huddle() {
    var original = zephyr_dict[selected_zephyr_id];
    do_narrow("Group chats with " + original.reply_to, function (other) {
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
    var original = zephyr_dict[selected_zephyr_id];
    var other_party;
    if (original.display_recipient === email) {
        other_party = original.sender_email;
    } else {
        other_party = original.display_recipient;
    }

    do_narrow("Huddles with " + other_party, function (other) {
        return (other.type === 'personal') &&
            (((other.display_recipient === original.display_recipient) && (other.sender_email === original.sender_email)) ||
             ((other.display_recipient === original.sender_email) && (other.sender_email === original.display_recipient)));
    });

}

function narrow_class() {
    var original = zephyr_dict[selected_zephyr_id];
    var message = original.display_recipient;
    do_narrow(message, function (other) {
        return (other.type === 'class' &&
                original.recipient_id === other.recipient_id);
    });
}

function narrow_instance() {
    var original = zephyr_dict[selected_zephyr_id];
    if (original.type !== 'class')
        return;

    var message = original.display_recipient + " | " + original.instance;
    do_narrow(message, function (other) {
        return (other.type === 'class' &&
                original.recipient_id === other.recipient_id &&
                original.instance === other.instance);
    });
}

// Called for the 'narrow by class' hotkey.
function narrow_by_recipient() {
    switch (zephyr_dict[selected_zephyr_id].type) {
        case 'personal': narrow_personals(); break;
        case 'huddle':   narrow_huddle();    break;
        case 'class':    narrow_class();     break;
    }
}

function show_all_messages() {
    if (!narrowed) {
        return;
    }
    narrowed = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $("#narrowbox").hide();
    $("#main_div").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $("#currently_narrowed_to").html("");

    // Includes scrolling.
    select_and_show_by_id(persistent_zephyr_id);

    scroll_to_selected();
}
