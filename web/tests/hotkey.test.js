"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

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

// Since all the tests here are based on narrow starting with all_messages.
// We set our default narrow to all messages here.
window.location.hash = "#all_messages";

set_global("navigator", {
    platform: "",
});

// jQuery stuff should go away if we make an initialize() method.
set_global("document", "document-stub");

const browser_history = mock_esm("../src/browser_history");
const compose_actions = mock_esm("../src/compose_actions");
const condense = mock_esm("../src/condense");
const drafts = mock_esm("../src/drafts");
const emoji_picker = mock_esm("../src/emoji_picker", {
    is_open: () => false,
    toggle_emoji_popover() {},
});
const gear_menu = mock_esm("../src/gear_menu", {
    is_open: () => false,
});
const lightbox = mock_esm("../src/lightbox");
const list_util = mock_esm("../src/list_util");
const message_edit = mock_esm("../src/message_edit");
const message_lists = mock_esm("../src/message_lists");
const user_topics_ui = mock_esm("../src/user_topics_ui");
const narrow = mock_esm("../src/narrow");
const narrow_state = mock_esm("../src/narrow_state", {
    is_message_feed_visible: () => true,
});
const navigate = mock_esm("../src/navigate");
const overlays = mock_esm("../src/overlays", {
    is_active: () => false,
    settings_open: () => false,
    streams_open: () => false,
    lightbox_open: () => false,
    drafts_open: () => false,
    scheduled_messages_open: () => false,
    info_overlay_open: () => false,
    is_modal_open: () => false,
    active_modal: () => undefined,
    is_overlay_or_modal_open: () => overlays.is_modal_open() || overlays.is_active(),
});
const popovers = mock_esm("../src/user_card_popover", {
    is_user_card_manage_menu_open: () => false,
    is_message_user_card_open: () => false,
    user_sidebar_popped: () => false,
    is_user_card_open: () => false,
});
const popover_menus = mock_esm("../src/popover_menus", {
    get_visible_instance: () => undefined,
});
const reactions = mock_esm("../src/reactions");
const search = mock_esm("../src/search");
const settings_data = mock_esm("../src/settings_data");
const stream_list = mock_esm("../src/stream_list");
const stream_settings_ui = mock_esm("../src/stream_settings_ui");

mock_esm("../src/hotspots", {
    is_open: () => false,
});

mock_esm("../src/recent_view_ui", {
    is_in_focus: () => false,
});

const stream_popover = mock_esm("../src/stream_popover", {
    is_open: () => false,
});

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

const activity = zrequire("activity");
const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const hotkey = zrequire("hotkey");

emoji.initialize({
    realm_emoji: {},
    emoji_codes,
});

function stubbing(module, func_name_to_stub, test_function) {
    with_overrides(({override}) => {
        const stub = make_stub();
        override(module, func_name_to_stub, stub.f);
        test_function(stub);
    });
}

function stubbing_rewire(module, func_name_to_stub, test_function) {
    with_overrides(({override_rewire}) => {
        const stub = make_stub();
        override_rewire(module, func_name_to_stub, stub.f);
        test_function(stub);
    });
}

// Set up defaults for most tests.
hotkey.__Rewire__("processing_text", () => false);

