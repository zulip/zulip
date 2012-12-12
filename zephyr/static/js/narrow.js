var narrow = (function () {

var exports = {};

// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// For narrowing based on a particular message
var target_id = 0;

var filter_function = false;

exports.active = function () {
    // Cast to bool
    return !!filter_function;
};

exports.predicate = function () {
    if (filter_function) {
        return filter_function;
    } else {
        return function () { return true; };
    }
};

var show_floating_recipient;
var allow_collapse;

exports.show_floating_recipient = function () {
    return (!filter_function) || show_floating_recipient;
};

exports.allow_collapse = function () {
    return (!filter_function) || allow_collapse;
};

/* Convert a list of operators to a string.
   Each operator is a key-value pair like

       ['subject', 'my amazing subject']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type. */
function unparse(operators) {
    var parts = [];
    $.each(operators, function (index, elem) {
        var operator = elem[0];
        if (operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            parts.push(elem[1]);
        } else {
            // FIXME: URI encoding will look really ugly
            parts.push(elem[0] + ':' + encodeURIComponent(elem[1]));
        }
    });
    return parts.join(' ');
}

// Build a filter function from a list of operators.
function build_filter(operators) {
    // FIXME: This is probably pretty slow.
    // We could turn it into something more like a compiler:
    // build JavaScript code in a string and then eval() it.

    return function (message) {
        var operand, i;
        for (i=0; i<operators.length; i++) {
            operand = operators[i][1];
            switch (operators[i][0]) {
            case 'is':
                if ((operand === 'private-message') || (operand === 'pm')) {
                    if (message.type !== 'private')
                        return false;
                }
                break;

            case 'stream':
                if ((message.type !== 'stream') ||
                    (message.display_recipient !== operand))
                    return false;
                break;

            case 'subject':
                if ((message.type !== 'stream') ||
                    (message.subject.toLowerCase() !== operand))
                    return false;
                break;

            case 'pm-with':
                if ((message.type !== 'private') ||
                    (message.reply_to !== operand))
                    return false;
                break;

            case 'search':
                if (message.content.toLowerCase().indexOf(operand) === -1) {
                    if ((message.type !== 'stream') ||
                        (message.subject.toLowerCase().indexOf(operand) === -1)) {
                        return false;
                    }
                }
                break;
            }
        }

        // All filters passed.
        return true;
    };
}

exports.activate = function (operators, opts) {
    opts = $.extend({}, {
        time_travel:             false,
        show_floating_recipient: true,
        allow_collapse:          true
    }, opts);

    var was_narrowed = exports.active();

    filter_function = build_filter(operators);

    show_floating_recipient = opts.show_floating_recipient;
    allow_collapse          = opts.allow_collapse;

    // Your pointer isn't changed when narrowed.
    if (! was_narrowed) {
        persistent_message_id = selected_message_id;
    }

    // Before we clear the table, check if anything was highlighted.
    var highlighted = search.something_is_highlighted();

    // Empty the filtered table right before we fill it again
    if (opts.time_travel) {
        load_old_messages(target_id, 200, 200, function (messages) {
            // We do this work inside the load_old_messages
            // continuation, to shorten the window with just 1 visible message
            clear_table('zfilt');
            add_to_table([message_dict[target_id]], 'zfilt', filter_function, 'bottom', allow_collapse);
            // Select target_id so that we will correctly arrange messages
            // surrounding the target message.
            select_message_by_id(target_id, {then_scroll: false});
            add_messages(messages, false);
        }, true, true);
    } else {
        clear_table('zfilt');
        add_to_table(message_array, 'zfilt', filter_function, 'bottom', allow_collapse);
    }

    // Show the new set of messages.
    $("#zfilt").addClass("focused_table");

    reset_load_more_status();
    $("#show_all_messages").removeAttr("disabled");
    $("#main_div").addClass("narrowed_view");
    $("#searchbox").addClass("narrowed_view");

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

    // Put the narrow operators in the URL fragment and search bar
    hashchange.save_narrow(operators);
    $('#search_query').val(unparse(operators));
};

exports.time_travel = function () {
    exports.activate([], {time_travel: true});
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
    exports.activate([['is', 'private-message']]);
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
    var operators = [
        ['stream',  stream],
        ['subject', subject.toLowerCase()]];
    exports.activate(operators, {show_floating_recipient: false});
};

exports.by_stream_name = function (name) {
    exports.activate([['stream', name]]);
};

exports.by_private_message_group = function (names, emails) {
    exports.activate([['pm-with', emails]], {show_floating_recipient: false});
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    var new_narrow, emails;
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
    exports.activate([['search', term.toLowerCase()]], {allow_collapse: false});
    load_more_messages();
};

exports.show_all_messages = function () {
    if (!filter_function) {
        return;
    }
    filter_function = false;

    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    reset_load_more_status();
    $("#main_div").removeClass('narrowed_view');
    $("#searchbox").removeClass('narrowed_view');
    $("#show_all_messages").attr("disabled", "disabled");
    $('#search_query').val('');
    // Includes scrolling.
    select_message_by_id(persistent_message_id, {then_scroll: true});

    search.update_highlight_on_narrow();

    hashchange.save_narrow();

    scroll_to_selected();
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
