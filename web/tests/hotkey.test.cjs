"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

// Important note on these tests:

//
// The way the Zulip hotkey tests work is as follows.  First, we set
// up various contexts by monkey-patching the various hotkeys exports
// functions (like overlays.settings_open).  Within that context, to
// test whether a given key (e.g. `x`) results in a specific function
// (e.g. `ui.foo()`), we fail to import any modules other than
// hotkey.js so that accessing them will result in a ReferenceError.
//
// Then we create a stub `ui.foo`, and call the hotkey function.  If
// it calls any external module other than `ui.foo`, it'll crash.
// Future work includes making sure it actually does call `ui.foo()`.

// All tests use the combined feed as the default narrow.
window.location.hash = "#feed";

set_global("navigator", {
    platform: "",
});

// jQuery stuff should go away if we make an initialize() method.
set_global("document", {
    hasFocus: () => false,
});

const activity_ui = mock_esm("../src/activity_ui");
const activity = zrequire("../src/activity");
const browser_history = mock_esm("../src/browser_history");
const compose_actions = mock_esm("../src/compose_actions");
const compose_reply = mock_esm("../src/compose_reply");
const condense = mock_esm("../src/condense");
const drafts_overlay_ui = mock_esm("../src/drafts_overlay_ui");
const emoji_picker = mock_esm("../src/emoji_picker", {
    is_open: () => false,
    toggle_emoji_popover() {},
});
const gear_menu = mock_esm("../src/gear_menu");
const lightbox = mock_esm("../src/lightbox");
const list_util = mock_esm("../src/list_util");
const message_actions_popover = mock_esm("../src/message_actions_popover");
const message_edit = mock_esm("../src/message_edit");
const message_edit_history = mock_esm("../src/message_edit_history");
const message_lists = mock_esm("../src/message_lists");
const user_topics_ui = mock_esm("../src/user_topics_ui");
const message_view = mock_esm("../src/message_view");
const narrow_state = mock_esm("../src/narrow_state");
const navigate = mock_esm("../src/navigate");
const modals = mock_esm("../src/modals", {
    any_active: () => false,
    active_modal: () => undefined,
});
const overlays = mock_esm("../src/overlays", {
    any_active: () => false,
    settings_open: () => false,
    streams_open: () => false,
    lightbox_open: () => false,
    drafts_open: () => false,
    scheduled_messages_open: () => false,
    reminders_open: () => false,
    info_overlay_open: () => false,
    message_edit_history_open: () => false,
});
const popovers = mock_esm("../src/user_card_popover", {
    user_sidebar: {
        is_open: () => false,
    },
    message_user_card: {
        is_open: () => false,
    },
    user_card: {
        is_open: () => false,
    },
});
const reactions = mock_esm("../src/reactions");
const read_receipts = mock_esm("../src/read_receipts");
const search = mock_esm("../src/search");
const settings_data = mock_esm("../src/settings_data");
const stream_list = mock_esm("../src/stream_list", {
    is_zoomed_in: () => false,
});
const stream_popover = mock_esm("../src/stream_popover");
const stream_settings_ui = mock_esm("../src/stream_settings_ui");

mock_esm("../src/recent_view_ui", {
    is_in_focus: () => false,
});

const spectators = zrequire("../src/spectators");

message_lists.current = {
    visibly_empty() {
        return false;
    },
    selected_id() {
        return 42;
    },
    selected_row() {
        const $row = $.create("selected-row-stub");
        $row.set_find_results(".message-actions-menu-button", []);
        $row.set_find_results(".emoji-message-control-button-container", {
            closest: () => ({css: () => "none"}),
        });
        return $row;
    },
    selected_message() {
        return {
            sent_by_me: true,
            flags: ["read", "starred"],
        };
    },
    get_row() {
        return 101;
    },
};

const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const hotkey = zrequire("hotkey");

emoji.initialize({
    realm_emoji: {},
    emoji_codes,
});

const settings_config = zrequire("settings_config");
const {set_realm} = zrequire("state_data");
const realm = {};
set_realm(realm);

function stubbing(module, func_name_to_stub, test_function) {
    with_overrides(({override}) => {
        const stub = make_stub();
        override(module, func_name_to_stub, stub.f);
        test_function(stub);
    });
}