run_test("mappings", () => {
    function map_press(which, shiftKey) {
        return hotkey.get_keypress_hotkey({
            which,
            shiftKey,
        });
    }

    function map_down(which, shiftKey, ctrlKey, metaKey) {
        return hotkey.get_keydown_hotkey({
            which,
            shiftKey,
            ctrlKey,
            metaKey,
        });
    }

    // The next assertion protects against an iOS bug where we
    // treat "!" as a hotkey, because iOS sends the wrong code.
    assert.equal(map_press(33), undefined);

    // Test page-up does work.
    assert.equal(map_down(33).name, "page_up");

    // Test other mappings.
    assert.equal(map_down(9).name, "tab");
    assert.equal(map_down(9, true).name, "shift_tab");
    assert.equal(map_down(27).name, "escape");
    assert.equal(map_down(37).name, "left_arrow");
    assert.equal(map_down(13).name, "enter");
    assert.equal(map_down(46).name, "delete");
    assert.equal(map_down(13, true).name, "enter");

    assert.equal(map_press(47).name, "search"); // slash
    assert.equal(map_press(106).name, "vim_down"); // j

    assert.equal(map_down(219, false, true).name, "escape"); // Ctrl + [
    assert.equal(map_down(67, false, true).name, "copy_with_c"); // Ctrl + C
    assert.equal(map_down(75, false, true).name, "search_with_k"); // Ctrl + K
    assert.equal(map_down(83, false, true).name, "star_message"); // Ctrl + S
    assert.equal(map_down(190, false, true).name, "narrow_to_compose_target"); // Ctrl + .

    // More negative tests.
    assert.equal(map_down(47), undefined);
    assert.equal(map_press(27), undefined);
    assert.equal(map_down(27, true), undefined);
    assert.equal(map_down(86, false, true), undefined); // Ctrl + V
    assert.equal(map_down(90, false, true), undefined); // Ctrl + Z
    assert.equal(map_down(84, false, true), undefined); // Ctrl + T
    assert.equal(map_down(82, false, true), undefined); // Ctrl + R
    assert.equal(map_down(79, false, true), undefined); // Ctrl + O
    assert.equal(map_down(80, false, true), undefined); // Ctrl + P
    assert.equal(map_down(65, false, true), undefined); // Ctrl + A
    assert.equal(map_down(70, false, true), undefined); // Ctrl + F
    assert.equal(map_down(72, false, true), undefined); // Ctrl + H
    assert.equal(map_down(88, false, true), undefined); // Ctrl + X
    assert.equal(map_down(78, false, true), undefined); // Ctrl + N
    assert.equal(map_down(77, false, true), undefined); // Ctrl + M
    assert.equal(map_down(67, false, false, true), undefined); // Cmd + C
    assert.equal(map_down(75, false, false, true), undefined); // Cmd + K
    assert.equal(map_down(83, false, false, true), undefined); // Cmd + S
    assert.equal(map_down(75, true, true), undefined); // Shift + Ctrl + K
    assert.equal(map_down(83, true, true), undefined); // Shift + Ctrl + S
    assert.equal(map_down(219, true, true, false), undefined); // Shift + Ctrl + [

    // Cmd tests for MacOS
    navigator.platform = "MacIntel";
    assert.equal(map_down(219, false, true, false).name, "escape"); // Ctrl + [
    assert.equal(map_down(219, false, false, true), undefined); // Cmd + [
    assert.equal(map_down(67, false, true, true).name, "copy_with_c"); // Ctrl + C
    assert.equal(map_down(67, false, true, false), undefined); // Cmd + C
    assert.equal(map_down(75, false, false, true).name, "search_with_k"); // Cmd + K
    assert.equal(map_down(75, false, true, false), undefined); // Ctrl + K
    assert.equal(map_down(83, false, false, true).name, "star_message"); // Cmd + S
    assert.equal(map_down(83, false, true, false), undefined); // Ctrl + S
    assert.equal(map_down(190, false, false, true).name, "narrow_to_compose_target"); // Cmd + .
    assert.equal(map_down(190, false, true, false), undefined); // Ctrl + .
    // Reset platform
    navigator.platform = "";
});

function process(s) {
    const e = {
        which: s.codePointAt(0),
    };
    try {
        return hotkey.process_keypress(e);
    } catch (error) /* istanbul ignore next */ {
        // An exception will be thrown here if a different
        // function is called than the one declared.  Try to
        // provide a useful error message.
        // add a newline to separate from other console output.
        console.log('\nERROR: Mapping for character "' + e.which + '" does not match tests.');
        throw error;
    }
}

