var hotkeys = (function () {

var exports = {};

function do_narrow_action(action) {
    if (current_msg_list.empty()) {
        return false;
    }
    action(current_msg_list.selected_id(), {trigger: 'hotkey'});
    return true;
}

var directional_hotkeys = {
    'down_arrow':  {getrow: rows.next_visible, direction: 1, charCode: 0},  // down arrow
    'vim_down': {getrow: rows.next_visible, direction: 1, charCode: 106}, // 'j'
    'up_arrow':  {getrow: rows.prev_visible, direction: -1, charCode: 0}, // up arrow
    'vim_up': {getrow: rows.prev_visible, direction: -1, charCode: 107}, // 'k'
    'home':  {getrow: rows.first_visible, direction: -1, charCode: 0}  // Home
};

function get_event_name(e) {
    if ((e.which === 9) && e.shiftKey) {
        return 'shift_tab';
    }

    // We're in the middle of a combo; stop processing because
    // we want the browser to handle it (to avoid breaking
    // things like Ctrl-C or Command-C for copy).
    if (e.metaKey || e.ctrlKey) {
        return 'ignore';
    }

    if (!e.shiftKey) {
        switch (e.keyCode) {
        case 33: // Page Up
            return 'page_up';
        case 34: // Page Down
            return 'page_down';
        case 35:
            return 'end';
        case 36:
            return 'home';
        case 38:
            return 'up_arrow';
        case 40:
            return 'down_arrow';
        }
    }

    switch (e.which) {
    case 8:
        return 'backspace';
    case 13:
        return 'enter';
    case 27:
        return 'escape';
    case 32: // Spacebar
        if (e.shiftKey) {
            return 'page_up';
        } else {
            return 'page_down';
        }
    case 47: // '/': initiate search
        return 'search';
    case 63: // '?': Show keyboard shortcuts page
        return 'show_shortcuts';
    case 67: // 'C'
        return 'compose_private_message';
    case 82: // 'R': respond to author
        return 'respond_to_author';
    case 83: //'S'
        return 'narrow_by_subject';
    case 99: // 'c'
        return 'compose';
    case 106: // 'j'
        return 'vim_down';
    case 107: // 'k'
        return 'vim_up';
    case 114: // 'r': respond to message
        return 'reply_message';
    case 115: // 's'
        return 'narrow_by_recipient';
    case 118: // 'v'
        return 'narrow_private';
    }
    return 'ignore';
}

// Process a keydown or keypress event.
//
// Returns true if we handled it, false if the browser should.
function process_hotkey(e) {
    // Disable hotkeys on settings page etc., and when a modal pop-up
    // is visible.
    if (ui.home_tab_obscured())
        return false;

    var event_name = get_event_name(e);

    if (event_name === 'ignore') {
        return false;
    }

    var next_row, dirkey;

    // Handle a few keys specially when the send button is focused.
    if ($('#compose-send-button').is(':focus')) {
        if (event_name === 'backspace') {
            // Ignore backspace; don't navigate back a page.
            return true;
        } else if (event_name === 'shift_tab') {
            // Shift-Tab: go back to content textarea and restore
            // cursor position.
            ui.restore_compose_cursor();
            return true;
        }
    }

    // Process hotkeys specially when in an input, textarea, or send button
    if ($('input:focus,textarea:focus,#compose-send-button:focus').length > 0) {
        if (event_name === 'escape') {
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

        if ((event_name === 'up_arrow' || event_name === 'down_arrow')
            && compose.composing()
            && compose.message_content() === ""
            && page_params.staging) {
                compose.cancel();
                // don't return, as we still want it to be picked up by the code below
        } else {
            // Let the browser handle the key normally.
            return false;
        }
    }

    // If we're on a button or a link and have pressed enter, let the
    // browser handle the keypress
    //
    // This is subtle and here's why: Suppose you have the focus on a
    // stream name in your left sidebar. j and k will still move your
    // cursor up and down, but Enter won't reply -- it'll just trigger
    // the link on the sidebar! So you keep pressing enter over and
    // over again. Until you click somewhere or press r.
    if ($('a:focus,button:focus').length > 0 && event_name === 'enter') {
        return false;
    }

    if (event_name === 'end') {
        if (current_msg_list.empty()) {
            return false;
        }
        var next_id = current_msg_list.last().id;
        last_viewport_movement_direction = 1;
        current_msg_list.select_id(next_id, {then_scroll: true,
                                             from_scroll: true});
        return true;
    }

    if (directional_hotkeys.hasOwnProperty(event_name)) {
        if (current_msg_list.empty()) {
            return false;
        }
        dirkey = directional_hotkeys[event_name];
        last_viewport_movement_direction = dirkey.direction;
        next_row = dirkey.getrow(current_msg_list.selected_row());
        if (next_row.length !== 0) {
            ui.show_pointer();
            current_msg_list.select_id(rows.id(next_row),
                                       {then_scroll: true,
                                        from_scroll: true});
        }
        if ((next_row.length === 0) && (event_name === 'down_arrow' || event_name === 'vim_down')) {
            // At the last message, scroll to the bottom so we have
            // lots of nice whitespace for new messages coming in.
            //
            // FIXME: this doesn't work for End because rows.last_visible()
            // always returns a message.
            viewport.scrollTop($("#main_div").outerHeight(true));
        }
        return true;
    }

    switch (event_name) {
    case 'narrow_by_recipient':
        return do_narrow_action(narrow.by_recipient);
    case 'narrow_by_subject':
        return do_narrow_action(narrow.by_subject);
    case 'narrow_private':
        return do_narrow_action(function (target, opts) {
            narrow.by('is', 'private-message', opts);
        });
    }


    switch (event_name) {
    case 'page_up':
        if (viewport.at_top() && !current_msg_list.empty()) {
            current_msg_list.select_id(current_msg_list.first().id, {then_scroll: false});
        }
        else {
            ui.page_up_the_right_amount();
        }
        return true;
    case 'page_down':
        if (viewport.at_bottom() && !current_msg_list.empty()) {
            current_msg_list.select_id(current_msg_list.last().id, {then_scroll: false});
        }
        else {
            ui.page_down_the_right_amount();
        }
        return true;
    case 'escape': // Esc: close actions popup, cancel compose, clear a find, or un-narrow
        if (ui.actions_currently_popped()) {
            ui.hide_actions_popover();
        } else if (compose.composing()) {
            compose.cancel();
        } else {
            search.clear_search();
        }
        return true;
    case 'compose': // 'c': compose
        compose.set_mode('stream');
        respond_to_sent_message = true;
        return true;
    case 'compose_private_message':
        compose.set_mode('private');
        respond_to_sent_message = true;
        return true;
    case  'enter': // Enter: respond to message (unless we need to do something else)
        respond_to_cursor = true;
        respond_to_message({trigger: 'hotkey enter'});
        return true;
    case 'reply_message': // 'r': respond to message
        respond_to_cursor = true;
        respond_to_message({trigger: 'hotkey'});
        return true;
    case 'respond_to_author': // 'R': respond to author
        respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
        return true;
    case 'search':
        search.initiate_search();
        return true;
    case 'show_shortcuts': // Show keyboard shortcuts page
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
