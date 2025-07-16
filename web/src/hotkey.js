import $ from "jquery";
import assert from "minimalistic-assert";

import * as activity from "./activity.ts";
import * as activity_ui from "./activity_ui.ts";
import * as browser_history from "./browser_history.ts";
import * as color_picker_popover from "./color_picker_popover.ts";
import * as common from "./common.ts";
import * as compose from "./compose.js";
import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_reply from "./compose_reply.ts";
import * as compose_send_menu_popover from "./compose_send_menu_popover.js";
import * as compose_state from "./compose_state.ts";
import * as compose_textarea from "./compose_textarea.ts";
import * as condense from "./condense.ts";
import * as deprecated_feature_notice from "./deprecated_feature_notice.ts";
import * as drafts_overlay_ui from "./drafts_overlay_ui.ts";
import * as emoji from "./emoji.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as feedback_widget from "./feedback_widget.ts";
import * as gear_menu from "./gear_menu.ts";
import * as giphy from "./giphy.ts";
import * as hash_util from "./hash_util.ts";
import * as hashchange from "./hashchange.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as lightbox from "./lightbox.ts";
import * as list_util from "./list_util.ts";
import * as message_actions_popover from "./message_actions_popover.ts";
import * as message_edit from "./message_edit.ts";
import * as message_edit_history from "./message_edit_history.ts";
import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import * as message_view from "./message_view.ts";
import * as modals from "./modals.ts";
import * as narrow_state from "./narrow_state.ts";
import * as navbar_menus from "./navbar_menus.ts";
import * as navigate from "./navigate.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as playground_links_popover from "./playground_links_popover.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as reactions from "./reactions.ts";
import * as read_receipts from "./read_receipts.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as recent_view_util from "./recent_view_util.ts";
import * as reminders_overlay_ui from "./reminders_overlay_ui.ts";
import * as scheduled_messages_overlay_ui from "./scheduled_messages_overlay_ui.ts";
import * as search from "./search.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as spectators from "./spectators.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import {realm} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_popover from "./stream_popover.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as topic_list from "./topic_list.ts";
import * as unread_ops from "./unread_ops.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_popover from "./user_group_popover.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics_ui from "./user_topics_ui.ts";

function do_narrow_action(action) {
    if (message_lists.current === undefined) {
        return false;
    }

    action(message_lists.current.selected_id(), {trigger: "hotkey"});
    return true;
}

// For message actions and user profile menu.
const menu_dropdown_hotkeys = new Set(["down_arrow", "up_arrow", "vim_up", "vim_down", "enter"]);

const color_picker_hotkeys = new Set([
    "down_arrow",
    "up_arrow",
    "left_arrow",
    "right_arrow",
    "vim_up",
    "vim_down",
    "vim_left",
    "vim_right",
    "enter",
]);

// A set of characters that, on many keyboard layouts, require 'Shift' modifier key
// to type, or where pressing the key with a 'Shift' modifier is expected to produce
// a different character. We ignore the 'Shift' modifier when processing these keys,
// and disallow assigning hotkeys that involve 'Shift' modifier combined with them.
const KNOWN_IGNORE_SHIFT_MODIFIER_KEYS = new Set([
    "*",
    "+",
    "=",
    "-",
    "/",
    ":",
    "<",
    ">",
    "?",
    "@",
]);

// Note that multiple keys can map to the same event_name, which
// we'll do in cases where they have the exact same semantics.
// DON'T FORGET: update keyboard_shortcuts.html

