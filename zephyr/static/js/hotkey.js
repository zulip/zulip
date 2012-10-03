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
    74: get_next_visible,  // 'j'
    38: get_prev_visible,  // up arrow
    75: get_prev_visible,  // 'k'
    36: get_first_visible, // Home
    35: get_last_visible   // End
};

function simulate_keypress(keycode) {
    $(document).trigger($.Event('keydown', {keyCode: keycode}));
}

function process_hotkey(code) {
    var next_zephyr;
    if (directional_hotkeys.hasOwnProperty(code)) {
        next_zephyr = directional_hotkeys[code](selected_zephyr);
        if (next_zephyr.length !== 0) {
            select_zephyr(next_zephyr, true);
        }
        if ((next_zephyr.length === 0) && (code === 40)) {
            // At the last zephyr, scroll to the bottom so we have
            // lots of nice whitespace for new zephyrs coming in.
            //
            // FIXME: this doesn't work for End because get_last_visible()
            // always returns a zephyr.
            $("#main_div").scrollTop($("#main_div").prop("scrollHeight"));
        }
        return process_hotkey;
    }

    if (num_pressed_keys() > 1) {
        // If you are already holding down another key, none of these
        // actions apply.
        return false;
    }

    switch (code) {
    case 33: // Page Up
        keep_pointer_in_view();
        return false; // We want the browser to actually page up and down
    case 34: // Page Down
        keep_pointer_in_view();
        return false;
    case 27: // Esc: hide compose pane
        hide_compose();
        return process_hotkey;
    case 67: // 'c': compose
        compose_button();
        return process_compose_hotkey;
    case 82: // 'r': respond to zephyr
        respond_to_zephyr();
        return process_key_in_input;

    case 71: // 'g': start of "go to" command
        return process_goto_hotkey;
    }

    return false;
}

var goto_hotkeys = {
    67: narrow_by_recipient,  // 'c'
    73: narrow_instance,      // 'i'
    80: narrow_all_personals, // 'p'
    65: show_all_messages,    // 'a'
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
        simulate_keypress(code);
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

$(document).keydown(function (event) {
    var result = keydown_handler(event.keyCode);
    if (typeof result === 'function') {
        keydown_handler = result;
        event.preventDefault();
    }
});
