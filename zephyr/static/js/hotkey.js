var directional_hotkeys = {
    40: get_next_visible,  // down arrow
    38: get_prev_visible,  // up arrow
    36: get_first_visible, // Home
    35: get_last_visible   // End
};

function process_hotkey(code) {
    var next_zephyr, window_to_scroll;
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

    window_to_scroll = $(".active.scrolling_tab");
    if (window_to_scroll.length === 0) {
        window_to_scroll = $(".active").find(".scrolling-tab");
    }

    switch (code) {
    case 33: // Page Up
        window_to_scroll.scrollTop(window_to_scroll.scrollTop() - window_to_scroll.height());
        return process_hotkey;
    case 34: // Page Down
        window_to_scroll.scrollTop(window_to_scroll.scrollTop() + window_to_scroll.height());
        return process_hotkey;
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

var goto_hotkeys = {
    67: narrow_by_recipient,  // 'c'
    73: narrow_instance,      // 'i'
    80: narrow_all_personals, // 'p'
    65: show_all_messages,    // 'a'
    27: hide_compose          // Esc
};

function process_goto_hotkey(code) {
    if (code in goto_hotkeys)
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
