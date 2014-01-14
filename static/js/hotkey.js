var hotkeys = (function () {

var exports = {};

function do_narrow_action(action) {
    action(current_msg_list.selected_id(), {trigger: 'hotkey'});
    return true;
}

var actions_dropdown_hotkeys = [
    'down_arrow',
    'up_arrow',
    'vim_up',
    'vim_down',
    'enter'
];

function get_event_name(e) {
    // Note that multiple keys can map to the same event_name, which
    // we'll do in cases where they have the exact same semantics.
    // DON'T FORGET: update keyboard_shortcuts.html

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
    case 9:
        return 'tab';
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
    case 74: // 'J'
        return 'page_down';
    case 75: // 'K'
        return 'page_up';
    case 82: // 'R': respond to author
        return 'respond_to_author';
    case 83: //'S'
        return 'narrow_by_subject';
    case 99: // 'c'
        return 'compose';
    case 105: // 'i'
        return 'message_actions';
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
    var row, focused_message_edit_content, focused_message_edit_save, message_edit_form;

    var event_name = get_event_name(e);
    activity.new_user_input = true;

    if (event_name === "tab") {
        // The alert word configuration is on the settings page,
        // so handle this before we abort early
        var alert_words_content = $(".edit-alert-word").filter(":focus");
        if (alert_words_content.length > 0) {
            var add_word_li = alert_words_content.closest(".alert-word-item");
            add_word_li.find(".add-alert-word").focus();
            return true;
        }
    }

    if (ui.home_tab_obscured() && event_name !== 'search') {
        return false;
    }

    if (event_name === 'ignore') {
        return false;
    }

    if (popovers.actions_popped() && actions_dropdown_hotkeys.indexOf(event_name) !== -1) {
        popovers.actions_menu_handle_keyboard(event_name);
        return true;
    }

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

    // In Safari and the desktop app, we can't tab to buttons. Intercept the
    // tab from the message edit content box to Save and then Cancel.
    if (event_name === "tab") {
        focused_message_edit_content = $(".message_edit_content").filter(":focus");
        if (focused_message_edit_content.length > 0) {
            message_edit_form = focused_message_edit_content.closest(".message_edit_form");
            message_edit_form.find(".message_edit_save").focus();
            return true;
        }

        focused_message_edit_save = $(".message_edit_save").filter(":focus");
        if (focused_message_edit_save.length > 0) {
            message_edit_form = focused_message_edit_save.closest(".message_edit_form");
            message_edit_form.find(".message_edit_cancel").focus();
            return true;
        }
    }
    if (event_name === "shift_tab") {
        // Shift-tabbing from the edit message cancel button takes you to save.
        if ($(".message_edit_cancel").filter(":focus").length > 0) {
            $(".message_edit_save").focus();
            return true;
        }

        // Shift-tabbing from the edit message save button takes you to the content.
        focused_message_edit_save = $(".message_edit_save").filter(":focus");
        if (focused_message_edit_save.length > 0) {
            focused_message_edit_save.closest(".message_edit_form")
                                     .find(".message_edit_content").focus();
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
            } else if ($(".message_edit_content").filter(":focus").length > 0) {
                row = $(".message_edit_content").filter(":focus").closest(".message_row");
                message_edit.end(row);
            } else if (activity.searching()) {
                activity.clear_search();
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

        if (event_name === 'enter') {
            if (activity.searching()) {
                activity.blur_search();
                return true;
            }
        }

        if ((event_name === 'up_arrow' || event_name === 'down_arrow')
            && compose.composing()
            && compose.message_content() === ""
            && $('#new_message_content').is(':focus')) {
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

    // Shortcuts that don't require a message
    switch (event_name) {
        case 'narrow_private':
            return do_narrow_action(function (target, opts) {
                narrow.by('is', 'private', opts);
            });
        case 'escape': // Esc: close actions popup, cancel compose, clear a find, or un-narrow
            if (popovers.any_active()) {
                popovers.hide_all();
            } else if (compose.composing()) {
                compose.cancel();
            } else {
                search.clear_search();
            }
            return true;
        case 'compose': // 'c': compose
            compose.start('stream', {trigger: "compose_hotkey"});
            return true;
        case 'compose_private_message':
            compose.start('private', {trigger: "compose_hotkey"});
            return true;
        case 'search':
            search.initiate_search();
            return true;
        case 'show_shortcuts': // Show keyboard shortcuts page
            $('#keyboard-shortcuts').modal('show');
            return true;
    }

    if (current_msg_list.empty()) {
        return false;
    }

    // Navigation shortcuts
    switch (event_name) {
        case 'down_arrow':
        case 'vim_down':
            navigate.down(true); // with_centering
            return true;
        case 'up_arrow':
        case 'vim_up':
            navigate.up();
            return true;
        case 'home':
            navigate.to_home();
            return true;
        case 'end':
            navigate.to_end();
            return true;
        case 'page_up':
            navigate.page_up();
            return true;
        case 'page_down':
            navigate.page_down();
            return true;
    }

    if (current_msg_list.on_expandable_row()) {
        switch (event_name) {
            case 'enter':
                ui.expand_summary_row(current_msg_list.selected_row().expectOne());
                return true;
        }
        return false;
    }

    // Shortcuts that operate on a message
    switch (event_name) {
        case 'message_actions':
            return popovers.open_message_menu();
        case 'narrow_by_recipient':
            return do_narrow_action(narrow.by_recipient);
        case 'narrow_by_subject':
            return do_narrow_action(narrow.by_subject);
        case  'enter': // Enter: respond to message (unless we need to do something else)
            respond_to_message({trigger: 'hotkey enter'});
            return true;
        case 'reply_message': // 'r': respond to message
            respond_to_message({trigger: 'hotkey'});
            return true;
        case 'respond_to_author': // 'R': respond to author
            respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
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
        if (process_hotkey(e)) {
            e.preventDefault();
        }
    }
    ui.resize_bottom_whitespace();
});

$(document).keypress(function (e) {
    // What exactly triggers .keypress may vary by browser.
    // Welcome to compatability hell.
    //
    // In particular, when you press tab in Firefox, it fires a
    // keypress event with keycode 0 after processing the original
    // event.
    if (e.which !== 0 && e.charCode !== 0) {
        if (process_hotkey(e)) {
            e.preventDefault();
        }
    }
});

return exports;

}());
