var directional_hotkeys = {
    40: get_next_visible,  // down arrow
    38: get_prev_visible,  // up arrow
    36: get_first_visible, // Home
    35: get_last_visible   // End
};

function process_hotkey(code) {
    var next_zephyr;
    if (code in directional_hotkeys) {
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

    switch (code) {
    case 27: // Esc: hide compose pane
        hide_compose();
        return process_hotkey;

    case 82: // 'r': respond to zephyr
        respond_to_zephyr();
        return process_key_in_input;

    case 71: // 'g': start of "go to" command
        return process_goto_hotkey;
    }

    return false;
}

function process_goto_hotkey(code) {
    switch (code) {
    case 67: // 'c': narrow by recipient
        narrow_by_recipient();
        break;

    case 73: // 'i': narrow by instance
        narrow_instance();
        break;

    case 80: // 'p': narrow to personals
        narrow_all_personals();
        break;

    case 65: // 'a': un-narrow
        show_all_messages();
        break;

    case 27: // Esc: hide compose pane
        hide_compose();
        break;
    }

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

/* The current handler function for keydown events.
   It should return a new handler, or 'false' to
   decline to handle the event. */
var keydown_handler = process_hotkey;

$(document).keydown(function (event) {
    var result = keydown_handler(event.keyCode);
    if (typeof result === 'function') {
        keydown_handler = result;
        event.preventDefault();
    }
});
