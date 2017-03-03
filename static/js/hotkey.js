var hotkeys = (function () {

var exports = {};

function do_narrow_action(action) {
    action(current_msg_list.selected_id(), {trigger: 'hotkey'});
    return true;
}


function focus_in_empty_compose() {
    return (
        compose.composing() &&
        compose.message_content() === "" &&
        $('#new_message_content').is(':focus'));
}

function is_settings_page() {
  return (/^#*(settings|administration)/g).test(window.location.hash);
}

var actions_dropdown_hotkeys = [
    'down_arrow',
    'up_arrow',
    'vim_up',
    'vim_down',
    'enter',
];

// Note that multiple keys can map to the same event_name, which
// we'll do in cases where they have the exact same semantics.
// DON'T FORGET: update keyboard_shortcuts.html

var hotkeys_shift = {
    // these can be triggered by shift + key only
    9: {name: 'shift_tab', message_view_only: false}, // tab
    32: {name: 'page_up', message_view_only: true},  // space bar
};
var hotkeys_no_modifiers = {
    // these can be triggered by key only (without shift)
    9: {name: 'tab', message_view_only: false}, // tab
    32: {name: 'page_down', message_view_only: true}, // space bar
    33: {name: 'page_up', message_view_only: true}, // page up
    34: {name: 'page_down', message_view_only: true}, // page down
    35: {name: 'end', message_view_only: true}, // end
    36: {name: 'home', message_view_only: true}, // home
    37: {name: 'left_arrow', message_view_only: true}, // left arrow
    38: {name: 'up_arrow', message_view_only: true}, // up arrow
    40: {name: 'down_arrow', message_view_only: true}, // down arrow
};
var hotkeys_shift_insensitive = {
    // these can be triggered by key or shift + key
    // Note that codes for letters are still case sensitive!
    8: {name: 'backspace', message_view_only: true}, // backspace
    13: {name: 'enter', message_view_only: false}, // enter
    27: {name: 'escape', message_view_only: false}, // escape
    47: {name: 'search', message_view_only: false}, // '/'
    63: {name: 'show_shortcuts', message_view_only: false}, // '?'
    64: {name: 'compose_reply_with_mention', message_view_only: true}, // '@'
    65: {name: 'stream_cycle_backward', message_view_only: true}, // 'A'
    67: {name: 'compose_private_message', message_view_only: true}, // 'C'
    68: {name: 'stream_cycle_forward', message_view_only: true}, // 'D'
    74: {name: 'page_down', message_view_only: true}, // 'J'
    75: {name: 'page_up', message_view_only: true}, // 'K'
    82: {name: 'respond_to_author', message_view_only: true}, // 'R'
    83: {name: 'narrow_by_subject', message_view_only: true}, //'S'
    99: {name: 'compose', message_view_only: true}, // 'c'
    105: {name: 'message_actions', message_view_only: true}, // 'i'
    106: {name: 'vim_down', message_view_only: true}, // 'j'
    107: {name: 'vim_up', message_view_only: true}, // 'k'
    113: {name: 'query_users', message_view_only: false}, // 'q'
    114: {name: 'reply_message', message_view_only: true}, // 'r'
    115: {name: 'narrow_by_recipient', message_view_only: true}, // 's'
    118: {name: 'narrow_private', message_view_only: true}, // 'v'
    119: {name: 'query_streams', message_view_only: false}, // 'w'
};

var tab_up_down = (function () {
    var list = ["#group-pm-list", "#stream_filters", "#global_filters", "#user_presences"];

    return function (e) {
        var $target = $(e.target);
        var flag = $target.closest(list.join(", ")).length > 0;

        return {
            flag: flag,
            next: function () {
                return $target.closest("li").next().find("a");
            },
            prev: function () {
                return $target.closest("li").prev().find("a");
            },
        };
    };
}());

function get_hotkey_from_event(e) {

    // We're in the middle of a combo; stop processing because
    // we want the browser to handle it (to avoid breaking
    // things like Ctrl-C or Command-C for copy).
    if (e.metaKey || e.ctrlKey || e.altKey) {
        return {name: 'ignore', message_view_only: false};
    }

    if (e.shiftKey && hotkeys_shift[e.which] !== undefined) {
        return hotkeys_shift[e.which];
    } else if (!e.shiftKey && hotkeys_no_modifiers[e.which] !== undefined) {
        return hotkeys_no_modifiers[e.which];
    } else if (hotkeys_shift_insensitive[e.which] !== undefined) {
        return hotkeys_shift_insensitive[e.which];
    }

    return {name: 'ignore', message_view_only: false};
}

// Process a keydown or keypress event.
//
// Returns true if we handled it, false if the browser should.
function process_hotkey(e) {
    var row;
    var alert_words_content;
    var focused_message_edit_content;
    var focused_message_edit_save;
    var message_edit_form;
    var hotkey = get_hotkey_from_event(e);
    var event_name = hotkey.name;
    activity.new_user_input = true;

    if (event_name === 'ignore') {
        return false;
    }

    if (hotkey.message_view_only && ui.home_tab_obscured()) {
        return false;
    }

    if ($(e.target).is(".editable-section")) {
        if (event_name === "enter") {
            $(e.target).parent().find(".checkmark").click();
        }
        return false;
    }

    var tab_list;

    if (event_name === "up_arrow") {
        tab_list = tab_up_down(e);
        if (tab_list.flag) {
            tab_list.prev().focus();
            return true;
        }
    }

    if (event_name === "down_arrow") {
        tab_list = tab_up_down(e);
        if (tab_list.flag) {
            tab_list.next().focus();
            return true;
        }
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
        alert_words_content = $(".edit-alert-word").filter(":focus");
        if (alert_words_content.length > 0) {
            var add_word_li = alert_words_content.closest(".alert-word-item");
            add_word_li.find(".add-alert-word").focus();
            return true;
        }

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

    if (event_name === "escape") {
        if ($("#overlay").hasClass("show")) {
            ui.exit_lightbox_photo();
            return true;
        } else if ($("#subscription_overlay").hasClass("show")) {
            subs.close();
            return true;
        } else if ($("#draft_overlay").hasClass("show")) {
            drafts.close();
            return true;
        } else if ($(".informational-overlays").hasClass("show")) {
            ui.hide_info_overlay();
            return true;
        }
    }

    if (is_settings_page()) {
        if (event_name === 'up_arrow') {
            var prev = e.target.previousElementSibling;

            if ($(prev).css("display") !== "none") {
                $(prev).focus().click();
            }
            return true;
        } else if (event_name === 'down_arrow') {
            var next = e.target.nextElementSibling;

            if ($(next).css("display") !== "none") {
                $(next).focus().click();
            }
            return true;
        } else if (event_name === 'escape') {
            $("#settings_overlay_container .exit").click();
            return true;
        }
        return false;
    }

    // Process hotkeys specially when in an input, select, textarea, or send button
    if ($('input:focus,select:focus,textarea:focus,#compose-send-button:focus').length > 0) {
        if (event_name === 'escape') {
            // emoji window should trap escape before it is able to close the compose box
            if ($('.emoji_popover').css('display') === 'inline-block') {
                popovers.hide_emoji_map_popover();
                return;
            }
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
            } else if ($(".message_edit_topic").filter(":focus").length > 0) {
                row = $(".message_edit_topic").filter(":focus").closest(".message_row");
                message_edit.end(row);
            } else if (activity.searching()) {
                activity.escape_search();
                return true;
            } else if (stream_list.searching()) {
                stream_list.escape_search();
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
            if (is_settings_page()) {
                $(e.target).click();
                return true;
            } else if (activity.searching()) {
                activity.blur_search();
                return true;
            } else if (stream_list.searching()) {
                stream_list.clear_and_hide_search();
                return true;
            }
        }

        if (event_name === 'left_arrow' && focus_in_empty_compose()) {
            compose.cancel();
            message_edit.edit_last_sent_message();
            return true;
        }

        if ((event_name === 'up_arrow' || event_name === 'down_arrow') && focus_in_empty_compose()) {
            compose.cancel();
            // don't return, as we still want it to be picked up by the code below
        } else {
            // Let the browser handle the key normally.
            return false;
        }
    }

    if (event_name === 'left_arrow') {
        message_edit.edit_last_sent_message();
        return true;
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
        case 'compose': // 'c': compose
            compose.start('stream', {trigger: "compose_hotkey"});
            return true;
        case 'compose_private_message':
            compose.start('private', {trigger: "compose_hotkey"});
            return true;
        case 'enter':
            // There's special handling for when you're previewing a composition
            if ($("#preview_message_area").is(":visible")) {
                compose.enter_with_preview_open();
                return true;
            }
            break;
        case 'escape': // Esc: close actions popup, cancel compose, clear a find, or un-narrow
            if ($('.emoji_popover').css('display') === 'inline-block') {
                popovers.hide_emoji_map_popover();
            } else if (popovers.any_active()) {
                popovers.hide_all();
            } else if (compose.composing()) {
                compose.cancel();
            } else {
                search.clear_search();
            }
            return true;
        case 'narrow_private':
            return do_narrow_action(function (target, opts) {
                narrow.by('is', 'private', opts);
            });
        case 'query_streams':
            stream_list.initiate_search();
            return true;
        case 'query_users':
            activity.initiate_search();
            return true;
        case 'search':
            search.initiate_search();
            return true;
        case 'show_shortcuts': // Show keyboard shortcuts page
            ui.show_info_overlay("keyboard-shortcuts");
            return true;
        case 'stream_cycle_backward':
            navigate.cycle_stream('backward');
            return true;
        case 'stream_cycle_forward':
            navigate.cycle_stream('forward');
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
            if (!is_settings_page()) {
                navigate.page_up();
                return true;
            }
            break;
        case 'page_down':
            if (!is_settings_page()) {
                navigate.page_down();
                return true;
            }
            break;
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
            compose.respond_to_message({trigger: 'hotkey enter'});
            return true;
        case 'reply_message': // 'r': respond to message
            compose.respond_to_message({trigger: 'hotkey'});
            return true;
        case 'respond_to_author': // 'R': respond to author
            compose.respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
            return true;
        case 'compose_reply_with_mention': // '@': respond to message with mention to author
            compose.respond_to_message({trigger: 'hotkey'});
            var message = current_msg_list.selected_message();
            $("#new_message_content").val('@**' + message.sender_full_name + '** ');
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
    // check if 27 (esc) because it doesn't register under .keypress()
    if (e.which < 48 || e.which > 90 || e.which === 27) {
        if (process_hotkey(e)) {
            e.preventDefault();
        }
    }
    resize.resize_bottom_whitespace();
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

if (typeof module !== 'undefined') {
    module.exports = hotkeys;
}