function test_while_not_editing_text(label, f) {
    run_test(label, (helpers) => {
        helpers.override_rewire(hotkey, "processing_text", () => false);
        f(helpers);
    });
}

run_test("mappings", () => {
    function map_down(key, shiftKey, ctrlKey, metaKey, altKey) {
        return hotkey.get_keydown_hotkey({
            key,
            shiftKey,
            ctrlKey,
            metaKey,
            altKey,
        });
    }

    // The next assertion protects against an iOS bug where we
    // treat "!" as a hotkey, because iOS sends the wrong code.
    assert.equal(map_down("!"), undefined);

    // Test page-up does work.
    assert.equal(map_down("PageUp").name, "page_up");

    // Test other mappings.
    assert.equal(map_down("Tab").name, "tab");
    assert.equal(map_down("Tab", true).name, "shift_tab");
    assert.equal(map_down("Escape").name, "escape");
    assert.equal(map_down("ArrowLeft").name, "left_arrow");
    assert.equal(map_down("Enter").name, "enter");
    assert.equal(map_down("Delete").name, "delete");
    assert.equal(map_down("Enter", true).name, "enter");
    assert.equal(map_down("H", true).name, "view_edit_history");
    assert.equal(map_down("N", true).name, "narrow_to_next_unread_followed_topic");
    assert.deepEqual(
        map_down("V", true).map((item) => item.name),
        ["view_selected_stream", "toggle_read_receipts"],
    );

    assert.equal(map_down("/").name, "search");
    assert.equal(map_down("j").name, "vim_down");

    assert.equal(map_down("[", false, true).name, "escape");
    assert.equal(map_down("c", false, true).name, "copy_with_c");
    assert.equal(map_down("k", false, true).name, "search_with_k");
    assert.equal(map_down("s", false, true).name, "star_message");
    assert.equal(map_down(".", false, true).name, "narrow_to_compose_target");

    assert.equal(map_down("p", false, false, false, true).name, "toggle_compose_preview"); // Alt + P
    assert.equal(map_down("+", false).name, "thumbs_up_emoji");
    assert.equal(map_down("+", true).name, "thumbs_up_emoji");

    // More negative tests.
    assert.equal(map_down("Escape", true), undefined);
    assert.equal(map_down("v", false, true), undefined);
    assert.equal(map_down("z", false, true), undefined);
    assert.equal(map_down("t", false, true), undefined);
    assert.equal(map_down("r", false, true), undefined);
    assert.equal(map_down("o", false, true), undefined);
    assert.equal(map_down("p", false, true), undefined);
    assert.equal(map_down("a", false, true), undefined);
    assert.equal(map_down("f", false, true), undefined);
    assert.equal(map_down("h", false, true), undefined);
    assert.equal(map_down("x", false, true), undefined);
    assert.equal(map_down("n", false, true), undefined);
    assert.equal(map_down("m", false, true), undefined);
    assert.equal(map_down("c", false, false, true), undefined);
    assert.equal(map_down("k", false, false, true), undefined);
    assert.equal(map_down("s", false, false, true), undefined);
    assert.equal(map_down("K", true, true), undefined);
    assert.equal(map_down("S", true, true), undefined);
    assert.equal(map_down("[", true, true, false), undefined);
    assert.equal(map_down("P", true, false, false, true), undefined);
    assert.equal(map_down("+", false, true), undefined);

    // Cmd tests for MacOS
    navigator.platform = "MacIntel";
    assert.equal(map_down("[", false, true, false).name, "escape");
    assert.equal(map_down("[", false, false, true), undefined);
    assert.equal(map_down("c", false, false, true).name, "copy_with_c");
    assert.equal(map_down("c", false, true, true), undefined);
    assert.equal(map_down("c", false, true, false), undefined);
    assert.equal(map_down("k", false, false, true).name, "search_with_k");
    assert.equal(map_down("k", false, true, false), undefined);
    assert.equal(map_down("s", false, false, true).name, "star_message");
    assert.equal(map_down("s", false, true, false), undefined);
    assert.equal(map_down(".", false, false, true).name, "narrow_to_compose_target");
    assert.equal(map_down(".", false, true, false), undefined);
    // Reset platform
    navigator.platform = "";

    // Caps Lock doesn't interfere with shortcuts.
    assert.equal(map_down("A").name, "open_combined_feed");
    assert.equal(map_down("A", true).name, "stream_cycle_backward");
    assert.equal(map_down("C", false, true).name, "copy_with_c");
    assert.equal(map_down("P", false, false, false, true).name, "toggle_compose_preview");
});

