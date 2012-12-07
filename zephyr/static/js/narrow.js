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

exports.allow_collapse = function () {
    if (narrowdata && narrowdata.allow_collapse !== undefined) {
        return narrowdata.allow_collapse;
    } else {
        return true;
    }
};

exports.data = function () {
    return narrowdata;
};

exports.hashchanged = function (hash) {
    var full_names, decoded, emails;

    if (hash[1] === "all_private_messages") {
        exports.all_private_messages();
    }
    else if (hash[1] === "stream" && hash[3] === "subject") {
        exports.by_stream_and_subject_names(decodeURIComponent(hash[2]),
                                            decodeURIComponent(hash[4]));
    }
    else if (hash[1] === "stream") {
        exports.by_stream_name(decodeURIComponent(hash[2]));
    }
    else if (hash[1] === "private_messages") {
        decoded = decodeURIComponent(hash[2]);
        emails = decoded.split(", ");

        $.each(emails, function (index, email) {
            $.each(people_list, function (index, person) {
                if (person.email === email) {
                    if (full_names === undefined) {
                        full_names = person.full_name;
                    }
                    else {
                        full_names += ", " + person.full_name;
                    }
                    return false;
                }
            });
        });
        exports.by_private_message_group(full_names, decoded);
    }
};

function do_narrow(new_narrow, bar, time_travel, new_filter) {
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
    if (time_travel) {
        load_old_messages(target_id, 200, 200, function (messages) {
            // We do this work inside the load_old_messages
            // continuation, to shorten the window with just 1 visible message
            clear_table('zfilt');
            add_to_table([message_dict[target_id]], 'zfilt', filter_function, 'bottom', exports.allow_collapse());
            // Select target_id so that we will correctly arrange messages
            // surrounding the target message.
            select_message_by_id(target_id, {then_scroll: false});
            add_messages(messages, false);
        }, true, true);
    } else {
        clear_table('zfilt');
        add_to_table(message_array, 'zfilt', filter_function, 'bottom', exports.allow_collapse());
    }

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    reset_load_more_status();
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
                         {then_scroll: false, for_narrow: false});
    select_message_by_id(target_id, {then_scroll: true});

    // If anything was highlighted before, try to rehighlight it.
    if (highlighted) {
        search.update_highlight_on_narrow();
    }
}

exports.time_travel = function () {
    var bar = {
        icon:        'time',
        description: 'Messages around time ' + message_dict[target_id].full_date_str
    };
    do_narrow({}, bar, true, function (other) {
        return true;
    });
};

// This is the message we're about to select, within the narrowed view.
// But it won't necessarily be selected once the user un-narrows.
//
// FIXME: We probably don't need this variable, selected_message_id, *and*
// persistent_message_id.
exports.target = function (id) {
    target_id = id;
};

exports.all_private_messages = function () {
    hashchange.changehash("#narrow/all_private_messages");

    var new_narrow = {type: "all_private_messages"};
    var bar = {icon: 'user', description: 'You and anyone else'};
    do_narrow(new_narrow, bar, false, function (other) {
        return other.type === "private";
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
    exports.by_stream_and_subject_names(original.display_recipient,
                                        original.subject);
};

exports.by_stream_and_subject_names = function (stream, subject) {
    hashchange.changehash("#narrow/stream/" +
                          encodeURIComponent(stream) +
                          "/subject/" +
                          encodeURIComponent(subject));

    var new_narrow = {type: "subject", stream: stream, subject: subject};
    var bar = {
        icon:           'bullhorn',
        description:    stream,
        subject:        subject
    };
    do_narrow(new_narrow, bar, false, function (other) {
        return ((other.type === 'stream') &&
                (other.display_recipient === stream &&
                 other.subject.toLowerCase() === subject.toLowerCase()));
    });
};

exports.by_stream_name = function (name) {
    hashchange.changehash("#narrow/stream/" +
                          encodeURIComponent(name));

    var new_narrow = {type: "stream", stream: name};
    var bar = {icon: 'bullhorn', description: name};
    do_narrow(new_narrow, bar, false, function (other) {
        return (other.type === 'stream' &&
                name === other.display_recipient);
    });
};

exports.by_private_message_group = function (names, emails) {
    hashchange.changehash("#narrow/private_messages/" +
                          encodeURIComponent(emails));

    var new_narrow = {type: "private", emails: emails.split(", ")};
    var bar = {icon: 'user', description: "You and " + names};
    var my_email = email;
    do_narrow(new_narrow, bar, false, function (other) {
        return (other.type === 'private' &&
                other.reply_to === emails);
    });
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    var bar, new_narrow, emails;
    switch (message.type) {
    case 'private':
        exports.by_private_message_group(message.display_reply_to,
                                         message.reply_to);
        break;

    case 'stream':
        exports.by_stream_name(message.display_recipient);
        break;
    }
};

exports.by_search_term = function (term) {
    hashchange.changehash("#narrow/searchterm/" + encodeURIComponent(term));

    var new_narrow = {type: "searchterm", searchterm: term, allow_collapse: false};
    var bar = {icon: 'search', description: 'Messages containing "' + term + '"'};
    var term_lowercase = term.toLowerCase();
    do_narrow(new_narrow, bar, false, function (other) {
        return other.subject.toLowerCase().indexOf(term_lowercase) !== -1 ||
               other.content.toLowerCase().indexOf(term_lowercase) !== -1;
    });
    load_more_messages();
};

exports.show_all_messages = function () {
    hashchange.changehash("");

    if (!narrowdata) {
        return;
    }
    narrowdata = false;
    filter_function = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $(".narrowed_to_bar").hide();
    reset_load_more_status();
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