// The `message_view_only` property is a convenient and performant way
// to express a common case of which hotkeys do something in which
// views.  It is set for hotkeys (like `Ctrl + S`) that only have an effect
// in the main message view with a selected message.
// `message_view_only` hotkeys, as a group, are not processed if any
// overlays are open (e.g. settings, streams, etc.).
const KEYDOWN_MAPPINGS = {
    "Alt+P": {name: "toggle_compose_preview", message_view_only: true},
    "Ctrl+[": {name: "escape", message_view_only: false},
    "Cmd+Enter": {name: "action_with_enter", message_view_only: true},
    "Cmd+C": {name: "copy_with_c", message_view_only: false},
    "Cmd+K": {name: "search_with_k", message_view_only: false},
    "Cmd+S": {name: "star_message", message_view_only: true},
    "Cmd+.": {name: "narrow_to_compose_target", message_view_only: true},
    "Cmd+'": {name: "open_saved_snippet_dropdown", message_view_only: true},
    "Ctrl+Enter": {name: "action_with_enter", message_view_only: true},
    "Ctrl+C": {name: "copy_with_c", message_view_only: false},
    "Ctrl+K": {name: "search_with_k", message_view_only: false},
    "Ctrl+S": {name: "star_message", message_view_only: true},
    "Ctrl+.": {name: "narrow_to_compose_target", message_view_only: true},
    "Ctrl+'": {name: "open_saved_snippet_dropdown", message_view_only: true},
    "Shift+A": {name: "stream_cycle_backward", message_view_only: true},
    "Shift+C": {name: "C_deprecated", message_view_only: true},
    "Shift+D": {name: "stream_cycle_forward", message_view_only: true},
    "Shift+G": {name: "G_end", message_view_only: true},
    "Shift+H": {name: "view_edit_history", message_view_only: true},
    "Shift+I": {name: "open_inbox", message_view_only: true},
    "Shift+J": {name: "vim_page_down", message_view_only: true},
    "Shift+K": {name: "vim_page_up", message_view_only: true},
    "Shift+M": {name: "toggle_topic_visibility_policy", message_view_only: true},
    "Shift+N": {name: "narrow_to_next_unread_followed_topic", message_view_only: false},
    "Shift+P": {name: "narrow_private", message_view_only: true},
    "Shift+R": {name: "respond_to_author", message_view_only: true},
    "Shift+S": {name: "toggle_stream_subscription", message_view_only: true},
    "Shift+U": {name: "mark_unread", message_view_only: true},
    "Shift+V": [
        {name: "view_selected_stream", message_view_only: false},
        {name: "toggle_read_receipts", message_view_only: true},
    ],
    "Shift+Tab": {name: "shift_tab", message_view_only: false},
    "Shift+ ": {name: "shift_spacebar", message_view_only: true},
    "Shift+ArrowLeft": {name: "left_arrow", message_view_only: false},
    "Shift+ArrowRight": {name: "right_arrow", message_view_only: false},
    "Shift+ArrowUp": {name: "up_arrow", message_view_only: false},
    "Shift+ArrowDown": {name: "down_arrow", message_view_only: false},
    // The shortcut "A" dates from when this was called "All messages".
    A: {name: "open_combined_feed", message_view_only: true},
    C: {name: "compose", message_view_only: true},
    D: {name: "open_drafts", message_view_only: true},
    E: {name: "edit_message", message_view_only: true},
    G: {name: "gear_menu", message_view_only: true},
    H: {name: "vim_left", message_view_only: true},
    I: {name: "message_actions", message_view_only: true},
    J: {name: "vim_down", message_view_only: true},
    K: {name: "vim_up", message_view_only: true},
    L: {name: "vim_right", message_view_only: true},
    M: {name: "move_message", message_view_only: true},
    N: {name: "n_key", message_view_only: false},
    P: {name: "p_key", message_view_only: false},
    Q: {name: "query_streams", message_view_only: true},
    R: {name: "reply_message", message_view_only: true},
    S: {name: "toggle_conversation_view", message_view_only: true},
    T: {name: "open_recent_view", message_view_only: true},
    U: {name: "toggle_sender_info", message_view_only: true},
    V: {name: "show_lightbox", message_view_only: true},
    W: {name: "query_users", message_view_only: true},
    X: {name: "compose_private_message", message_view_only: true},
    Y: {name: "list_of_channel_topics", message_view_only: true},
    Z: {name: "zoom_to_message_near", message_view_only: true},
    Tab: {name: "tab", message_view_only: false},
    Escape: {name: "escape", message_view_only: false},
    " ": {name: "spacebar", message_view_only: true},
    PageUp: {name: "page_up", message_view_only: true},
    PageDown: {name: "page_down", message_view_only: true},
    End: {name: "end", message_view_only: true},
    Home: {name: "home", message_view_only: true},
    ArrowLeft: {name: "left_arrow", message_view_only: false},
    ArrowRight: {name: "right_arrow", message_view_only: false},
    ArrowUp: {name: "up_arrow", message_view_only: false},
    ArrowDown: {name: "down_arrow", message_view_only: false},
    "*": {name: "open_starred_message_view", message_view_only: true},
    "+": {name: "thumbs_up_emoji", message_view_only: true},
    "=": {name: "upvote_first_emoji", message_view_only: true},
    "-": {name: "toggle_message_collapse", message_view_only: true},
    "/": {name: "search", message_view_only: false},
    ":": {name: "toggle_reactions_popover", message_view_only: true},
    "<": {name: "compose_forward_message", message_view_only: true},
    ">": {name: "compose_quote_message", message_view_only: true},
    "?": {name: "show_shortcuts", message_view_only: false},
    "@": {name: "compose_reply_with_mention", message_view_only: true},
    // these can be triggered by key or Shift + key
    //
    // We may want to revisit both of these. For Backspace, we don't
    // have any specific mapping behavior; we are just trying to disable
    // the normal browser features for certain OSes when we are in the
    // compose box, and the little bit of Backspace-related code here is
    // dubious, but may apply to Shift-Backspace.
    // For Enter, there is some possibly that Shift-Enter is intended to
    // have special behavior for folks that are used to Shift-Enter behavior
    // in other apps, but that's also slightly dubious.
    Backspace: {name: "backspace", message_view_only: true},
    Enter: {name: "enter", message_view_only: false},
    Delete: {name: "delete", message_view_only: false},
    "Shift+Backspace": {name: "backspace", message_view_only: true},
    "Shift+Enter": {name: "enter", message_view_only: false},
    "Shift+Delete": {name: "delete", message_view_only: false},
};

const KNOWN_NAMED_KEY_ATTRIBUTE_VALUES = new Set([
    "Alt",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "Backspace",
    "Control",
    "Delete",
    "End",
    "Enter",
    "Escape",
    "Home",
    "Meta",
    "PageDown",
    "PageUp",
    "Shift",
    "Tab",
]);

const CODE_TO_QWERTY_CHAR = {
    KeyA: "a",
    KeyB: "b",
    KeyC: "c",
    KeyD: "d",
    KeyE: "e",
    KeyF: "f",
    KeyG: "g",
    KeyH: "h",
    KeyI: "i",
    KeyJ: "j",
    KeyK: "k",
    KeyL: "l",
    KeyM: "m",
    KeyN: "n",
    KeyO: "o",
    KeyP: "p",
    KeyQ: "q",
    KeyR: "r",
    KeyS: "s",
    KeyT: "t",
    KeyU: "u",
    KeyV: "v",
    KeyW: "w",
    KeyX: "x",
    KeyY: "y",
    KeyZ: "z",
    "Shift+KeyA": "A",
    "Shift+KeyB": "B",
    "Shift+KeyC": "C",
    "Shift+KeyD": "D",
    "Shift+KeyE": "E",
    "Shift+KeyF": "F",
    "Shift+KeyG": "G",
    "Shift+KeyH": "H",
    "Shift+KeyI": "I",
    "Shift+KeyJ": "J",
    "Shift+KeyK": "K",
    "Shift+KeyL": "L",
    "Shift+KeyM": "M",
    "Shift+KeyN": "N",
    "Shift+KeyO": "O",
    "Shift+KeyP": "P",
    "Shift+KeyQ": "Q",
    "Shift+KeyR": "R",
    "Shift+KeyS": "S",
    "Shift+KeyT": "T",
    "Shift+KeyU": "U",
    "Shift+KeyV": "V",
    "Shift+KeyW": "W",
    "Shift+KeyX": "X",
    "Shift+KeyY": "Y",
    "Shift+KeyZ": "Z",
    BracketLeft: "[",
    Equal: "=",
    Minus: "-",
    Period: ".",
    Quote: "'",
    "Shift+Comma": "<",
    "Shift+Digit2": "@",
    "Shift+Digit8": "*",
    "Shift+Equal": "+",
    "Shift+Period": ">",
    "Shift+Semicolon": ":",
    "Shift+Slash": "?",
    Slash: "/",
    Space: " ",
};