run_test("mappings non-latin keyboard", () => {
    // This test replicates the logic of the "mappings" test above
    // but uses a non-Latin (Russian) keyboard layout to verify that
    // hotkeys work irrespective of the keyboard layout.
    // Layout used: https://kbdlayout.info/kbdru/overview+virtualkeys?arrangement=ANSI104
    function map_down(key, code, shiftKey, ctrlKey, metaKey, altKey) {
        return hotkey.get_keydown_hotkey({
            key,
            code,
            shiftKey,
            ctrlKey,
            metaKey,
            altKey,
        });
    }

    // Test mappings.
    assert.equal(map_down("Р", "KeyH", true).name, "view_edit_history");
    assert.equal(map_down("Т", "KeyN", true).name, "narrow_to_next_unread_followed_topic");
    assert.deepEqual(
        map_down("М", "KeyV", true).map((item) => item.name),
        ["view_selected_stream", "toggle_read_receipts"],
    );
    assert.equal(map_down("о", "KeyJ").name, "vim_down");
    assert.equal(map_down("х", "BracketLeft", false, true).name, "escape");
    assert.equal(map_down("с", "KeyC", false, true).name, "copy_with_c");
    assert.equal(map_down("л", "KeyK", false, true).name, "search_with_k");
    assert.equal(map_down("ы", "KeyS", false, true).name, "star_message");
    assert.equal(map_down("з", "KeyP", false, false, false, true).name, "toggle_compose_preview");

    // More negative tests.
    assert.equal(map_down("м", "KeyV", false, true), undefined);
    assert.equal(map_down("я", "KeyZ", false, true), undefined);
    assert.equal(map_down("е", "KeyT", false, true), undefined);
    assert.equal(map_down("к", "KeyR", false, true), undefined);
    assert.equal(map_down("щ", "KeyO", false, true), undefined);
    assert.equal(map_down("з", "KeyP", false, true), undefined);
    assert.equal(map_down("ф", "KeyA", false, true), undefined);
    assert.equal(map_down("а", "KeyF", false, true), undefined);
    assert.equal(map_down("р", "KeyH", false, true), undefined);
    assert.equal(map_down("ч", "KeyX", false, true), undefined);
    assert.equal(map_down("т", "KeyN", false, true), undefined);
    assert.equal(map_down("ь", "KeyM", false, true), undefined);
    assert.equal(map_down("с", "KeyC", false, false, true), undefined);
    assert.equal(map_down("л", "KeyK", false, false, true), undefined);
    assert.equal(map_down("ы", "KeyS", false, false, true), undefined);
    assert.equal(map_down("Л", "KeyK", true, true), undefined);
    assert.equal(map_down("Ы", "KeyS", true, true), undefined);
    assert.equal(map_down("Х", "BracketLeft", true, true, false), undefined);
    assert.equal(map_down("З", "KeyP", true, false, false, true), undefined);

    // Cmd tests for MacOS
    navigator.platform = "MacIntel";
    assert.equal(map_down("х", "BracketLeft", false, true, false).name, "escape");
    assert.equal(map_down("х", "BracketLeft", false, false, true), undefined);
    assert.equal(map_down("с", "KeyC", false, false, true).name, "copy_with_c");
    assert.equal(map_down("с", "KeyC", false, true, true), undefined);
    assert.equal(map_down("с", "KeyC", false, true, false), undefined);
    assert.equal(map_down("л", "KeyK", false, false, true).name, "search_with_k");
    assert.equal(map_down("л", "KeyK", false, true, false), undefined);
    assert.equal(map_down("ы", "KeyS", false, false, true).name, "star_message");
    assert.equal(map_down("ы", "KeyS", false, true, false), undefined);
    // Reset platform
    navigator.platform = "";

    // Caps Lock doesn't interfere with shortcuts.
    assert.equal(map_down("Ф", "KeyA").name, "open_combined_feed");
    assert.equal(map_down("Ф", "KeyA", true).name, "stream_cycle_backward");
    assert.equal(map_down("С", "KeyC", false, true).name, "copy_with_c");
    assert.equal(map_down("З", "KeyP", false, false, false, true).name, "toggle_compose_preview");
});

