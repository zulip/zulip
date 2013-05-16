var hotkeys = (function () {

var exports = {};

var directional_hotkeys = {
    40:  {getrow: rows.next_visible, direction: 1},  // down arrow
    106: {getrow: rows.next_visible, direction: 1}, // 'j'
    38:  {getrow: rows.prev_visible, direction: -1}, // up arrow
    107: {getrow: rows.prev_visible, direction: -1}, // 'k'
    36:  {getrow: rows.first_visible, direction: -1}  // Home
};

var directional_hotkeys_id = {
    35:  {getid: function () {return current_msg_list.last().id;},
          direction: 1} // End
};

var narrow_hotkeys = {
    115: narrow.by_recipient,           // 's'
    83:  narrow.by_subject,             // 'S'
    118: function (target, opts) {      // 'v'
        narrow.by('is', 'private-message', opts);
    }
};

// Process a keydown or keypress event.
//
// Returns true if we handled it, false if the browser should.
function process_hotkey(e) {
    var code = e.which;
    var next_row, dirkey;

    // Disable hotkeys on settings page etc., and when a modal pop-up
    // is visible.
    if (ui.home_tab_obscured())
        return false;

    // Handle a few keys specially when the send button is focused.
    if ($('#compose-send-button').is(':focus')) {
        if (code === 8) {
            // Ignore backspace; don't navigate back a page.
            return true;
        } else if ((code === 9) && e.shiftKey) {
            // Shift-Tab: go back to content textarea and restore
            // cursor position.
            ui.restore_compose_cursor();
            return true;
        }
    }

    // Process hotkeys specially when in an input, textarea, or send button
    if ($('input:focus,textarea:focus,#compose-send-button:focus').length > 0) {
        if (code === 27) {
            // If one of our typeaheads is open, do nothing so that the Esc
            // will go to close it
            if ($("#subject").data().typeahead.shown ||
                $("#stream").data().typeahead.shown ||
                $("#private_message_recipient").data().typeahead.shown ||
                $("#new_message_content").data().typeahead.shown ||
                $("#search_query").data().typeahead.shown) {
                // For some reason this code is only needed in Firefox;
                // in Chrome our typeahead is able to intercept the Esc
                // event before we even get it.
                // Regardless, we do nothing in this case.
                return true;
            } else if (compose.composing()) {
                // If the user hit the escape key, cancel the current compose
                compose.cancel();
                return true;
            } else {
                // We pressed Esc and something was focused, and the composebox
                // wasn't open. In that case, we should blur the input.
                // (this is almost certainly the searchbar)
                $("input:focus,textarea:focus").blur();
                return true;
            }
        }
        // If we just typed a character to change the recipient in the
        // compose box, this means that we're no longer replying to
        // whatever the original message was, and we should unfade.
        if (compose.composing() &&
            $("#stream:focus,#subject:focus,#private_message_recipient:focus").length > 0) {
            compose.unfade_messages(true);
            return false;
        }
        // Let the browser handle the key normally.
        return false;
    }

    // If we're on a button or a link and have pressed enter, let the
    // browser handle the keypress
    //
    // This is subtle and here's why: Suppose you have the focus on a
    // stream name in your left sidebar. j and k will still move your
    // cursor up and down, but Enter won't reply -- it'll just trigger
    // the link on the sidebar! So you keep pressing enter over and
    // over again. Until you click somewhere or press r.
    if ($('a:focus,button:focus').length > 0 && code === 13) {
        return false;
    }

    if (directional_hotkeys_id.hasOwnProperty(code)) {
        if (current_msg_list.empty()) {
            return false;
        }
        dirkey = directional_hotkeys_id[code];
        var next_id = dirkey.getid();
        last_viewport_movement_direction = dirkey.direction;
        current_msg_list.select_id(next_id, {then_scroll: true,
                                             from_scroll: true});
        return true;
    }

    if (directional_hotkeys.hasOwnProperty(code)) {
        if (current_msg_list.empty()) {
            return false;
        }
        dirkey = directional_hotkeys[code];
        last_viewport_movement_direction = dirkey.direction;
        next_row = dirkey.getrow(current_msg_list.selected_row());
        if (next_row.length !== 0) {
            current_msg_list.select_id(rows.id(next_row),
                                       {then_scroll: true,
                                        from_scroll: true});
        }
        if ((next_row.length === 0) && (code === 40 || code === 106)) {
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
        if (current_msg_list.empty()) {
            return false;
        }
        narrow_hotkeys[code](current_msg_list.selected_id(), {trigger: 'hotkey'});
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
        if (viewport.at_top() && !current_msg_list.empty()) {
            current_msg_list.select_id(current_msg_list.first().id, {then_scroll: false});
        }
        else {
            ui.page_up_the_right_amount();
        }
        return true;
    case 32: // Spacebar
    case 34: // Page Down
        if (viewport.at_bottom() && !current_msg_list.empty()) {
            current_msg_list.select_id(current_msg_list.last().id, {then_scroll: false});
        }
        else {
            ui.page_down_the_right_amount();
        }
        return true;
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
        respond_to_cursor = true;
        respond_to_message({trigger: 'hotkey enter'});
        return true;
    case 114: // 'r': respond to message
        respond_to_cursor = true;
        respond_to_message({trigger: 'hotkey'});
        return true;
    case 82: // 'R': respond to author
        respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
        return true;
    case 47: // '/': initiate search
        search.initiate_search();
        return true;
    case 63: // '?': Show keyboard shortcuts page
        $('#keyboard-shortcuts').modal('show');
        return true;

    case 116: // 't'
        ui.anchor_to_top();
        return true;
    case 98: // 'b'
        ui.anchor_to_bottom();
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