function assert_mapping(c, module, func_name, shiftKey) {
    stubbing(module, func_name, (stub) => {
        assert.ok(process(c, shiftKey));
        assert.equal(stub.num_calls, 1);
    });
}

function assert_mapping_rewire(c, module, func_name, shiftKey) {
    stubbing_rewire(module, func_name, (stub) => {
        assert.ok(process(c, shiftKey));
        assert.equal(stub.num_calls, 1);
    });
}

function assert_unmapped(s) {
    for (const c of s) {
        assert.equal(process(c), false);
    }
}

function test_normal_typing() {
    assert_unmapped("abcdefghijklmnopqrsuvwxyz");
    assert_unmapped(" ");
    assert_unmapped("[]\\.,;");
    assert_unmapped("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
    assert_unmapped('~!@#$%^*()_+{}:"<>');
}

run_test("allow normal typing when processing text", ({override, override_rewire}) => {
    // Unmapped keys should immediately return false, without
    // calling any functions outside of hotkey.js.
    assert_unmapped("bfoyz");
    assert_unmapped("BEFHLNOQTWXYZ");

    // All letters should return false if we are composing text.
    override_rewire(hotkey, "processing_text", () => true);

    let settings_open;
    let is_active;
    let info_overlay_open;
    override(overlays, "is_active", () => is_active);
    override(overlays, "settings_open", () => settings_open);
    override(overlays, "info_overlay_open", () => info_overlay_open);

    for (settings_open of [true, false]) {
        for (is_active of [true, false]) {
            for (info_overlay_open of [true, false]) {
                test_normal_typing();
            }
        }
    }
});

run_test("streams", ({override}) => {
    settings_data.user_can_create_private_streams = () => true;
    delete settings_data.user_can_create_public_streams;
    delete settings_data.user_can_create_web_public_streams;
    override(overlays, "streams_open", () => true);
    override(overlays, "is_active", () => true);
    assert_mapping("S", stream_settings_ui, "keyboard_sub");
    assert_mapping("V", stream_settings_ui, "view_stream");
    assert_mapping("n", stream_settings_ui, "open_create_stream");
    settings_data.user_can_create_private_streams = () => false;
    settings_data.user_can_create_public_streams = () => false;
    settings_data.user_can_create_web_public_streams = () => false;
    assert_unmapped("n");
});

run_test("basic mappings", () => {
    assert_mapping("?", browser_history, "go_to_location");
    assert_mapping("/", search, "initiate_search");
    assert_mapping_rewire("w", activity, "initiate_search");
    assert_mapping("q", stream_list, "initiate_search");

    assert_mapping("A", narrow, "stream_cycle_backward");
    assert_mapping("D", narrow, "stream_cycle_forward");

    assert_mapping("c", compose_actions, "start");
    assert_mapping("x", compose_actions, "start");
    assert_mapping("P", narrow, "by");
    assert_mapping("g", gear_menu, "open");
});

run_test("drafts open", ({override}) => {
    override(overlays, "is_active", () => true);
    override(overlays, "drafts_open", () => true);
    assert_mapping("d", overlays, "close_overlay");
});

run_test("drafts closed w/other overlay", ({override}) => {
    override(overlays, "is_active", () => true);
    override(overlays, "drafts_open", () => false);
    test_normal_typing();
});

run_test("drafts closed launch", ({override}) => {
    override(overlays, "is_active", () => false);
    assert_mapping("d", browser_history, "go_to_location");
});

run_test("modal open", ({override}) => {
    override(overlays, "is_modal_open", () => true);
    test_normal_typing();
});

run_test("misc", ({override}) => {
    // Next, test keys that only work on a selected message.
    const message_view_only_keys = "@+>RjJkKsuvi:GM";

    // Check that they do nothing without a selected message
    with_overrides(({override}) => {
        override(message_lists.current, "visibly_empty", () => true);
        assert_unmapped(message_view_only_keys);
    });

    // Check that they do nothing while in the settings overlay
    with_overrides(({override}) => {
        override(overlays, "settings_open", () => true);
        assert_unmapped("@*+->rRjJkKsSuvi:GM");
    });

    // TODO: Similar check for being in the subs page

    assert_mapping("@", compose_actions, "reply_with_mention");
    assert_mapping("+", reactions, "toggle_emoji_reaction");
    // Without an existing emoji reaction, this next one will only
    // call get_message_reactions, so we verify just that.
    assert_mapping("=", reactions, "get_message_reactions");
    assert_mapping("-", condense, "toggle_collapse");
    assert_mapping("r", compose_actions, "respond_to_message");
    assert_mapping("R", compose_actions, "respond_to_message", true);
    assert_mapping("j", navigate, "down");
    assert_mapping("J", navigate, "page_down");
    assert_mapping("k", navigate, "up");
    assert_mapping("K", navigate, "page_up");
    assert_mapping("u", popovers, "toggle_sender_info");
    assert_mapping("i", popover_menus, "toggle_message_actions_menu");
    assert_mapping(":", emoji_picker, "toggle_emoji_popover", true);
    assert_mapping(">", compose_actions, "quote_and_reply");
    assert_mapping("e", message_edit, "start");

    override(narrow_state, "narrowed_by_topic_reply", () => true);
    assert_mapping("s", narrow, "by_recipient");

    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_pm_reply", () => true);
    assert_unmapped("s");

    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_pm_reply", () => false);
    assert_mapping("s", narrow, "by_topic");

    override(message_edit, "can_move_message", () => true);
    assert_mapping("m", stream_popover, "build_move_topic_to_stream_popover");

    override(message_edit, "can_move_message", () => false);
    assert_unmapped("m");
});

run_test("lightbox overlay open", ({override}) => {
    override(overlays, "is_active", () => true);
    override(overlays, "lightbox_open", () => true);
    assert_mapping("v", overlays, "close_overlay");
});

run_test("lightbox closed w/other overlay open", ({override}) => {
    override(overlays, "is_active", () => true);
    override(overlays, "lightbox_open", () => false);
    test_normal_typing();
});

run_test("v w/no overlays", ({override}) => {
    override(overlays, "is_active", () => false);
    assert_mapping("v", lightbox, "show_from_selected_message");
});

run_test("emoji picker", ({override}) => {
    override(emoji_picker, "is_open", () => true);
    assert_mapping(":", emoji_picker, "navigate", true);
});

run_test("G/M keys", () => {
    // TODO: move
    assert_mapping("G", navigate, "to_end");
    assert_mapping("M", user_topics_ui, "toggle_topic_visibility_policy");
});

run_test("n/p keys", () => {
    // Test keys that work when a message is selected and
    // also when the message list is empty.
    assert_mapping("n", narrow, "narrow_to_next_topic");
    assert_mapping("p", narrow, "narrow_to_next_pm_string");
    assert_mapping("n", narrow, "narrow_to_next_topic");
});

run_test("motion_keys", () => {
    const codes = {
        down_arrow: 40,
        end: 35,
        home: 36,
        left_arrow: 37,
        right_arrow: 39,
        page_up: 33,
        page_down: 34,
        spacebar: 32,
        up_arrow: 38,
        "+": 187,
    };

    function process(name) {
        const e = {
            which: codes[name],
        };

        try {
            return hotkey.process_keydown(e);
        } catch (error) /* istanbul ignore next */ {
            // An exception will be thrown here if a different
            // function is called than the one declared.  Try to
            // provide a useful error message.
            // add a newline to separate from other console output.
            console.log('\nERROR: Mapping for character "' + e.which + '" does not match tests.');
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

    delete overlays.is_active;
    overlays.drafts_open = () => true;
    assert_mapping("up_arrow", drafts, "handle_keyboard_events");
    assert_mapping("down_arrow", drafts, "handle_keyboard_events");
    delete overlays.is_active;
    delete overlays.drafts_open;
});