function process(s, shiftKey) {
    const e = {
        key: s,
        shiftKey,
    };
    try {
        return hotkey.process_keydown(e);
    } catch (error) /* istanbul ignore next */ {
        // An exception will be thrown here if a different
        // function is called than the one declared.  Try to
        // provide a useful error message.
        // add a newline to separate from other console output.
        console.log('\nERROR: Mapping for character "' + e.key + '" does not match tests.');
        throw error;
    }
}

function assert_mapping(c, module, func_name, shiftKey) {
    stubbing(module, func_name, (stub) => {
        assert.ok(process(c, shiftKey));
        assert.equal(stub.num_calls, 1);
    });
}

function assert_unmapped(s) {
    for (const c of s) {
        const shiftKey = /^[A-Z]$/.test(c);
        assert.equal(process(c, shiftKey), false);
    }
}

function test_normal_typing() {
    assert_unmapped("abcdefghijklmnopqrsuvwxyz");
    assert_unmapped(" ");
    assert_unmapped("[]\\.,;");
    assert_unmapped("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
    assert_unmapped('~!@#$%^*()_+{}:"<>');
}

test_while_not_editing_text("unmapped keys return false easily", () => {
    // Unmapped keys should immediately return false, without
    // calling any functions outside of hotkey.js.
    // (unless we are editing text)
    assert_unmapped("bfoyz");
    assert_unmapped("BEFLOQTWXYZ");
});

run_test("allow normal typing when editing text", ({override, override_rewire}) => {
    // All letters should return false if we are composing text.
    override_rewire(hotkey, "processing_text", () => true);

    let settings_open;
    let any_active;
    let info_overlay_open;
    override(overlays, "any_active", () => any_active);
    override(overlays, "settings_open", () => settings_open);
    override(overlays, "info_overlay_open", () => info_overlay_open);

    $.create(".navbar-item:focus", {children: []});

    for (settings_open of [true, false]) {
        for (any_active of [true, false]) {
            for (info_overlay_open of [true, false]) {
                test_normal_typing();
            }
        }
    }
});

test_while_not_editing_text("streams", ({override}) => {
    settings_data.user_can_create_private_streams = () => true;
    delete settings_data.user_can_create_public_streams;
    delete settings_data.user_can_create_web_public_streams;
    override(overlays, "streams_open", () => true);
    override(overlays, "any_active", () => true);
    assert_mapping("S", stream_settings_ui, "keyboard_sub", true);
    assert_mapping("V", stream_settings_ui, "view_stream", true);
    assert_mapping("n", stream_settings_ui, "open_create_stream");
    settings_data.user_can_create_private_streams = () => false;
    settings_data.user_can_create_public_streams = () => false;
    settings_data.user_can_create_web_public_streams = () => false;
    assert_unmapped("n");
});

test_while_not_editing_text("basic mappings", () => {
    assert_mapping("?", browser_history, "go_to_location");
    assert_mapping("/", search, "initiate_search");
    assert_mapping("w", activity_ui, "initiate_search");
    assert_mapping("q", stream_list, "initiate_search");

    assert_mapping("A", message_view, "stream_cycle_backward", true);
    assert_mapping("D", message_view, "stream_cycle_forward", true);

    assert_mapping("c", compose_actions, "start");
    assert_mapping("x", compose_actions, "start");
    assert_mapping("P", message_view, "show", true);
    assert_mapping("g", gear_menu, "toggle");
});

test_while_not_editing_text("drafts open", ({override}) => {
    override(overlays, "any_active", () => true);
    override(overlays, "drafts_open", () => true);
    assert_mapping("d", overlays, "close_overlay");
});

test_while_not_editing_text("drafts closed w/other overlay", ({override}) => {
    override(overlays, "any_active", () => true);
    override(overlays, "drafts_open", () => false);
    test_normal_typing();
});

test_while_not_editing_text("drafts closed launch", ({override}) => {
    override(overlays, "any_active", () => false);
    assert_mapping("d", browser_history, "go_to_location");
});

run_test("modal open", ({override}) => {
    override(modals, "any_active", () => true);
    test_normal_typing();
});

test_while_not_editing_text("misc", ({override}) => {
    // Next, test keys that only work on a selected message.
    const message_view_only_keys = "@+>RjJkKsuvVi:GH";

    // Check that they do nothing without a selected message
    with_overrides(({override}) => {
        override(message_lists.current, "visibly_empty", () => true);
        assert_unmapped(message_view_only_keys);
    });

    // Check that they do nothing while in the settings overlay
    with_overrides(({override}) => {
        override(overlays, "settings_open", () => true);
        assert_unmapped("@*+->rRjJkKsSuvVi:GMH");
    });

    // TODO: Similar check for being in the subs page

    assert_mapping("@", compose_reply, "reply_with_mention");
    assert_mapping("+", reactions, "toggle_emoji_reaction");
    // Without an existing emoji reaction, this next one will only
    // call get_message_reactions, so we verify just that.
    assert_mapping("=", reactions, "get_message_reactions");
    assert_mapping("-", condense, "toggle_collapse");
    assert_mapping("r", compose_reply, "respond_to_message");
    assert_mapping("R", compose_reply, "respond_to_message", true);
    assert_mapping("j", navigate, "down");
    assert_mapping("J", navigate, "page_down", true);
    assert_mapping("k", navigate, "up");
    assert_mapping("K", navigate, "page_up", true);
    assert_mapping("u", popovers, "toggle_sender_info");
    assert_mapping("i", message_actions_popover, "toggle_message_actions_menu");
    assert_mapping(":", emoji_picker, "toggle_emoji_popover", true);
    assert_mapping(">", compose_reply, "quote_message");
    assert_mapping("<", compose_reply, "quote_message");
    assert_mapping("e", message_edit, "start");

    override(
        realm,
        "realm_message_edit_history_visibility_policy",
        settings_config.message_edit_history_visibility_policy_values.always.code,
    );
    assert_mapping("H", message_edit_history, "fetch_and_render_message_history", true, true);

    override(narrow_state, "narrowed_by_topic_reply", () => true);
    assert_mapping("s", message_view, "narrow_by_recipient");

    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_pm_reply", () => true);
    assert_unmapped("s");

    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_pm_reply", () => false);
    assert_mapping("s", message_view, "narrow_by_topic");

    override(message_edit, "can_move_message", () => true);
    assert_mapping("m", stream_popover, "build_move_topic_to_stream_popover");

    override(message_edit, "can_move_message", () => false);
    assert_unmapped("m");

    assert_mapping("V", read_receipts, "show_user_list", true);

    override(modals, "any_active", () => true);
    override(modals, "active_modal", () => "#read_receipts_modal");
    assert_mapping("V", read_receipts, "hide_user_list", true);
});

test_while_not_editing_text("lightbox overlay open", ({override}) => {
    override(overlays, "any_active", () => true);
    override(overlays, "lightbox_open", () => true);
    assert_mapping("v", overlays, "close_overlay");
});

test_while_not_editing_text("lightbox closed w/other overlay open", ({override}) => {
    override(overlays, "any_active", () => true);
    override(overlays, "lightbox_open", () => false);
    test_normal_typing();
});

test_while_not_editing_text("v w/no overlays", ({override}) => {
    override(overlays, "any_active", () => false);
    assert_mapping("v", lightbox, "show_from_selected_message");
});

run_test("emoji picker", ({override}) => {
    override(emoji_picker, "is_open", () => true);
    assert_mapping(":", emoji_picker, "navigate", true);
});

test_while_not_editing_text("G/M keys", () => {
    // TODO: move
    assert_mapping("G", navigate, "to_end", true);
    assert_mapping("M", user_topics_ui, "toggle_topic_visibility_policy", true);
});

test_while_not_editing_text("n/p keys", () => {
    // Test keys that work when a message is selected and
    // also when the message list is empty.
    assert_mapping("n", message_view, "narrow_to_next_topic");
    assert_mapping("p", message_view, "narrow_to_next_pm_string");
    assert_mapping("n", message_view, "narrow_to_next_topic");
});

test_while_not_editing_text("narrow next unread followed topic", () => {
    assert_mapping("N", message_view, "narrow_to_next_topic", true);
});

test_while_not_editing_text("motion_keys", () => {
    $.create(".navbar-item:focus", {children: []});

    const keys = {
        down_arrow: "ArrowDown",
        end: "End",
        home: "Home",
        left_arrow: "ArrowLeft",
        right_arrow: "ArrowRight",
        page_up: "PageUp",
        page_down: "PageDown",
        spacebar: " ",
        up_arrow: "ArrowUp",
    };

    function process(name) {
        const e = {
            key: keys[name],
        };

        try {
            return hotkey.process_keydown(e);
        } catch (error) /* istanbul ignore next */ {
            // An exception will be thrown here if a different
            // function is called than the one declared.  Try to
            // provide a useful error message.
            // add a newline to separate from other console output.
            console.log('\nERROR: Mapping for character "' + e.key + '" does not match tests.');
            throw error;
        }
    }

    function assert_unmapped(name) {
        assert.equal(process(name), false);
    }

    function assert_mapping(key_name, module, func_name) {
        stubbing(module, func_name, (stub) => {
            assert.ok(process(key_name));
            assert.equal(stub.num_calls, 1);
        });
    }

    list_util.inside_list = () => false;
    message_lists.current.visibly_empty = () => true;
    overlays.settings_open = () => false;
    overlays.streams_open = () => false;
    overlays.lightbox_open = () => false;

    assert_unmapped("down_arrow");
    assert_unmapped("end");
    assert_unmapped("home");
    assert_unmapped("page_up");
    assert_unmapped("page_down");
    assert_unmapped("spacebar");
    assert_unmapped("up_arrow");

    list_util.inside_list = () => true;
    assert_mapping("up_arrow", list_util, "go_up");
    assert_mapping("down_arrow", list_util, "go_down");
    list_util.inside_list = () => false;

    message_lists.current.visibly_empty = () => false;
    assert_mapping("down_arrow", navigate, "down");
    assert_mapping("end", navigate, "to_end");
    assert_mapping("home", navigate, "to_home");
    assert_mapping("left_arrow", message_edit, "edit_last_sent_message");
    assert_mapping("page_up", navigate, "page_up");
    assert_mapping("page_down", navigate, "page_down");
    assert_mapping("spacebar", navigate, "page_down");
    assert_mapping("up_arrow", navigate, "up");

    overlays.info_overlay_open = () => true;
    assert_unmapped("down_arrow");
    assert_unmapped("up_arrow");
    overlays.info_overlay_open = () => false;

    overlays.streams_open = () => true;
    assert_mapping("up_arrow", stream_settings_ui, "switch_rows");
    assert_mapping("down_arrow", stream_settings_ui, "switch_rows");
    delete overlays.streams_open;

    overlays.lightbox_open = () => true;
    assert_mapping("left_arrow", lightbox, "prev");
    assert_mapping("right_arrow", lightbox, "next");
    delete overlays.lightbox_open;

    overlays.settings_open = () => true;
    assert_unmapped("end");
    assert_unmapped("home");
    assert_unmapped("left_arrow");
    assert_unmapped("page_up");
    assert_unmapped("page_down");
    assert_unmapped("spacebar");
    delete overlays.settings_open;

    delete overlays.any_active;
    overlays.drafts_open = () => true;
    assert_mapping("up_arrow", drafts_overlay_ui, "handle_keyboard_events");
    assert_mapping("down_arrow", drafts_overlay_ui, "handle_keyboard_events");
    delete overlays.any_active;
    delete overlays.drafts_open;
});

run_test("test new user input hook called", () => {
    let hook_called = false;
    activity.register_on_new_user_input_hook(() => {
        hook_called = true;
    });

    // Currently, "b" is not a valid hotkey.
    // But it serves our purpose here to verify
    // `hook_called` on keydown.
    hotkey.process_keydown({key: "b"});
    assert.ok(hook_called);
});

test_while_not_editing_text("e shortcut works for anonymous users", ({override_rewire}) => {
    page_params.is_spectator = true;

    const stub = make_stub();
    override_rewire(spectators, "login_to_access", stub.f);
    overlays.any_active = () => false;
    overlays.settings_open = () => false;

    const e = {
        key: "e",
    };

    stubbing(message_edit, "start", (stub) => {
        hotkey.process_keydown(e);
        assert.equal(stub.num_calls, 1);
    });
    assert.equal(stub.num_calls, 0, "login_to_access should not be called for 'e' shortcut");
    // Fake call to avoid warning about unused stub.
    spectators.login_to_access();
    assert.equal(stub.num_calls, 1);
});
