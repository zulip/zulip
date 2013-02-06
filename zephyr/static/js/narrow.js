var narrow = (function () {

var exports = {};

// For tracking where you were before you narrowed.
var persistent_message_id = 0;

// For narrowing based on a particular message
var target_id = 0;

var filter_function   = false;
var current_operators = false;

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

exports.operators = function () {
    return current_operators;
};

/* Operators we should send to the server. */
exports.public_operators = function () {
    var safe_to_return;
    safe_to_return = [];
    $.each(current_operators, function (index, value) {
        // Currently just filter out the "in" keyword.
        if (value[0] !== "in") {
            safe_to_return.push(value);
        }
    });
    if (safe_to_return.length !== 0) {
        return safe_to_return;
    }
};

var allow_collapse;

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
            parts.push(elem[0] + ':' + encodeURIComponent(elem[1]).toLowerCase());
        }
    });
    return parts.join(' ');
}

// Convert a list of operators to a human-readable description.
exports.describe = function (operators) {
    return $.map(operators, function (elem) {
        var operand = elem[1];
        switch (elem[0]) {
        case 'is':
            if (operand === 'private-message')
                return 'private messages';
            break;

        case 'stream':
            return 'stream ' + operand;

        case 'subject':
            return 'subject ' + operand;

        case 'pm-with':
            return 'private messages with ' + operand;

        case 'search':
            return 'messages containing ' + operand;

        case 'in':
            return 'messages in ' + operand;
        }
        return '(unknown operator)';
    }).join(', ');
};

// Parse a string into a list of operators (see below).
exports.parse = function (str) {
    var operators   = [];
    var search_term = [];
    $.each(str.split(/ +/), function (idx, token) {
        var parts, operator;
        if (token.length === 0)
            return;
        parts = token.split(':');
        if (parts.length > 1) {
            // Looks like an operator.
            // FIXME: Should we skip unknown operator names here?
            operator = parts.shift();
            operators.push([operator, decodeURIComponent(parts.join(':'))]);
        } else {
            // Looks like a normal search term.
            search_term.push(token);
        }
    });
    // NB: Callers of 'parse' can assume that the 'search' operator is last.
    if (search_term.length > 0)
        operators.push(['search', search_term.join(' ')]);
    return operators;
};

exports.in_home = function (message) {
    return message.type === "private" || subs.have(message.display_recipient).in_home_view;
};

// Build a filter function from a list of operators.
function build_filter(operators_mixed_case) {
    var operators = [];
    // We don't use $.map because it flattens returned arrays.
    $.each(operators_mixed_case, function (idx, operator) {
        operators.push([operator[0], operator[1].toLowerCase()]);
    });

    // FIXME: This is probably pretty slow.
    // We could turn it into something more like a compiler:
    // build JavaScript code in a string and then eval() it.

    return function (message) {
        var operand, i;
        for (i=0; i<operators.length; i++) {
            operand = operators[i][1];
            switch (operators[i][0]) {
            case 'is':
                if (operand === 'private-message') {
                    if (message.type !== 'private')
                        return false;
                }
                break;

            case 'in':
                if (operand === 'home') {
                    return exports.in_home(message);
                }
                else if (operand === 'all') {
                    return true;
                }
                break;

            case 'stream':
                if ((message.type !== 'stream') ||
                    (message.display_recipient.toLowerCase() !== operand))
                    return false;
                break;

            case 'subject':
                if ((message.type !== 'stream') ||
                    (message.subject.toLowerCase() !== operand))
                    return false;
                break;

            case 'pm-with':
                if ((message.type !== 'private') ||
                    (message.reply_to.toLowerCase() !== operand))
                    return false;
                break;

            case 'search':
                var words = operand.trim().split(/\s+/);
                var j;
                for (j = 0; j < words.length; ++j) {
                    if (message.content.toLowerCase().indexOf(words[j]) === -1) {
                        if ((message.type !== 'stream') ||
                            (message.subject.toLowerCase().indexOf(words[j]) === -1)) {
                            return false;
                        }
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
        allow_collapse: true
    }, opts);

    var was_narrowed = exports.active();

    filter_function   = build_filter(operators);
    current_operators = operators;

    allow_collapse          = opts.allow_collapse;

    // Your pointer isn't changed when narrowed.
    if (! was_narrowed) {
        persistent_message_id = selected_message_id;
    }

    // Before we clear the table, check if anything was highlighted.
    var highlighted = search.something_is_highlighted();

    // If our message id is not in range of the loaded message list, we need to fetch the messages
    //  around the target message time
    if (message_array.length > 0 && (selected_message_id < message_array[0].id ||
                                     selected_message_id > message_array[message_array.length - 1])) {
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
    $("#main_div").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");
    $("#zfilt").css("opacity", 0).animate({opacity: 1});

    reset_load_more_status();
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
    search.update_button_visibility();

    $("ul.filters li").removeClass('active-filter');
    if (operators.length === 1) {
        if (operators[0][0] === "stream") {
            $("#stream_filters li[data-name='" + encodeURIComponent(operators[0][1]) + "']").addClass('active-filter');
        } else if (operators[0][0] === "is" && operators[0][1] === "private-message") {
            $("#filtpers").addClass('active-filter');
        }
    }
};

// Activate narrowing with a single operator.
// This is just for syntactic convenience.
exports.by = function (operator, operand, opts) {
    exports.activate([[operator, operand]], opts);
};

// This is the message we're about to select, within the narrowed view.
// But it won't necessarily be selected once the user un-narrows.
//
// FIXME: We probably don't need this variable, selected_message_id, *and*
// persistent_message_id.
exports.target = function (id) {
    target_id = id;
};

exports.by_subject = function () {
    var original = message_dict[target_id];
    if (original.type !== 'stream') {
        // Only stream messages have subjects, but the
        // user wants us to narrow in some way.
        exports.by_recipient();
        return;
    }
    exports.activate([
            ['stream',  original.display_recipient],
            ['subject', original.subject]
        ]);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function () {
    var message = message_dict[target_id];
    var new_narrow, emails;
    switch (message.type) {
    case 'private':
        exports.by('pm-with', message.reply_to);
        break;

    case 'stream':
        exports.by('stream', message.display_recipient);
        break;
    }
};

exports.deactivate = function () {
    if (!filter_function) {
        return;
    }
    filter_function   = false;
    current_operators = false;

    $("#main_div").removeClass('narrowed_view');
    $("#searchbox").removeClass('narrowed_view');
    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $("#zhome").css("opacity", 0).animate({opacity: 1});

    $('#search_query').val('');
    reset_load_more_status();
    // Includes scrolling.
    select_message_by_id(persistent_message_id, {then_scroll: true});

    search.update_highlight_on_narrow();

    hashchange.save_narrow();

    $("ul.filters li").removeClass('active-filter');
    $("#filthome").addClass('active-filter');

    scroll_to_selected();
};

exports.restore_home_state = function() {
    // If we click on the Home link while already at Home, unnarrow.
    // If we click on the Home link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the Home pane.
    if ($('#gear-menu li[title="Home"]').hasClass("active")) {
        exports.deactivate();
    }
};

return exports;

}());
