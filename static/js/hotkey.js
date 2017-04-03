var hotkeys = (function () {

var exports = {};

function do_narrow_action(action) {
    action(current_msg_list.selected_id(), {trigger: 'hotkey'});
    return true;
}


function focus_in_empty_compose() {
    return (
        compose_state.composing() &&
        compose.message_content() === "" &&
        $('#new_message_content').is(':focus'));
}

function open_reactions() {
    var message = current_msg_list.selected_message();
    var target = $(current_msg_list.selected_row()).find(".icon-vector-chevron-down")[0];
    if (!message.sent_by_me) {
        target = $(current_msg_list.selected_row()).find(".icon-vector-smile")[0];
    }
    popovers.toggle_reactions_popover(target, current_msg_list.selected_id());
    return true;
}

exports.is_settings_page = function () {
  return (/^#*(settings|administration)/g).test(window.location.hash);
};

exports.is_lightbox_open = function () {
    return lightbox.is_open;
};

exports.is_subs = function () {
    return subs.is_open;
};

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
    38: {name: 'up_arrow', message_view_only: true}, // up arrow
    40: {name: 'down_arrow', message_view_only: true}, // down arrow
};

var keydown_ctrl_mappings = {
    219: {name: 'esc_ctrl', message_view_only: false}, // '['
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
    85: {name: 'keyboard_sub', message_view_only: false}, //'U'
    86: {name: 'view_selected_stream', message_view_only: false}, //'V'
    99: {name: 'compose', message_view_only: true}, // 'c'
    100: {name: 'open_drafts', message_view_only: false}, // 'd'
    103: {name: 'gear_menu', message_view_only: true}, // 'g'
    105: {name: 'message_actions', message_view_only: true}, // 'i'
    106: {name: 'vim_down', message_view_only: true}, // 'j'
    107: {name: 'vim_up', message_view_only: true}, // 'k'
    110: {name: 'new_stream', message_view_only: false}, // 'n'
    113: {name: 'query_users', message_view_only: false}, // 'q'
    114: {name: 'reply_message', message_view_only: true}, // 'r'
    115: {name: 'narrow_by_recipient', message_view_only: true}, // 's'
    118: {name: 'show_lightbox', message_view_only: true}, // 'v'
    119: {name: 'query_streams', message_view_only: false}, // 'w'
};

exports.tab_up_down = (function () {
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
    var selector = 'input:focus,select:focus,textarea:focus,#compose-send-button:focus';
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

    if (exports.is_lightbox_open()) {
        modals.close_modal("lightbox");
        return true;
    }

    if ($("#subscription_overlay").hasClass("show")) {
        modals.close_modal("subscriptions");
        return true;
    }

    if (drafts.drafts_overlay_open()) {
        modals.close_modal("drafts");
        return true;
    }

    if ($(".informational-overlays").hasClass("show")) {
        modals.close_modal("informationalOverlays");
        return true;
    }

    if ($("#invite-user.show").length) {
        modals.close_modal("invite");
        return true;
    }

    if (exports.is_settings_page()) {
        $("#settings_overlay_container .exit").click();
        return true;
    }

    // emoji window should trap escape before it is able to close the compose box
    if ($('.emoji_popover').css('display') === 'inline-block') {
        popovers.hide_emoji_map_popover();
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

        if (compose_state.composing()) {
            // If the user hit the escape key, cancel the current compose
            compose_actions.cancel();
            return true;
        }

        if (popovers.reactions_popped()) {
            popovers.hide_reactions_popover();
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
    if ($(".dropdown.open").length) {
        // on #gear-menu li a[tabindex] elements, force a click and prevent default.
        // this is because these links do not have an href and so don't force a
        // default action.
        e.target.click();
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

    if (exports.is_settings_page()) {
        // On the settings page just let the browser handle
        // the enter key for things like submitting forms.
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
        var draft_list = drafts.draft_model.get();
        if (document.activeElement.parentElement.hasAttribute("data-draft-id")) {
             var focused_draft = document.activeElement.parentElement.getAttribute("data-draft-id");
             drafts.restore_draft(focused_draft);
        } else {
            var draft_id_list = Object.getOwnPropertyNames(draft_list);
            var first_draft = draft_id_list[draft_id_list.length-1];
            drafts.restore_draft(first_draft);
        }
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

    if (current_msg_list.empty()) {
        return false;
    }

    // If we got this far, then we're presumably in the message
    // view and there is a "current" message, so in that case
    // "enter" is the hotkey to respond to a message.  Note that
    // "r" has same effect, but that is handled in process_hotkey().
    compose.respond_to_message({trigger: 'hotkey enter'});
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
        case 'esc_ctrl':
            return exports.process_escape_key(e);
    }

    if (drafts.drafts_overlay_open()) {
        drafts.drafts_handle_events(e, event_name);
    }

    if (hotkey.message_view_only && ui_state.home_tab_obscured()) {
        if ((event_name === 'up_arrow' || event_name === 'down_arrow') && exports.is_subs()) {
            subs.switch_rows(event_name);
            return true;
        }
        return false;
    }

    if (exports.is_editing_stream_name(e)) {
        // We handle the enter key in process_enter_key().
        // We ignore all other keys.
        return false;
    }

    var tab_list;

    if (event_name === "up_arrow") {
        tab_list = exports.tab_up_down(e);
        if (tab_list.flag) {
            tab_list.prev().focus();
            return true;
        }
    }

    if (event_name === "down_arrow") {
        tab_list = exports.tab_up_down(e);
        if (tab_list.flag) {
            tab_list.next().focus();
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

    if (exports.is_settings_page()) {
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
        }
        return false;
    }

    // Process hotkeys specially when in an input, select, textarea, or send button
    if (exports.processing_text()) {
        // Note that there is special handling for enter/escape too, but
        // we handle this in other functions.

        if (event_name === 'left_arrow' && focus_in_empty_compose()) {
            message_edit.edit_last_sent_message();
            return true;
        }

        if ((event_name === 'up_arrow' || event_name === 'down_arrow') && focus_in_empty_compose()) {
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
        if (exports.is_lightbox_open()) {
            lightbox.prev();
            return true;
        } else if (exports.is_subs()) {
            subs.toggle_view(event_name);
            return true;
        }

        message_edit.edit_last_sent_message();
        return true;
    }

    if (event_name === 'right_arrow') {
        if (exports.is_lightbox_open()) {
            lightbox.next();
            return true;
        } else if (exports.is_subs()) {
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
            ui.show_info_overlay("keyboard-shortcuts");
            return true;
        case 'stream_cycle_backward':
            navigate.cycle_stream('backward');
            return true;
        case 'stream_cycle_forward':
            navigate.cycle_stream('forward');
            return true;
        case 'keyboard_sub':
            if (exports.is_subs()) {
                subs.keyboard_sub();
            }
            return true;
        case 'view_selected_stream':
            if (exports.is_subs()) {
                subs.view_stream();
            }
            return true;
        case 'new_stream':
            if (exports.is_subs()) {
                subs.new_stream_clicked();
            }
            return true;
        case 'open_drafts':
            drafts.toggle();
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
        case 'reply_message': // 'r': respond to message
            // Note that you can "enter" to respond to messages as well,
            // but that is handled in process_enter_key().
            compose.respond_to_message({trigger: 'hotkey'});
            return true;
        case 'respond_to_author': // 'R': respond to author
            compose.respond_to_message({reply_type: "personal", trigger: 'hotkey pm'});
            return true;
        case 'compose_reply_with_mention': // '@': respond to message with mention to author
            compose.reply_with_mention({trigger: 'hotkey'});
            return true;
        case 'show_lightbox':
            lightbox.show_from_selected_message();
            return true;
        case 'open_reactions': // ':': open reactions to message
            open_reactions();
            return true;
        case 'thumbs_up_emoji': // '+': reacts with thumbs up emoji on selected message
            reactions.toggle_reaction(msg.id, '+1');
            return true;
        case 'toggle_mute':
            muting_ui.toggle_mute(msg);
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
