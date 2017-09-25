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
    'enter',
];

// Note that multiple keys can map to the same event_name, which
// we'll do in cases where they have the exact same semantics.
// DON'T FORGET: update keyboard_shortcuts.html

var keydown_shift_mappings = {
    // these can be triggered by shift + key only
    9: {name: 'shift_tab', message_view_only: false}, // tab
    32: {name: 'shift_spacebar', message_view_only: true},  // space bar
};

var keydown_unshift_mappings = {
    // these can be triggered by key only (without shift)
    9: {name: 'tab', message_view_only: false}, // tab
    27: {name: 'escape', message_view_only: false}, // escape
    32: {name: 'spacebar', message_view_only: true}, // space bar
    33: {name: 'page_up', message_view_only: true}, // page up
    34: {name: 'page_down', message_view_only: true}, // page down
    35: {name: 'end', message_view_only: true}, // end
    36: {name: 'home', message_view_only: true}, // home
    37: {name: 'left_arrow', message_view_only: false}, // left arrow
    39: {name: 'right_arrow', message_view_only: false}, // right arrow
    38: {name: 'up_arrow', message_view_only: false}, // up arrow
    40: {name: 'down_arrow', message_view_only: false}, // down arrow
};

var keydown_ctrl_mappings = {
    219: {name: 'escape', message_view_only: false}, // '['
};

var keydown_either_mappings = {
    // these can be triggered by key or shift + key
    // Note that codes for letters are still case sensitive!
    //
    // We may want to revisit both of these.  For backspace, we don't
    // have any specific mapping behavior; we are just trying to disable
    // the normal browser features for certain OSes when we are in the
    // compose box, and the little bit of backspace-related code here is
    // dubious, but may apply to shift-backspace.
    // For enter, there is some possibly that shift-enter is intended to
    // have special behavior for folks that are used to shift-enter behavior
    // in other apps, but that's also slightly dubious.
    8: {name: 'backspace', message_view_only: true}, // backspace
    13: {name: 'enter', message_view_only: false}, // enter
};

var keypress_mappings = {
    42: {name: 'star_message', message_view_only: true}, // '*'
    43: {name: 'thumbs_up_emoji', message_view_only: true}, // '+'
    45: {name: 'toggle_message_collapse', message_view_only: true}, // '-'
    47: {name: 'search', message_view_only: false}, // '/'
    58: {name: 'open_reactions', message_view_only: true}, // ':'
    63: {name: 'show_shortcuts', message_view_only: false}, // '?'
    64: {name: 'compose_reply_with_mention', message_view_only: true}, // '@'
    65: {name: 'stream_cycle_backward', message_view_only: true}, // 'A'
    67: {name: 'compose_private_message', message_view_only: true}, // 'C'
    68: {name: 'stream_cycle_forward', message_view_only: true}, // 'D'
    71: {name: 'G_end', message_view_only: true}, // 'G'
    74: {name: 'vim_page_down', message_view_only: true}, // 'J'
    75: {name: 'vim_page_up', message_view_only: true}, // 'K'
    77: {name: 'toggle_mute', message_view_only: true}, // 'M'
    80: {name: 'narrow_private', message_view_only: true}, // 'P'
    82: {name: 'respond_to_author', message_view_only: true}, // 'R'
    83: {name: 'narrow_by_subject', message_view_only: true}, //'S'
    86: {name: 'view_selected_stream', message_view_only: false}, //'V'
    99: {name: 'compose', message_view_only: true}, // 'c'
    100: {name: 'open_drafts', message_view_only: false}, // 'd'
    103: {name: 'gear_menu', message_view_only: true}, // 'g'
    105: {name: 'message_actions', message_view_only: true}, // 'i'
    106: {name: 'vim_down', message_view_only: true}, // 'j'
    107: {name: 'vim_up', message_view_only: true}, // 'k'
    110: {name: 'n_key', message_view_only: false}, // 'n'
    113: {name: 'query_streams', message_view_only: false}, // 'q'
    114: {name: 'reply_message', message_view_only: true}, // 'r'
    115: {name: 'narrow_by_recipient', message_view_only: true}, // 's'
    117: {name: 'show_sender_info', message_view_only: true}, // 'u'
    118: {name: 'show_lightbox', message_view_only: true}, // 'v'
    119: {name: 'query_users', message_view_only: false}, // 'w'
};