// Keyboard Event Viewer tool:
// https://w3c.github.io/uievents/tools/key-event-viewer.html
export function get_keydown_hotkey(e) {
    // Determine the key pressed in a consistent way.
    //
    // For keyboard layouts (e.g. QWERTY) where `e.key` results
    // in printable ASCII characters or named key attribute values
    // like "Tab", "Enter", etc., we use `e.key` directly.
    //
    // However, for layouts where the character defined for a hotkey
    // can't be typed directly (e.g. 'a' in Cyrillic), users press
    // the same physical key combination that a QWERTY user would
    // use (e.g. 'ф' on Cyrillic maps to 'a' on QWERTY). In such cases,
    // we derive the QWERTY equivalent using `e.code` and the `CODE_TO_QWERTY_CHAR` map.
    const use_event_key =
        common.is_printable_ascii(e.key) || KNOWN_NAMED_KEY_ATTRIBUTE_VALUES.has(e.key);
    let key = e.key;
    if (!use_event_key) {
        const code = `${e.shiftKey ? "Shift+" : ""}${e.code}`;
        key = CODE_TO_QWERTY_CHAR[code];
    }

    if (common.has_mac_keyboard() && e.ctrlKey && key !== "[") {
        // On macOS, Cmd is used instead of Ctrl. Except 'Ctrl + ['.
        return undefined;
    }
    if (!common.has_mac_keyboard() && e.metaKey) {
        return undefined;
    }

    // Make lowercase a-z uppercase; leave others unchanged.
    // We distinguish between 'a' and 'A' as 'A' vs 'Shift+A'.
    // This helps to avoid Caps Lock affecting shortcuts.
    if (/^[a-z]$/.test(key)) {
        key = key.toUpperCase();
    }

    if (e.shiftKey && !KNOWN_IGNORE_SHIFT_MODIFIER_KEYS.has(key)) {
        key = "Shift+" + key;
    }
    if (e.altKey) {
        key = "Alt+" + key;
    }
    if (e.ctrlKey) {
        key = "Ctrl+" + key;
    }
    if (e.metaKey) {
        assert(common.has_mac_keyboard());
        key = "Cmd+" + key;
    }

    return KEYDOWN_MAPPINGS[key];
}

export let processing_text = () => {
    const $focused_elt = $(":focus");
    return (
        $focused_elt.is("input") ||
        $focused_elt.is("select") ||
        $focused_elt.is("textarea") ||
        $focused_elt.parents(".pill-container").length > 0 ||
        $focused_elt.attr("id") === "compose-send-button" ||
        $focused_elt.parents(".dropdown-list-container").length > 0
    );
};

export function rewire_processing_text(value) {
    processing_text = value;
}

export function in_content_editable_widget(e) {
    return $(e.target).is(".editable-section");
}

// Returns true if we handled it, false if the browser should.
export function process_escape_key(e) {
    if (
        recent_view_ui.is_in_focus() &&
        // This will return false if `e.target` is not
        // any of the Recent Conversations elements by design.
        recent_view_ui.change_focused_element($(e.target), "escape")
    ) {
        // Recent Conversations uses escape to switch focus from
        // search / filters to the conversations table. If focus is
        // already on the table, it returns false.
        return true;
    }

    if (inbox_ui.is_in_focus() && inbox_ui.change_focused_element("escape")) {
        return true;
    }

    if (feedback_widget.is_open()) {
        feedback_widget.dismiss();
        return true;
    }

    if (popovers.any_active()) {
        popovers.hide_all();
        return true;
    }

    if (modals.any_active()) {
        modals.close_active();
        return true;
    }

    if (overlays.any_active()) {
        overlays.close_active();
        return true;
    }

    if (navbar_menus.any_focused()) {
        navbar_menus.blur_focused();
        return true;
    }

    if (processing_text()) {
        if (activity_ui.searching()) {
            activity_ui.clear_search();
            return true;
        }

        if (stream_list.searching()) {
            stream_list.clear_and_hide_search();
            return true;
        }

        // Emoji picker goes before compose so compose emoji picker is closed properly.
        if (emoji_picker.is_open()) {
            emoji_picker.hide_emoji_popover();
            return true;
        }

        if (giphy.is_popped_from_edit_message()) {
            giphy.focus_current_edit_message();
            // Hide after setting focus so that `edit_message_id` is
            // still set in giphy.
            giphy.hide_giphy_popover();
            return true;
        }

        // When the input is focused, we blur and clear the input. A second "Esc"
        // will zoom out, handled below.
        if (stream_list.is_zoomed_in() && $("#topic_filter_query").is(":focus")) {
            topic_list.clear_topic_search(e);
            return true;
        }

        if (pm_list.is_zoomed_in() && $(".direct-messages-list-filter").is(":focus")) {
            pm_list.clear_search();
            return true;
        }

        if (compose_state.composing()) {
            // Check if the giphy popover was open using compose box.
            // Hide GIPHY popover if it's open.
            if (!giphy.is_popped_from_edit_message() && giphy.hide_giphy_popover()) {
                $("textarea#compose-textarea").trigger("focus");
                return true;
            }

            // Check for errors in compose box; close errors if they exist
            if ($("main-view-banner").length > 0) {
                compose_banner.clear_all();
                return true;
            }

            // If the user hit the Esc key, cancel the current compose
            compose_actions.cancel();
            return true;
        }

        // We pressed Esc and something was focused, and the composebox
        // wasn't open. In that case, we should blur the input.
        $("input:focus,textarea:focus").trigger("blur");
        return true;
    }

    if (sidebar_ui.any_sidebar_expanded_as_overlay()) {
        sidebar_ui.hide_all();
        return true;
    }

    if (compose_state.composing()) {
        compose_actions.cancel();
        return true;
    }

    if (stream_list.is_zoomed_in()) {
        stream_list.zoom_out();
        return true;
    }

    /* The Ctrl+[ hotkey navigates to the home view
     * unconditionally; Esc's behavior depends on a setting. */
    if (user_settings.web_escape_navigates_to_home_view || e.key === "[") {
        const triggered_by_escape_key = true;
        hashchange.set_hash_to_home_view(triggered_by_escape_key);
        return true;
    }

    return false;
}

