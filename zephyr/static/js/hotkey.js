/*global
    process_goto_hotkey:    false,
    process_compose_hotkey: false,
    process_key_in_input:   false */

// We don't generally treat these as global.
// Tell JSLint they are, to break the mutual recursion.


var pressed_keys = {};

function num_pressed_keys() {
    var size = 0, key;
    for (key in pressed_keys) {
        if (pressed_keys.hasOwnProperty(key))
            size++;
    }
    return size;
}

var directional_hotkeys = {
    40: get_next_visible,  // down arrow
    106: get_next_visible,  // 'j'
    38: get_prev_visible,  // up arrow
    107: get_prev_visible,  // 'k'
    36: get_first_visible, // Home
    35: get_last_visible   // End
};

function simulate_keydown(keycode) {
    $(document).trigger($.Event('keydown', {keyCode: keycode}));
}

function process_hotkey(code) {
    var next_zephyr;
    if (directional_hotkeys.hasOwnProperty(code)) {
        next_zephyr = directional_hotkeys[code](selected_zephyr);
        if (next_zephyr.length !== 0) {
            select_zephyr(next_zephyr, true);
        }
        if ((next_zephyr.length === 0) && (code === 40 || code === 106)) {
            // At the last zephyr, scroll to the bottom so we have
            // lots of nice whitespace for new zephyrs coming in.
            //
            // FIXME: this doesn't work for End because get_last_visible()
            // always returns a zephyr.
            var viewport = $(window);
            viewport.scrollTop($("#main_div").outerHeight(true));
        }
        return process_hotkey;
    }

    if (num_pressed_keys() > 1 &&
            // "shift"                        "caps lock"
            !((pressed_keys[16] === true || pressed_keys[20]) &&
                num_pressed_keys() === 2)) {
        // If you are already holding down another key, none of these
        // actions apply.
        return false;
    }

    switch (code) {
    case 33: // Page Up
        keep_pointer_in_view();
        if (at_top_of_viewport()) {
            select_zephyr(get_first_visible(), false);
        }
        return false; // We want the browser to actually page up and down
    case 34: // Page Down
        keep_pointer_in_view();
        if (at_bottom_of_viewport()) {
            select_zephyr(get_last_visible(), false);
        }
        return false;
    case 27: // Esc: hide compose pane
        hide_compose();
        return process_hotkey;
    case 99: // 'c': compose
        compose_button();
        return process_compose_hotkey;
    case 114: // 'r': respond to zephyr
        respond_to_zephyr();
        return process_key_in_input;
    case 82: // 'R': respond to author
        respond_to_zephyr("personal");
        return process_key_in_input;
    case 103: // 'g': start of "go to" command
        return process_goto_hotkey;
    }

    return false;
}

var goto_hotkeys = {
    99: narrow_by_recipient,  // 'c'
    105: narrow_instance,      // 'i'
    112: narrow_all_personals, // 'p'
    97: show_all_messages,    // 'a'
    27: hide_compose          // Esc
};

function process_goto_hotkey(code) {
    if (goto_hotkeys.hasOwnProperty(code))
        goto_hotkeys[code]();

    /* Always return to the initial hotkey mode, even
       with an unrecognized "go to" command. */
    return process_hotkey;
}

function process_key_in_input(code) {
    if (code === 27) {
        // User hit Escape key
        hide_compose();
        return process_hotkey;
    }
    return false;
}

function process_compose_hotkey(code) {
    if (code === 9) { // Tab: toggle between class and huddle compose tabs.
        toggle_compose();
        return process_compose_hotkey;
    } else {
        set_keydown_in_input(true);
        simulate_keydown(code);
    }
}

$(document).keydown(function (e) {
    pressed_keys[e.which] = true;
});

$(document).keyup(function (e) {
    pressed_keys = {};
});

/* The current handler function for keydown events.
   It should return a new handler, or 'false' to
   decline to handle the event. */
var keydown_handler = process_hotkey;

function set_keydown_in_input(flag) {
    // No argument should behave like 'true'.
    if (flag === undefined)
        flag = true;

    if (flag) {
        keydown_handler = process_key_in_input;
    } else {
        keydown_handler = process_hotkey;
    }
}

/* We register both a keydown and a keypress function because
   we want to intercept pgup/pgdn, escape, etc, and process them
   as they happen on the keyboard. However, if we processed
   letters/numbers in keydown, we wouldn't know what the case of
   the letters were.

   We want case-sensitive hotkeys (such as in the case of r vs R)
   so we bail in .keydown if the event is a letter or number and
   instead just let keypress go for it. */

$(document).keydown(function (event) {
    if (48 > event.which ||90 < event.which) { // outside the alphanumeric range
        var result = keydown_handler(event.which);
        if (typeof result === 'function') {
            keydown_handler = result;
            event.preventDefault();
        }
    }
});

$(document).keypress(function (event) {
    // What exactly triggers .keypress may vary by browser.
    // Welcome to compatability hell.

    var result = keydown_handler(event.which);
    if (typeof result === 'function') {
        keydown_handler = result;
        event.preventDefault();
    }
});