exports.get_keydown_hotkey = function (e) {
    if (e.metaKey || e.altKey) {
        return;
    }

    var hotkey;
    if (e.ctrlKey) {
        hotkey = keydown_ctrl_mappings[e.which];
        if (hotkey) {
            return hotkey;
        }
        return;
    }

    if (e.shiftKey) {
        hotkey = keydown_shift_mappings[e.which];
        if (hotkey) {
            return hotkey;
        }
    }

    if (!e.shiftKey) {
        hotkey = keydown_unshift_mappings[e.which];
        if (hotkey) {
            return hotkey;
        }
    }

    return keydown_either_mappings[e.which];
};

exports.get_keypress_hotkey = function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) {
        return;
    }

    return keypress_mappings[e.which];
};

exports.processing_text = function () {
    var selector = 'input:focus,select:focus,textarea:focus,#compose-send-button:focus,.editable-section:focus';
    return $(selector).length > 0;
};

exports.is_editing_stream_name = function (e) {
    return $(e.target).is(".editable-section");
};

// Returns true if we handled it, false if the browser should.
exports.process_escape_key = function (e) {
    var row;

    if (exports.is_editing_stream_name(e)) {
        return false;
    }

    if (overlays.is_modal_open()) {
        overlays.close_active_modal();
        return true;
    }

    if (overlays.is_active()) {
        overlays.close_active();
        return true;
    }

    if (gear_menu.is_open()) {
        gear_menu.close();
        return true;
    }

    if (message_edit.is_editing(current_msg_list.selected_id())) {
        message_edit.end(current_msg_list.selected_row());
        return true;
    }

    if (exports.processing_text()) {
        if ($(".message_edit_content").filter(":focus").length > 0) {
            row = $(".message_edit_content").filter(":focus").closest(".message_row");
            row.find('.message_edit_content').blur();
            message_edit.end(row);
            return true;
        }

        if ($(".message_edit_topic").filter(":focus").length > 0) {
            row = $(".message_edit_topic").filter(":focus").closest(".message_row");
            row.find('.message_edit_topic').blur();
            message_edit.end(row);
            return true;
        }

        if (activity.searching()) {
            activity.escape_search();
            return true;
        }

        if (stream_list.searching()) {
            stream_list.escape_search();
            return true;
        }

        // Emoji picker goes before compose so compose emoji picker is closed properly.
        if (emoji_picker.reactions_popped()) {
            emoji_picker.hide_emoji_popover();
            return true;
        }

        if (compose_state.composing()) {
            // If the user hit the escape key, cancel the current compose
            compose_actions.cancel();
            return true;
        }

        // We pressed Esc and something was focused, and the composebox
        // wasn't open. In that case, we should blur the input.
        // (this is almost certainly the searchbar)
        $("input:focus,textarea:focus").blur();
        return true;
    }

    if (popovers.any_active()) {
        popovers.hide_all();
        return true;
    }

    if (compose_state.composing()) {
        compose_actions.cancel();
        return true;
    }

    search.clear_search();
    return true;
};