function handle_popover_events(event_name) {
    const popover_menu_visible_instance = popover_menus.get_visible_instance();

    if (popover_menus.is_stream_actions_popover_displayed()) {
        stream_popover.stream_sidebar_menu_handle_keyboard(event_name);
        return true;
    }

    if (popover_menu_visible_instance) {
        popover_menus.sidebar_menu_instance_handle_keyboard(
            popover_menu_visible_instance,
            event_name,
        );
        return true;
    }

    if (user_card_popover.message_user_card.is_open()) {
        user_card_popover.message_user_card.handle_keyboard(event_name);
        return true;
    }

    if (user_card_popover.user_card.is_open()) {
        user_card_popover.user_card.handle_keyboard(event_name);
        return true;
    }

    if (user_card_popover.user_sidebar.is_open()) {
        user_card_popover.user_sidebar.handle_keyboard(event_name);
        return true;
    }

    if (user_group_popover.is_open()) {
        user_group_popover.handle_keyboard(event_name);
        return true;
    }

    if (playground_links_popover.is_open()) {
        playground_links_popover.handle_keyboard(event_name);
        return true;
    }

    return false;
}

// Returns true if we handled it, false if the browser should.
export function process_enter_key(e) {
    if (popovers.any_active() && $(e.target).hasClass("navigate-link-on-enter")) {
        // If a popover is open and we pressed Enter on a menu item,
        // call click directly on the item to navigate to the `href`.
        // trigger("click") doesn't work for them to navigate to `href`.
        e.target.click();
        e.preventDefault();
        popovers.hide_all();
        return true;
    }

    if (emoji_picker.is_open()) {
        return emoji_picker.navigate("enter", e);
    }

    if (handle_popover_events("enter")) {
        return true;
    }

    if (overlays.settings_open()) {
        // On the settings page just let the browser handle
        // the Enter key for things like submitting forms.
        return false;
    }

    if (overlays.streams_open()) {
        return false;
    }

    if (processing_text()) {
        if (stream_list.searching()) {
            // This is sort of funny behavior, but I think
            // the intention is that we want it super easy
            // to close stream search.
            stream_list.clear_and_hide_search();
            return true;
        }

        // Don't send the message if topic box is focused.
        if (compose.is_topic_input_focused()) {
            return true;
        }

        return false;
    }

    // This handles when pressing Enter while looking at drafts.
    // It restores draft that is focused.
    if (overlays.drafts_open()) {
        drafts_overlay_ui.handle_keyboard_events("enter");
        return true;
    }

    if (overlays.scheduled_messages_open()) {
        scheduled_messages_overlay_ui.handle_keyboard_events("enter");
        return true;
    }

    if (overlays.reminders_open()) {
        reminders_overlay_ui.handle_keyboard_events("enter");
        return true;
    }

    // Transfer the enter keypress from button to the `<i>` tag inside
    // it since it is the trigger for the popover. <button> is already used
    // to trigger the tooltip so it cannot be used to trigger the popover.
    if (e.target.id === "send_later") {
        compose_send_menu_popover.toggle();
        return true;
    }

    if ($(e.target).attr("role") === "button") {
        e.target.click();
        return true;
    }

    // All custom logic for overlays/modals is above; if we're in a
    // modal at this point, let the browser handle the event.
    if (modals.any_active()) {
        return false;
    }

    // If we're on a button or a link and have pressed Enter, let the
    // browser handle the keypress
    //
    // This is subtle and here's why: Suppose you have the focus on a
    // stream name in your left sidebar. j and k will still move your
    // cursor up and down, but Enter won't reply -- it'll just trigger
    // the link on the sidebar! So you keep pressing Enter over and
    // over again. Until you click somewhere or press r.
    if ($("a:focus,button:focus").length > 0) {
        return false;
    }

    if ($("#compose").hasClass("preview_mode")) {
        compose.handle_enter_key_with_preview_open();
        return true;
    }

    if (recent_view_util.is_visible()) {
        if (e.target === $("body")[0]) {
            // There's a race when using `Esc` and `Enter` to navigate to
            // Recent Conversations and then navigate to the next topic, wherein
            // Recent Conversations won't have applied focus to its table yet.
            //
            // Recent Conversations' own navigation just lets `Enter` be
            // treated as a click on the highlighted message, so we
            // don't need to do anything there. But if nothing is
            // focused (say, during the race or after clicking on the
            // sidebars, it's worth focusing the table so that hitting
            // `Enter` again will navigate you somewhere.
            const focus_changed = recent_view_ui.revive_current_focus();
            return focus_changed;
        }

        // Never fall through to opening the compose box to reply.
        return false;
    }

    if (!narrow_state.is_message_feed_visible()) {
        return false;
    }

    // For search views, renarrow to the current message's
    // conversation.
    const current_filter = narrow_state.filter();
    if (current_filter !== undefined && !current_filter.contains_no_partial_conversations()) {
        assert(message_lists.current !== undefined);
        const message = message_lists.current.selected_message();

        if (message === undefined) {
            // No selected message.
            return false;
        }

        window.location = hash_util.by_conversation_and_time_url(message);
        return true;
    }

    compose_reply.respond_to_message({trigger: "hotkey enter"});
    return true;
}

