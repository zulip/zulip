var hotkeys = (function () {

var exports = {};

var directional_hotkeys = {
    40:  rows.next_visible,  // down arrow
    106: rows.next_visible,  // 'j'
    38:  rows.prev_visible,  // up arrow
    107: rows.prev_visible,  // 'k'
    36:  rows.first_visible, // Home
    35:  rows.last_visible   // End
};

var narrow_hotkeys = {
    115: narrow.by_recipient,           // 's'
    83:  narrow.by_subject,             // 'S'
    118: function () {                  // 'v'
        narrow.by('is', 'private-message');
    }
};

// Process a keydown or keypress event.
//
// Returns true if we handled it, false if the browser should.
function process_hotkey(e) {
    var code = e.which;
    var next_message;

    // Disable hotkeys on settings page etc., and when a modal pop-up
    // is visible.
    if (ui.home_tab_obscured())
        return false;

    // In browsers where backspace sends the browser back (e.g. Mac Chrome),
    // do not go back if the send button is in focus
    if ($('#compose-send-button:focus').length > 0 && code === 8) {
        e.preventDefault();
        return false;
    }

    // Process hotkeys specially when in an input, textarea, or send button
    if ($('input:focus,textarea:focus,#compose-send-button:focus').length > 0) {
        if (code === 27) {
            // If one of our typeaheads is open, do nothing so that the Esc
            // will go to close it
            if ($("#subject").data().typeahead.shown ||
                $("#stream").data().typeahead.shown ||
                $("#private_message_recipient").data().typeahead.shown ||
                $("#new_message_content").data().typeahead.shown) {
                return false;
            } else {
                // If the user hit the escape key, cancel the current compose
                compose.cancel();
            }
        }
        // Keycode 13 is Return.
        if ((code === 13) && $("#search_query").is(":focus")) {
            // Pass it along to the search up button.
            $("#search_up").focus();
        }
        // Let the browser handle the key normally.
        return false;
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
        return true;
    }

    if (narrow_hotkeys.hasOwnProperty(code)) {
        narrow_hotkeys[code](selected_message_id);
        return true;
    }

    // We're in the middle of a combo; stop processing because
    // we want the browser to handle it (to avoid breaking
    // things like Ctrl-C or Command-C for copy).
    if (e.metaKey || e.ctrlKey) {
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
    case 27: // Esc: close actions popup, cancel compose, clear a find, or un-narrow
        if (ui.actions_currently_popped()) {
            ui.hide_actions_popover();
        } else if (compose.composing()) {
            compose.cancel();
        } else {
            search.clear_search();
        }
        return true;
    case 99: // 'c': compose
        compose.set_mode('stream');
        return true;
    case 67: // 'C': compose private message
        compose.set_mode('private');
        return true;
    case  13: // Enter: respond to message (unless we need to do something else)
        if (search.keyboard_currently_finding()) {
            // Pass through to our searchbox (to advance to next result)
            return false;
        } else {
            respond_to_message();
            return true;
        }
    case 114: // 'r': respond to message
        respond_to_message();
        return true;
    case 82: // 'R': respond to author
        respond_to_message("personal");
        return true;
    case 47: // '/': initiate search
        search.initiate_search();
        return true;
    case 63: // '?': Show keyboard shortcuts page
        $('#keyboard-shortcuts').modal('show');
        return true;
    }

    return false;
}

/* We register both a keydown and a keypress function because
   we want to intercept pgup/pgdn, escape, etc, and process them
   as they happen on the keyboard. However, if we processed
   letters/numbers in keydown, we wouldn't know what the case of
   the letters were.

   We want case-sensitive hotkeys (such as in the case of r vs R)
   so we bail in .keydown if the event is a letter or number and
   instead just let keypress go for it. */

$(document).keydown(function (e) {
    // Restrict to non-alphanumeric keys
    if (48 > e.which || 90 < e.which) {
        if (process_hotkey(e))
            e.preventDefault();
    }
});

$(document).keypress(function (e) {
    // What exactly triggers .keypress may vary by browser.
    // Welcome to compatability hell.
    //
    // In particular, when you press tab in Firefox, it fires a
    // keypress event with keycode 0 after processing the original
    // event.
    if (e.which !== 0 && e.charCode !== 0) {
        if (process_hotkey(e))
            e.preventDefault();
    }
});

return exports;

}());