// Returns true if we handled it, false if the browser should.
exports.process_enter_key = function (e) {
    if ($(".dropdown.open").length && $(e.target).attr("role") === "menuitem") {
        // on #gear-menu li a[tabindex] elements, force a click and prevent default.
        // this is because these links do not have an href and so don't force a
        // default action.
        e.target.click();
        return true;
    }

    if (hotspots.is_open()) {
        $(e.target).find('.hotspot.overlay.show .hotspot-confirm').click();
        return false;
    }

    if (emoji_picker.reactions_popped()) {
        if (emoji_picker.is_composition(e.target)) {
            e.target.click();
        } else {
            emoji_picker.toggle_selected_emoji();
        }
        return true;
    }

    if (exports.is_editing_stream_name(e)) {
        $(e.target).parent().find(".checkmark").click();
        return false;
    }

    if (popovers.actions_popped()) {
        popovers.actions_menu_handle_keyboard('enter');
        return true;
    }

    if (overlays.settings_open()) {
        // On the settings page just let the browser handle
        // the enter key for things like submitting forms.
        return false;
    }

    if (overlays.streams_open()) {
        return false;
    }

    if (exports.processing_text()) {
        if (activity.searching()) {
            activity.blur_search();
            return true;
        }

        if (stream_list.searching()) {
            // This is sort of funny behavior, but I think
            // the intention is that we want it super easy
            // to close stream search.
            stream_list.clear_and_hide_search();
            return true;
        }

        return false;
    }

    // This handles when pressing enter while looking at drafts.
    // It restores draft that is focused.
    if (drafts.drafts_overlay_open()) {
        drafts.drafts_handle_events(e, "enter");
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
    if ($('a:focus,button:focus').length > 0) {
        return false;
    }

    if ($("#preview_message_area").is(":visible")) {
        compose.enter_with_preview_open();
        return true;
    }

    // If we got this far, then we're presumably in the message
    // view, so in that case "enter" is the hotkey to respond to a message.
    // Note that "r" has same effect, but that is handled in process_hotkey().
    compose_actions.respond_to_message({trigger: 'hotkey enter'});
    return true;
};

exports.process_tab_key = function () {
    // Returns true if we handled it, false if the browser should.
    // TODO: See if browsers like Safari can now handle tabbing correctly
    // without our intervention.

    var message_edit_form;

    var focused_message_edit_content = $(".message_edit_content").filter(":focus");
    if (focused_message_edit_content.length > 0) {
        message_edit_form = focused_message_edit_content.closest(".message_edit_form");
        message_edit_form.find(".message_edit_save").focus();
        return true;
    }

    var focused_message_edit_save = $(".message_edit_save").filter(":focus");
    if (focused_message_edit_save.length > 0) {
        message_edit_form = focused_message_edit_save.closest(".message_edit_form");
        message_edit_form.find(".message_edit_cancel").focus();
        return true;
    }

    if (emoji_picker.reactions_popped()) {
        return emoji_picker.navigate('tab');
    }

    return false;
};

exports.process_shift_tab_key = function () {
    // Returns true if we handled it, false if the browser should.
    // TODO: See if browsers like Safari can now handle tabbing correctly
    // without our intervention.

    if ($('#compose-send-button').is(':focus')) {
        // Shift-Tab: go back to content textarea and restore
        // cursor position.
        ui.restore_compose_cursor();
        return true;
    }

    // Shift-tabbing from the edit message cancel button takes you to save.
    if ($(".message_edit_cancel").filter(":focus").length > 0) {
        $(".message_edit_save").focus();
        return true;
    }

    // Shift-tabbing from the edit message save button takes you to the content.
    var focused_message_edit_save = $(".message_edit_save").filter(":focus");
    if (focused_message_edit_save.length > 0) {
        focused_message_edit_save.closest(".message_edit_form")
                                 .find(".message_edit_content").focus();
        return true;
    }

    // Shift-tabbing from emoji catalog/search results takes you back to search textbox.
    if (emoji_picker.reactions_popped()) {
        return emoji_picker.navigate('shift_tab');
    }

    return false;
};

// Process a keydown or keypress event.
//
// Returns true if we handled it, false if the browser should.
exports.process_hotkey = function (e, hotkey) {
    var event_name = hotkey.name;

    // We handle the most complex keys in their own functions.
    switch (event_name) {
        case 'escape':
            return exports.process_escape_key(e);
        case 'enter':
            return exports.process_enter_key(e);
        case 'tab':
            return exports.process_tab_key();
        case 'shift_tab':
            return exports.process_shift_tab_key();
    }

    switch (event_name) {
        // TODO: break out specific handlers for up_arrow,
        //       down_arrow, and backspace
        case 'up_arrow':
        case 'down_arrow':
        case 'backspace':
            if (drafts.drafts_overlay_open()) {
                drafts.drafts_handle_events(e, event_name);
                return true;
            }
    }

    if (hotkey.message_view_only && overlays.is_active()) {
        if (exports.processing_text()) {
            return false;
        }
        if (event_name === 'narrow_by_subject' && overlays.streams_open()) {
            subs.keyboard_sub();
            return true;
        }
        if (overlays.lightbox_open()) {
            overlays.close_active();
            return true;
        }
        return false;
    }

    if (overlays.settings_open()) {
        if (exports.processing_text()) {
            return false;
        }
        switch (event_name) {
            case 'up_arrow':
                settings.handle_up_arrow(e);
                return true;
            case 'down_arrow':
                settings.handle_down_arrow(e);
                return true;
        }
        return false;
    }

    if (emoji_picker.reactions_popped()) {
        return emoji_picker.navigate(event_name);
    }

    if (hotspots.is_open()) {
        return false;
    }

    if (overlays.info_overlay_open()) {
        if (event_name === 'show_shortcuts') {
            overlays.close_active();
            return true;
        }
        return false;
    }

    if ((event_name === 'up_arrow' || event_name === 'down_arrow') && overlays.streams_open()) {
        return subs.switch_rows(event_name);
    }

    if (exports.is_editing_stream_name(e)) {
        // We handle the enter key in process_enter_key().
        // We ignore all other keys.
        return false;
    }

    if (event_name === "up_arrow") {
        if (list_util.inside_list(e)) {
            list_util.go_up(e);
            return true;
        }
    }

    if (event_name === "down_arrow") {
        if (list_util.inside_list(e)) {
            list_util.go_down(e);
            return true;
        }
    }

    if ((actions_dropdown_hotkeys.indexOf(event_name) !== -1) && popovers.actions_popped()) {
        popovers.actions_menu_handle_keyboard(event_name);
        return true;
    }

    // The next two sections date back to 00445c84 and are Mac/Chrome-specific,
    // and they should possibly be eliminated in favor of keeping standard
    // browser behavior.
    if (event_name === 'backspace') {
        if ($('#compose-send-button').is(':focus')) {
            // Ignore backspace; don't navigate back a page.
            return true;
        }
    }

    // Process hotkeys specially when in an input, select, textarea, or send button
    if (exports.processing_text()) {
        // Note that there is special handling for enter/escape too, but
        // we handle this in other functions.

        if (event_name === 'left_arrow' && compose_state.focus_in_empty_compose()) {
            message_edit.edit_last_sent_message();
            return true;
        }

        if ((event_name === 'up_arrow' || event_name === 'down_arrow') && compose_state.focus_in_empty_compose()) {
            compose_actions.cancel();
            // don't return, as we still want it to be picked up by the code below
        } else if (event_name === "page_up") {
            $("#new_message_content").caret(0);
            return true;
        } else if (event_name === "page_down") {
            // so that it always goes to the end of the compose box.
            $("#new_message_content").caret(Infinity);
            return true;
        } else {
            // Let the browser handle the key normally.
            return false;
        }
    }

    if (event_name === 'left_arrow') {
        if (overlays.lightbox_open()) {
            lightbox.prev();
            return true;
        } else if (overlays.streams_open()) {
            subs.toggle_view(event_name);
            return true;
        }

        message_edit.edit_last_sent_message();
        return true;
    }

    if (event_name === 'right_arrow') {
        if (overlays.lightbox_open()) {
            lightbox.next();
            return true;
        } else if (overlays.streams_open()) {
            subs.toggle_view(event_name);
            return true;
        }
    }

    // Shortcuts that don't require a message
    switch (event_name) {
        case 'compose': // 'c': compose
            compose_actions.start('stream', {trigger: "compose_hotkey"});
            return true;
        case 'compose_private_message':
            compose_actions.start('private', {trigger: "compose_hotkey"});
            return true;
        case 'narrow_private':
            return do_narrow_action(function (target, opts) {
                opts = _.defaults({}, opts, {select_first_unread: true});
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
        case 'gear_menu':
            gear_menu.open();
            return true;
        case 'show_shortcuts': // Show keyboard shortcuts page
            ui.maybe_show_keyboard_shortcuts();
            return true;
        case 'stream_cycle_backward':
            narrow.stream_cycle_backward();
            return true;
        case 'stream_cycle_forward':
            narrow.stream_cycle_forward();
            return true;
        case 'view_selected_stream':
            if (overlays.streams_open()) {
                subs.view_stream();
                return true;
            }
            break;
        case 'n_key':
            if (overlays.streams_open()) {
                if (page_params.can_create_streams) {
                    subs.new_stream_clicked();
                    return true;
                }
                return false;
            }
            narrow.narrow_to_next_topic();
            return true;
        case 'open_drafts':
            drafts.toggle();
            return true;
        case 'reply_message': // 'r': respond to message
            // Note that you can "enter" to respond to messages as well,
            // but that is handled in process_enter_key().
            compose_actions.respond_to_message({trigger: 'hotkey'});
            return true;
    }

    if (current_msg_list.empty()) {
        return false;
    }

    // Prevent navigation in the background when the overlays are active.
    if (overlays.is_active()) {
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
        case 'G_end':
            navigate.to_end();
            return true;
        case 'page_up':
        case 'vim_page_up':
        case 'shift_spacebar':
            navigate.page_up();
            return true;
        case 'page_down':
        case 'vim_page_down':
        case 'spacebar':
            navigate.page_down();
            return true;
    }

    var msg = current_msg_list.selected_message();
    // Shortcuts that operate on a message
    switch (event_name) {
        case 'message_actions':
            return popovers.open_message_menu();
        case 'star_message':
            return message_flags.toggle_starred(msg);
        case 'narrow_by_recipient':
            return do_narrow_action(narrow.by_recipient);
        case 'narrow_by_subject':
            return do_narrow_action(narrow.by_subject);
        case 'respond_to_author': // 'R': respond to author
            compose_actions.respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
            return true;
        case 'compose_reply_with_mention': // '@': respond to message with mention to author
            compose_actions.reply_with_mention({trigger: 'hotkey'});
            return true;
        case 'show_lightbox':
            lightbox.show_from_selected_message();
            return true;
        case 'show_sender_info':
            popovers.show_sender_info();
            return true;
        case 'open_reactions': // ':': open reactions to message
            reactions.open_reactions_popover();
            return true;
        case 'thumbs_up_emoji': // '+': reacts with thumbs up emoji on selected message
            reactions.toggle_emoji_reaction(msg.id, '+1');
            return true;
        case 'toggle_mute':
            muting_ui.toggle_mute(msg);
            return true;
        case 'toggle_message_collapse':
            condense.toggle_collapse(msg);
            return true;
    }

    return false;
};

/* We register both a keydown and a keypress function because
   we want to intercept pgup/pgdn, escape, etc, and process them
   as they happen on the keyboard. However, if we processed
   letters/numbers in keydown, we wouldn't know what the case of
   the letters were.

   We want case-sensitive hotkeys (such as in the case of r vs R)
   so we bail in .keydown if the event is a letter or number and
   instead just let keypress go for it. */

exports.process_keydown = function (e) {
    activity.new_user_input = true;
    var hotkey = exports.get_keydown_hotkey(e);
    if (!hotkey) {
        return false;
    }
    return exports.process_hotkey(e, hotkey);
};

$(document).keydown(function (e) {
    if (exports.process_keydown(e)) {
        // TODO: We should really move this resize code
        // so it only executes as part of navigation actions.
        resize.resize_bottom_whitespace();
        e.preventDefault();
    }
});

exports.process_keypress = function (e) {
    var hotkey = exports.get_keypress_hotkey(e);
    if (!hotkey) {
        return false;
    }
    return exports.process_hotkey(e, hotkey);
};

$(document).keypress(function (e) {
    if (exports.process_keypress(e)) {
        e.preventDefault();
    }
});

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = hotkeys;
}