export function process_cmd_or_ctrl_enter_key() {
    if ($("#compose").hasClass("preview_mode")) {
        const cmd_or_ctrl_pressed = true;
        compose.handle_enter_key_with_preview_open(cmd_or_ctrl_pressed);
        return true;
    }

    return false;
}

export function process_tab_key() {
    // Returns true if we handled it, false if the browser should.
    // TODO: See if browsers like Safari can now handle tabbing correctly
    // without our intervention.

    let $message_edit_form;

    const $focused_message_edit_content = $(".message_edit_content:focus");
    if ($focused_message_edit_content.length > 0) {
        $message_edit_form = $focused_message_edit_content.closest(".message_edit_form");
        // Open message edit forms either have a save button or a close button, but not both.
        $message_edit_form.find(".message_edit_save,.message_edit_close").trigger("focus");
        return true;
    }

    const $focused_message_edit_save = $(".message_edit_save:focus");
    if ($focused_message_edit_save.length > 0) {
        $message_edit_form = $focused_message_edit_save.closest(".message_edit_form");
        $message_edit_form.find(".message_edit_cancel").trigger("focus");
        return true;
    }

    if (emoji_picker.is_open()) {
        return emoji_picker.navigate("tab");
    }

    return false;
}

export function process_shift_tab_key() {
    // Returns true if we handled it, false if the browser should.
    // TODO: See if browsers like Safari can now handle tabbing correctly
    // without our intervention.

    if ($("#compose-send-button").is(":focus")) {
        // Shift-Tab: go back to content textarea and restore
        // cursor position.
        compose_textarea.restore_compose_cursor();
        return true;
    }

    // Shift-Tabbing from the edit message cancel button takes you to save.
    if ($(".message_edit_cancel:focus").length > 0) {
        $(".message_edit_save").trigger("focus");
        return true;
    }

    // Shift-Tabbing from the edit message save button takes you to the content.
    const $focused_message_edit_save = $(".message_edit_save:focus");
    if ($focused_message_edit_save.length > 0) {
        $focused_message_edit_save
            .closest(".message_edit_form")
            .find(".message_edit_content")
            .trigger("focus");
        return true;
    }

    // Shift-Tabbing from emoji catalog/search results takes you back to search textbox.
    if (emoji_picker.is_open()) {
        return emoji_picker.navigate("shift_tab");
    }

    if ($("input#stream_message_recipient_topic").is(":focus")) {
        compose_recipient.toggle_compose_recipient_dropdown();
        return true;
    }

    return false;
}

