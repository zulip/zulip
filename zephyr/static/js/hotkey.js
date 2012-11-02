var hotkeys = (function () {

var exports = {};

var pressed_keys = {};

function num_pressed_keys() {
    var size = 0, key;
    $.each(pressed_keys, function () {
        size++;
    });
    return size;
}

var directional_hotkeys = {
    40:  rows.next_visible,  // down arrow
    106: rows.next_visible,  // 'j'
    38:  rows.prev_visible,  // up arrow
    107: rows.prev_visible,  // 'k'
    36:  rows.first_visible, // Home
    35:  rows.last_visible   // End
};

var narrow_hotkeys = {
    115: narrow.by_recipient,  // 's'
    83:  narrow.by_subject,    // 'S'
    118: narrow.all_huddles    // 'v'
};

// These are not exported, but they need to be used before they are
// defined, since we have a cycle in function reference.  So we
// declare them ahead of time to make JSLint happy.
var process_key_in_input, process_compose_hotkey;

function simulate_keydown(keycode) {
    $(document).trigger($.Event('keydown', {keyCode: keycode}));
}

function process_hotkey(code) {
    var next_message;

    // Disable hotkeys on settings page etc.
    if (!$('#home').hasClass('active')) {
        return false;
    }

    // Disable hotkeys when in an input, textarea, or send button
    if ($('input:focus,textarea:focus,#compose-send-button:focus').length > 0) {
        return process_key_in_input(code);
    }

    if (directional_hotkeys.hasOwnProperty(code)) {
        next_message = directional_hotkeys[code](selected_message);
        if (next_message.length !== 0) {
            select_message(next_message, {then_scroll: true});
        }
        if ((next_message.length === 0) && (code === 40 || code === 106)) {
            // At the last message, scroll to the bottom so we have
            // lots of nice whitespace for new messages coming in.
            //
            // FIXME: this doesn't work for End because rows.last_visible()
            // always returns a message.
            viewport.scrollTop($("#main_div").outerHeight(true));
        }
        return process_hotkey;
    }

    if (narrow_hotkeys.hasOwnProperty(code)) {
        narrow.target(selected_message_id);
        narrow_hotkeys[code]();
        return process_hotkey;
    }

    if (num_pressed_keys() > 1 &&
            // "shift"             "caps lock"
            !((pressed_keys[16] || pressed_keys[20]) &&
                num_pressed_keys() === 2)) {
        // If you are already holding down another key, none of these
        // actions apply. However, if you are holding down exactly one
        // other key and that key is shift or caps lock, we still want
        // to continue processing.
        return false;
    }

    switch (code) {
    case 33: // Page Up
        if (at_top_of_viewport()) {
            select_message(rows.first_visible(), {then_scroll: false});
        }
        return false; // We want the browser to actually page up and down
    case 32: // Spacebar
    case 34: // Page Down
        if (at_bottom_of_viewport()) {
            select_message(rows.last_visible(), {then_scroll: false});
        }
        return false;
    case 27: // Esc: close userinfo popup, cancel compose, or un-narrow
        if (userinfo_currently_popped !== undefined) {
            userinfo_currently_popped.popover("destroy");
            userinfo_currently_popped = undefined;
        } else if (compose.composing()) {
            compose.cancel();
        } else {
            narrow.show_all_messages();
        }
        return process_hotkey;
    case 99: // 'c': compose
        compose.start('stream');
        return process_compose_hotkey;
    case 67: // 'C': compose huddle
        compose.start('personal');
        return process_compose_hotkey;
    case 114: // 'r': respond to message
        respond_to_message();
        return process_hotkey;
    case 82: // 'R': respond to author
        respond_to_message("personal");
        return process_hotkey;
    case 47: // '/': initiate search
        initiate_search();
        return process_hotkey;
    case 63: // '?': Show keyboard shortcuts page
        $('#keyboard-shortcuts').modal('show');
        return process_hotkey;
    }

    return false;
}

/* The current handler function for keydown events.
   It should return a new handler, or 'false' to
   decline to handle the event. */
var current_key_handler = process_hotkey;

process_key_in_input = function (code) {
    if (code === 27) {
        // If the user hit the escape key, cancel the current compose
        compose.cancel();
    }
    // Keycode 13 is Return.
    if ((code === 13) && $("#search").is(":focus")) {
        // Pass it along to the search up button.
        $("#search_up").focus();
    }
    // Let the browser handle the key normally.
    return false;
};

process_compose_hotkey = function (code) {
    if (code === 9) { // Tab: toggles between stream and huddle compose tabs.
        compose.toggle_mode();
        return process_compose_hotkey;
    }
    // Process the first non-tab character and everything after it
    // like any other keys typed in the input box
    current_key_handler = process_hotkey;
    return process_hotkey(code);
};

exports.set_compose = function () {
    current_key_handler = process_compose_hotkey;
};

$(document).keydown(function (e) {
    pressed_keys[e.which] = true;
    if ((num_pressed_keys() >= 2) &&
        (48 <= e.which && e.which <= 90) &&
        (pressed_keys[17] === true ||
         pressed_keys[91] === true)) {
        // If the user typed 2 or more characters, one of which was
        // ctrl(17) or command(91), and ending with an alphanumeric
        // character (between 48 and 90), this is probably a browser
        // keyboard shortcut (example: ctrl-f in Chrome).  Browsers
        // will often not trigger a keyup event after processing those
        // shortcuts and we don't have any hotkeys using these
        // characters, so just ignore such key presses for our
        // accounting.
        pressed_keys = {};
    }
});

$(document).keyup(function (e) {
    pressed_keys = {};
});

/* We register both a keydown and a keypress function because
   we want to intercept pgup/pgdn, escape, etc, and process them
   as they happen on the keyboard. However, if we processed
   letters/numbers in keydown, we wouldn't know what the case of
   the letters were.

   We want case-sensitive hotkeys (such as in the case of r vs R)
   so we bail in .keydown if the event is a letter or number and
   instead just let keypress go for it. */

function down_or_press(event) {
    var result = current_key_handler(event.which);
    if (result) {
        current_key_handler = result;
        event.preventDefault();
    }
}

$(document).keydown(function (event) {
    // Restrict to non-alphanumeric keys
    if (48 > event.which || 90 < event.which)
        down_or_press(event);
});

$(document).keypress(function (event) {
    // What exactly triggers .keypress may vary by browser.
    // Welcome to compatability hell.
    //
    // In particular, when you press tab in Firefox, it fires a
    // keypress event with keycode 0 after processing the original
    // event.
    if (event.which !== 0 && event.charCode !== 0)
        down_or_press(event);
});

return exports;

}());