// Process a keydown event.
//
// Returns true if we handled it, false if the browser should.
export function process_hotkey(e, hotkey) {
    const event_name = hotkey.name;

    // This block needs to be before the `Tab` handler.
    switch (event_name) {
        case "up_arrow":
        case "down_arrow":
        case "left_arrow":
        case "right_arrow":
        case "page_down":
        case "page_up":
        case "vim_up":
        case "vim_down":
        case "vim_left":
        case "vim_right":
        case "tab":
        case "shift_tab":
        case "open_recent_view":
            if (recent_view_ui.is_in_focus()) {
                return recent_view_ui.change_focused_element($(e.target), event_name);
            }
    }

    switch (event_name) {
        case "up_arrow":
        case "down_arrow":
        case "left_arrow":
        case "right_arrow":
        case "tab":
        case "shift_tab":
        case "vim_up":
        case "vim_down":
        case "vim_left":
        case "vim_right":
        case "page_up":
        case "page_down":
            if (inbox_ui.is_in_focus()) {
                return inbox_ui.change_focused_element(event_name);
            }
    }

    // We handle the most complex keys in their own functions.
    switch (event_name) {
        case "escape":
            return process_escape_key(e);
        case "enter":
            return process_enter_key(e);
        case "action_with_enter":
            return process_cmd_or_ctrl_enter_key(e);
        case "tab":
            return process_tab_key();
        case "shift_tab":
            return process_shift_tab_key();
    }

    // This block needs to be before the open modals check, because
    // the "user status" modal can show the emoji picker.
    if (emoji_picker.is_open()) {
        return emoji_picker.navigate(event_name);
    }

    // modals.any_active() and modals.active_modal() both query the dom to
    // find and retrieve any active modal. Thus, we limit the number of calls
    // to the DOM by storing these values as constants to be reused.
    const is_any_modal_active = modals.any_active();
    const active_modal = is_any_modal_active ? modals.active_modal() : null;

    // `list_util` will process the event in send later modal.
    if (is_any_modal_active && active_modal !== "#send_later_modal") {
        if (event_name === "toggle_read_receipts" && active_modal === "#read_receipts_modal") {
            read_receipts.hide_user_list();
            return true;
        }
        return false;
    }

    // TODO: break out specific handlers for up_arrow,
    //       down_arrow, and backspace
    switch (event_name) {
        case "up_arrow":
        case "down_arrow":
        case "vim_up":
        case "vim_down":
        case "backspace":
        case "delete":
            if (overlays.drafts_open()) {
                drafts_overlay_ui.handle_keyboard_events(event_name);
                return true;
            }
            if (overlays.scheduled_messages_open()) {
                scheduled_messages_overlay_ui.handle_keyboard_events(event_name);
                return true;
            }
            if (overlays.reminders_open()) {
                reminders_overlay_ui.handle_keyboard_events(event_name);
                return true;
            }
            if (overlays.message_edit_history_open()) {
                message_edit_history.handle_keyboard_events(event_name);
                return true;
            }
    }

    if (hotkey.message_view_only && overlays.any_active()) {
        if (processing_text()) {
            return false;
        }
        if (event_name === "toggle_stream_subscription" && overlays.streams_open()) {
            stream_settings_ui.keyboard_sub();
            return true;
        }
        if (event_name === "show_lightbox" && overlays.lightbox_open()) {
            overlays.close_overlay("lightbox");
            return true;
        }
        if (event_name === "open_drafts" && overlays.drafts_open()) {
            overlays.close_overlay("drafts");
            return true;
        }
        return false;
    }

    if (overlays.settings_open() && !user_card_popover.user_card.is_open()) {
        return false;
    }

    if (overlays.info_overlay_open()) {
        if (event_name === "show_shortcuts") {
            overlays.close_active();
            return true;
        }
        return false;
    }

    // We don't treat the color picker like our menu popovers, since it
    // supports sideways navigation (left and right arrow).
    if (color_picker_hotkeys.has(event_name) && popover_menus.is_color_picker_popover_displayed()) {
        color_picker_popover.handle_keyboard(event_name);
        return true;
    }

    if ((event_name === "up_arrow" || event_name === "down_arrow") && overlays.streams_open()) {
        return stream_settings_ui.switch_rows(event_name);
    }

    if (event_name === "up_arrow" && list_util.inside_list(e)) {
        list_util.go_up(e);
        return true;
    }

    if (event_name === "down_arrow" && list_util.inside_list(e)) {
        list_util.go_down(e);
        return true;
    }

    if (event_name === "toggle_compose_preview") {
        const $last_focused_compose_type_input = $(
            compose_state.get_last_focused_compose_type_input(),
        );

        if ($last_focused_compose_type_input.hasClass("message_edit_content")) {
            if ($last_focused_compose_type_input.closest(".preview_mode").length > 0) {
                message_edit.clear_preview_area($last_focused_compose_type_input);
                $last_focused_compose_type_input.trigger("focus");
            } else {
                message_edit.show_preview_area($last_focused_compose_type_input);
            }
            return true;
        }

        if (compose_state.composing()) {
            if ($("#compose").hasClass("preview_mode")) {
                compose.clear_preview_area();
            } else {
                compose.show_preview_area();
            }
            return true;
        }
    }

    // Handle our normal popovers that are basically vertical lists of menu items.
    if (menu_dropdown_hotkeys.has(event_name) && handle_popover_events(event_name)) {
        return true;
    }

    // Handle the left arrow and right arrow keys to make it easy to
    // get into fancy sideways navigation on the navbar (top right corner).
    if (
        (navbar_menus.is_navbar_menus_displayed() || navbar_menus.any_focused()) &&
        navbar_menus.handle_keyboard_events(event_name)
    ) {
        return true;
    }

    // The next two sections date back to 00445c84 and are Mac/Chrome-specific,
    // and they should possibly be eliminated in favor of keeping standard
    // browser behavior.
    if (event_name === "backspace" && $("#compose-send-button").is(":focus")) {
        // Ignore Backspace; don't navigate back a page.
        return true;
    }

    if (event_name === "narrow_to_compose_target") {
        message_view.to_compose_target();
        return true;
    }

    // Process hotkeys specially when in an input, select, textarea, or send button
    if (processing_text()) {
        // Note that there is special handling for Enter/Esc too, but
        // we handle this in other functions.

        if (event_name === "open_saved_snippet_dropdown") {
            const $messagebox = $(":focus").parents(".messagebox");
            if ($messagebox.length === 1) {
                $messagebox.find(".saved_snippets_widget")[0].click();
            }
        }

        if (event_name === "left_arrow" && compose_state.focus_in_empty_compose()) {
            message_edit.edit_last_sent_message();
            return true;
        }

        if (event_name === "down_arrow" && $(":focus").attr("id") === "search_query") {
            $("#search_query").trigger("blur");
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.down(true);
        }

        if (event_name === "up_arrow" && $(":focus").attr("id") === "search_query") {
            $("#search_query").trigger("blur");
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.up(true);
        }

        if (
            ((event_name === "down_arrow" || event_name === "page_down" || event_name === "end") &&
                compose_state.focus_in_empty_compose()) ||
            ((event_name === "up_arrow" || event_name === "page_up" || event_name === "home") &&
                compose_state.focus_in_empty_compose(true))
        ) {
            compose_actions.cancel();
            // don't return, as we still want it to be picked up by the code below
        } else {
            switch (event_name) {
                case "page_up":
                    $(":focus").caret(0).animate({scrollTop: 0}, "fast");
                    return true;
                case "page_down": {
                    // so that it always goes to the end of the text box.
                    const height = $(":focus")[0].scrollHeight;
                    $(":focus")
                        .caret(Number.POSITIVE_INFINITY)
                        .animate({scrollTop: height}, "fast");
                    return true;
                }
                case "search_with_k":
                    // Do nothing; this allows one to use Ctrl+K inside compose.
                    break;
                case "star_message":
                    // Do nothing; this allows one to use Ctrl+S inside compose.
                    break;
                default:
                    // Let the browser handle the key normally.
                    return false;
            }
        }
    }

    if (event_name === "left_arrow") {
        if (overlays.lightbox_open()) {
            lightbox.prev();
            return true;
        } else if (overlays.streams_open()) {
            stream_settings_ui.toggle_view(event_name);
            return true;
        } else if (compose_state.focus_in_formatting_buttons()) {
            // Allow left arrow to scroll the formatting buttons backward
            return false;
        }

        message_edit.edit_last_sent_message();
        return true;
    }

    if (event_name === "right_arrow") {
        if (overlays.lightbox_open()) {
            lightbox.next();
            return true;
        } else if (overlays.streams_open()) {
            stream_settings_ui.toggle_view(event_name);
            return true;
        }
    }

    // Prevent navigation in the background when the overlays are active.
    if (overlays.any_active() || is_any_modal_active) {
        if (event_name === "view_selected_stream" && overlays.streams_open()) {
            stream_settings_ui.view_stream();
            return true;
        }
        if (
            event_name === "n_key" &&
            overlays.streams_open() &&
            (settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams())
        ) {
            stream_settings_ui.open_create_stream();
            return true;
        }
        return false;
    }

    // Shortcuts that don't require a message
    let list_of_channel_topics_channel_id;
    switch (event_name) {
        case "narrow_private":
            message_view.show(
                [
                    {
                        operator: "is",
                        operand: "dm",
                    },
                ],
                {trigger: "hotkey"},
            );
            return true;
        case "query_streams":
            if (pm_list.is_zoomed_in()) {
                pm_list.focus_pm_search_filter();
            } else if (stream_list.is_zoomed_in()) {
                topic_list.focus_topic_search_filter();
            } else {
                stream_list.initiate_search();
            }
            return true;
        case "query_users":
            if (page_params.is_spectator) {
                return false;
            }
            activity_ui.initiate_search();
            return true;
        case "search":
        case "search_with_k":
            search.initiate_search();
            return true;
        case "gear_menu":
            gear_menu.toggle();
            return true;
        case "show_shortcuts": // Show keyboard shortcuts page
            browser_history.go_to_location("keyboard-shortcuts");
            return true;
        case "stream_cycle_backward":
            message_view.stream_cycle_backward();
            return true;
        case "stream_cycle_forward":
            message_view.stream_cycle_forward();
            return true;
        case "n_key":
            message_view.narrow_to_next_topic({trigger: "hotkey", only_followed_topics: false});
            return true;
        case "narrow_to_next_unread_followed_topic":
            message_view.narrow_to_next_topic({trigger: "hotkey", only_followed_topics: true});
            return true;
        case "p_key":
            message_view.narrow_to_next_pm_string({trigger: "hotkey"});
            return true;
        case "open_recent_view":
            browser_history.go_to_location("#recent");
            return true;
        case "open_inbox":
            browser_history.go_to_location("#inbox");
            return true;
        case "open_starred_message_view":
            browser_history.go_to_location("#narrow/is/starred");
            return true;
        case "open_combined_feed":
            browser_history.go_to_location("#feed");
            return true;
        case "toggle_topic_visibility_policy":
            if (recent_view_ui.is_in_focus()) {
                const recent_msg = recent_view_ui.get_focused_row_message();
                if (recent_msg !== undefined && recent_msg.type === "stream") {
                    user_topics_ui.toggle_topic_visibility_policy(recent_msg);
                    return true;
                }
            }
            if (inbox_ui.is_in_focus()) {
                return inbox_ui.toggle_topic_visibility_policy();
            }
            if (message_lists.current.selected_message()) {
                user_topics_ui.toggle_topic_visibility_policy(
                    message_lists.current.selected_message(),
                );
                return true;
            }
            return false;
        case "list_of_channel_topics":
            if (recent_view_ui.is_in_focus()) {
                const msg = recent_view_ui.get_focused_row_message();
                if (msg !== undefined && msg.type === "stream") {
                    list_of_channel_topics_channel_id = msg.stream_id;
                }
            }
            if (inbox_ui.is_in_focus()) {
                const msg = inbox_ui.get_focused_row_message();
                if (msg !== undefined && msg.msg_type === "stream") {
                    list_of_channel_topics_channel_id = msg.stream_id;
                }
            }
            if (message_lists.current !== undefined) {
                const selected_message = message_lists.current.selected_message();
                if (selected_message === undefined) {
                    const only_valid_id = true;
                    list_of_channel_topics_channel_id = narrow_state.stream_id(
                        narrow_state.filter(),
                        only_valid_id,
                    );
                } else if (selected_message.type === "stream") {
                    list_of_channel_topics_channel_id = selected_message.stream_id;
                }
            }

            if (list_of_channel_topics_channel_id === undefined) {
                return false;
            }

            browser_history.go_to_location(
                hash_util.by_channel_topic_list_url(list_of_channel_topics_channel_id),
            );
            return true;
    }

    // Shortcuts that are useful with an empty message feed, like opening compose.
    switch (event_name) {
        case "reply_message": // 'r': respond to message
            // Note that you can "Enter" to respond to messages as well,
            // but that is handled in process_enter_key().
            compose_reply.respond_to_message({trigger: "hotkey"});
            return true;
        case "compose": // 'c': compose
            if (!compose_state.composing()) {
                compose_actions.start({
                    message_type: "stream",
                    trigger: "compose_hotkey",
                    keep_composebox_empty: true,
                });
            }
            return true;
        case "compose_private_message":
            if (!compose_state.composing()) {
                compose_actions.start({
                    message_type: "private",
                    trigger: "compose_hotkey",
                    keep_composebox_empty: true,
                });
            }
            return true;
        case "open_drafts":
            browser_history.go_to_location("drafts");
            return true;
        case "C_deprecated":
            deprecated_feature_notice.maybe_show_deprecation_notice("Shift + C");
            return true;
    }

    // Hotkeys below this point are for the message feed, and so
    // should only function if the message feed is visible and nonempty.
    if (message_lists.current === undefined || message_lists.current.visibly_empty()) {
        return false;
    }

    // Shortcuts for navigation and other applications that require a
    // nonempty message feed but do not depend on the selected message.
    switch (event_name) {
        case "down_arrow":
        case "vim_down":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.down(true); // with_centering
            return true;
        case "up_arrow":
        case "vim_up":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.up();
            return true;
        case "home":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.to_home();
            return true;
        case "end":
        case "G_end":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.to_end();
            return true;
        case "page_up":
        case "vim_page_up":
        case "shift_spacebar":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.page_up();
            return true;
        case "page_down":
        case "vim_page_down":
        case "spacebar":
            message_scroll_state.set_keyboard_triggered_current_scroll(true);
            navigate.page_down();
            return true;
    }

    if (
        // Allow UI only features for spectators which they can perform.
        page_params.is_spectator &&
        ![
            "toggle_conversation_view",
            "show_lightbox",
            "toggle_sender_info",
            "edit_message",
        ].includes(event_name)
    ) {
        spectators.login_to_access();
        return true;
    }

    const msg = message_lists.current.selected_message();

    // Shortcuts that operate on a message
    switch (event_name) {
        case "message_actions":
            return message_actions_popover.toggle_message_actions_menu(msg);
        case "star_message":
            starred_messages_ui.toggle_starred_and_update_server(msg);
            return true;
        case "toggle_conversation_view":
            if (narrow_state.narrowed_by_topic_reply()) {
                // narrow to stream if user is in topic view
                return do_narrow_action(message_view.narrow_by_recipient);
            } else if (narrow_state.narrowed_by_pm_reply()) {
                // do nothing if user is in DM view
                return false;
            }
            // else narrow to conversation view (topic / DM)
            return do_narrow_action(message_view.narrow_by_topic);
        case "toggle_stream_subscription":
            deprecated_feature_notice.maybe_show_deprecation_notice("Shift + S");
            return true;
        case "respond_to_author": // 'R': respond to author
            compose_reply.respond_to_message({reply_type: "personal", trigger: "hotkey pm"});
            return true;
        case "compose_reply_with_mention": // '@': respond to message with mention to author
            compose_reply.reply_with_mention({trigger: "hotkey"});
            return true;
        case "show_lightbox":
            lightbox.show_from_selected_message();
            return true;
        case "toggle_sender_info":
            user_card_popover.toggle_sender_info();
            return true;
        // ':': open reactions to message
        case "toggle_reactions_popover": {
            const $row = message_lists.current.selected_row();
            const $emoji_icon = $row.find(".emoji-message-control-button-container");
            let emoji_picker_reference;
            if (
                $emoji_icon?.length !== 0 &&
                $emoji_icon.closest(".message_control_button").css("display") !== "none"
            ) {
                emoji_picker_reference = $emoji_icon[0];
            } else {
                emoji_picker_reference = $row.find(".message-actions-menu-button")[0];
            }

            emoji_picker.toggle_emoji_popover(emoji_picker_reference, msg.id, {
                placement: "bottom",
            });
            return true;
        }
        case "thumbs_up_emoji": {
            // '+': reacts with thumbs up emoji on selected message
            // Use canonical name.
            const thumbs_up_emoji_code = "1f44d";
            const canonical_name = emoji.get_emoji_name(thumbs_up_emoji_code);
            reactions.toggle_emoji_reaction(msg, canonical_name);
            return true;
        }
        case "upvote_first_emoji": {
            // '=': If the current message has at least one emoji
            // reaction, toggle out vote on the first one.
            const message_reactions = reactions.get_message_reactions(msg);
            if (message_reactions.length === 0) {
                return true;
            }

            const first_reaction = message_reactions[0];
            if (!first_reaction) {
                // If the message has no emoji reactions, do nothing.
                return true;
            }

            const canonical_name = emoji.get_emoji_name(first_reaction.emoji_code);
            // `canonical_name` will be `undefined` for custom emoji, so we can default
            // to the `emoji_name`.
            reactions.toggle_emoji_reaction(msg, canonical_name ?? first_reaction.emoji_name);
            return true;
        }
        case "toggle_message_collapse":
            condense.toggle_collapse(msg);
            return true;
        case "mark_unread":
            unread_ops.mark_as_unread_from_here(msg.id);
            return true;
        case "compose_quote_message": // > : respond to selected message with quote
            compose_reply.quote_message({trigger: "hotkey"});
            return true;
        case "compose_forward_message": // < : forward selected message
            compose_reply.quote_message({trigger: "hotkey", forward_message: true});
            return true;
        case "edit_message": {
            const $row = message_lists.current.get_row(msg.id);
            message_edit.start($row);
            return true;
        }
        case "view_edit_history": {
            if (
                realm.realm_message_edit_history_visibility_policy !==
                message_edit_history_visibility_policy_values.never.code
            ) {
                message_edit_history.fetch_and_render_message_history(msg);
                $("#message-history-overlay .exit-sign").trigger("focus");
                return true;
            }
            return false;
        }
        case "move_message": {
            if (!message_edit.can_move_message(msg)) {
                return false;
            }

            stream_popover.build_move_topic_to_stream_popover(msg.stream_id, msg.topic, false, msg);
            return true;
        }
        case "toggle_read_receipts": {
            read_receipts.show_user_list(msg.id);
            return true;
        }
        case "zoom_to_message_near": {
            // The following code is essentially equivalent to
            // `window.location = hashutil.by_conversation_and_time_url(msg)`
            // but we use `message_view.show` to pass in the `trigger` parameter
            switch (msg.type) {
                case "private":
                    message_view.show(
                        [
                            {operator: "dm", operand: msg.reply_to},
                            {operator: "near", operand: msg.id},
                        ],
                        {trigger: "hotkey"},
                    );
                    return true;
                case "stream":
                    message_view.show(
                        [
                            {
                                operator: "channel",
                                operand: msg.stream_id.toString(),
                            },
                            {operator: "topic", operand: msg.topic},
                            {operator: "near", operand: msg.id},
                        ],
                        {trigger: "hotkey"},
                    );
                    return true;
            }
        }
    }

    return false;
}

export function process_keydown(e) {
    activity.set_new_user_input(true);
    const result = get_keydown_hotkey(e);
    if (!result) {
        return false;
    }

    if (Array.isArray(result)) {
        return result.some((hotkey) => process_hotkey(e, hotkey));
    }
    return process_hotkey(e, result);
}

export function initialize() {
    $(document).on("keydown", (e) => {
        if (e.key === undefined) {
            /* Some browsers trigger a 'keydown' event with `key === undefined`
            on selecting autocomplete suggestion. These are not real keypresses
            and can be safely ignored.
            See: https://issues.chromium.org/issues/41425904
            */
            return;
        }
        if (process_keydown(e)) {
            e.preventDefault();
        }
    });
}
