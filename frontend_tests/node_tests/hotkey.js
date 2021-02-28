"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, with_field, with_overrides, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");

const popovers = {
    __esModule: true,
    actions_popped: () => false,
    message_info_popped: () => false,
    user_sidebar_popped: () => false,
    user_info_popped: () => false,
};
rewiremock("../../static/js/popovers").with(popovers);
const overlays = {
    __esModule: true,
    is_active: () => false,
    settings_open: () => false,
    streams_open: () => false,
    lightbox_open: () => false,
    drafts_open: () => false,
    info_overlay_open: () => false,
};

rewiremock("../../static/js/overlays").with(overlays);

rewiremock("../../static/js/stream_popover").with({
    stream_popped: () => false,
    topic_popped: () => false,
    all_messages_popped: () => false,
    starred_messages_popped: () => false,
});
const emoji_picker = {
    __esModule: true,
    reactions_popped: () => false,
};
rewiremock("../../static/js/emoji_picker").with(emoji_picker);
rewiremock("../../static/js/hotspots").with({
    is_open: () => false,
});
const gear_menu = {
    __esModule: true,
    is_open: () => false,
};

rewiremock("../../static/js/gear_menu").with(gear_menu);

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

const page_params = set_global("page_params", {});

// jQuery stuff should go away if we make an initialize() method.
set_global("document", "document-stub");

const compose_actions = {__esModule: true};
rewiremock("../../static/js/compose_actions").with(compose_actions);
const condense = {__esModule: true};
rewiremock("../../static/js/condense").with(condense);
const drafts = {__esModule: true};
rewiremock("../../static/js/drafts").with(drafts);
const hashchange = {
    __esModule: true,
    in_recent_topics_hash: () => false,
};
rewiremock("../../static/js/hashchange").with(hashchange);
const lightbox = {__esModule: true};
rewiremock("../../static/js/lightbox").with(lightbox);
const list_util = {__esModule: true};
rewiremock("../../static/js/list_util").with(list_util);
const message_edit = {__esModule: true};
rewiremock("../../static/js/message_edit").with(message_edit);
const muting_ui = {__esModule: true};
rewiremock("../../static/js/muting_ui").with(muting_ui);
const narrow = {__esModule: true};
rewiremock("../../static/js/narrow").with(narrow);
const navigate = {__esModule: true};
rewiremock("../../static/js/navigate").with(navigate);
const reactions = {__esModule: true};
rewiremock("../../static/js/reactions").with(reactions);
const search = {__esModule: true};
rewiremock("../../static/js/search").with(search);
const stream_list = {__esModule: true};
rewiremock("../../static/js/stream_list").with(stream_list);
const subs = {__esModule: true};

rewiremock("../../static/js/subs").with(subs);

set_global("current_msg_list", {
    empty() {
        return false;
    },
    selected_id() {
        return 42;
    },
    selected_message() {
        return {
            sent_by_me: true,
            flags: ["read", "starred"],
        };
    },
    selected_row() {},
    get_row() {
        return 101;
    },
});
rewiremock("../../static/js/recent_topics").with({
    is_visible: () => false,
});

rewiremock.enable();

const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");
const emoji = zrequire("emoji", "shared/js/emoji");
const activity = zrequire("activity");
const hotkey = zrequire("hotkey");

emoji.initialize({
    realm_emoji: {},
    emoji_codes,
});

function stubbing(module, func_name_to_stub, test_function) {
    with_overrides((override) => {
        const stub = make_stub();
        override(module, func_name_to_stub, stub.f);
        test_function(stub);
    });
}

// Set up defaults for most tests.
hotkey.__Rewire__("in_content_editable_widget", () => false);
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
        which: s.charCodeAt(0),
    };
    try {
        return hotkey.process_keypress(e);
    } catch (error) {
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
        assert(process(c, shiftKey));
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

run_test("allow normal typing when processing text", (override) => {
    // Unmapped keys should immediately return false, without
    // calling any functions outside of hotkey.js.
    assert_unmapped("bfmoyz");
    assert_unmapped("BEFHILNOQTUWXYZ");

    // We have to skip some checks due to the way the code is
    // currently organized for mapped keys.
    override(hotkey, "in_content_editable_widget", () => false);

    // All letters should return false if we are composing text.
    override(hotkey, "processing_text", () => true);

    for (const settings_open of [() => true, () => false]) {
        for (const is_active of [() => true, () => false]) {
            for (const info_overlay_open of [() => true, () => false]) {
                with_field(overlays, "is_active", is_active, () => {
                    with_field(overlays, "settings_open", settings_open, () => {
                        with_field(overlays, "info_overlay_open", info_overlay_open, () => {
                            test_normal_typing();
                        });
                    });
                });
            }
        }
    }
});

run_test("streams", (override) => {
    page_params.can_create_streams = true;
    override(overlays, "streams_open", () => true);
    override(overlays, "is_active", () => true);
    assert_mapping("S", subs, "keyboard_sub");
    assert_mapping("V", subs, "view_stream");
    assert_mapping("n", subs, "open_create_stream");
    page_params.can_create_streams = false;
    assert_unmapped("n");
});

run_test("basic mappings", () => {
    assert_mapping("?", hashchange, "go_to_location");
    assert_mapping("/", search, "initiate_search");
    assert_mapping("w", activity, "initiate_search");
    assert_mapping("q", stream_list, "initiate_search");

    assert_mapping("A", narrow, "stream_cycle_backward");
    assert_mapping("D", narrow, "stream_cycle_forward");

    assert_mapping("c", compose_actions, "start");
    assert_mapping("x", compose_actions, "start");
    assert_mapping("P", narrow, "by");
    assert_mapping("g", gear_menu, "open");
});

run_test("drafts open", (override) => {
    override(overlays, "is_active", () => true);
    override(overlays, "drafts_open", () => true);
    assert_mapping("d", overlays, "close_overlay");
});

run_test("drafts closed w/other overlay", (override) => {
    override(overlays, "is_active", () => true);
    override(overlays, "drafts_open", () => false);
    test_normal_typing();
});

run_test("drafts closed launch", (override) => {
    override(overlays, "is_active", () => false);
    assert_mapping("d", drafts, "launch");
});

run_test("misc", () => {
    // Next, test keys that only work on a selected message.
    const message_view_only_keys = "@+>RjJkKsSuvi:GM";

    // Check that they do nothing without a selected message
    with_overrides((override) => {
        override(current_msg_list, "empty", () => true);
        assert_unmapped(message_view_only_keys);
    });

    // Check that they do nothing while in the settings overlay
    with_overrides((override) => {
        override(overlays, "settings_open", () => true);
        assert_unmapped("@*+->rRjJkKsSuvi:GM");
    });

    // TODO: Similar check for being in the subs page

    assert_mapping("@", compose_actions, "reply_with_mention");
    assert_mapping("+", reactions, "toggle_emoji_reaction");
    assert_mapping("-", condense, "toggle_collapse");
    assert_mapping("r", compose_actions, "respond_to_message");
    assert_mapping("R", compose_actions, "respond_to_message", true);
    assert_mapping("j", navigate, "down");
    assert_mapping("J", navigate, "page_down");
    assert_mapping("k", navigate, "up");
    assert_mapping("K", navigate, "page_up");
    assert_mapping("s", narrow, "by_recipient");
    assert_mapping("S", narrow, "by_topic");
    assert_mapping("u", popovers, "show_sender_info");
    assert_mapping("i", popovers, "open_message_menu");
    assert_mapping(":", reactions, "open_reactions_popover", true);
    assert_mapping(">", compose_actions, "quote_and_reply");
    assert_mapping("e", message_edit, "start");
});

run_test("lightbox overlay open", (override) => {
    override(overlays, "is_active", () => true);
    override(overlays, "lightbox_open", () => true);
    assert_mapping("v", overlays, "close_overlay");
});

run_test("lightbox closed w/other overlay open", (override) => {
    override(overlays, "is_active", () => true);
    override(overlays, "lightbox_open", () => false);
    test_normal_typing();
});

run_test("v w/no overlays", (override) => {
    override(overlays, "is_active", () => false);
    assert_mapping("v", lightbox, "show_from_selected_message");
});

run_test("emoji picker", (override) => {
    override(emoji_picker, "reactions_popped", () => true);
    assert_mapping(":", emoji_picker, "navigate", true);
});

run_test("G/M keys", () => {
    // TODO: move
    assert_mapping("G", navigate, "to_end");
    assert_mapping("M", muting_ui, "toggle_topic_mute");
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
        } catch (error) {
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
            assert(process(key_name));
            assert.equal(stub.num_calls, 1);
        });
    }

    list_util.inside_list = () => false;
    current_msg_list.empty = () => true;
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

    current_msg_list.empty = () => false;
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
    assert_mapping("up_arrow", subs, "switch_rows");
    assert_mapping("down_arrow", subs, "switch_rows");
    overlays.streams_open = () => false;

    overlays.lightbox_open = () => true;
    assert_mapping("left_arrow", lightbox, "prev");
    assert_mapping("right_arrow", lightbox, "next");
    overlays.lightbox_open = () => false;

    hotkey.__Rewire__("in_content_editable_widget", () => true);
    assert_unmapped("down_arrow");
    assert_unmapped("up_arrow");
    hotkey.__Rewire__("in_content_editable_widget", () => false);

    overlays.settings_open = () => true;
    assert_unmapped("end");
    assert_unmapped("home");
    assert_unmapped("left_arrow");
    assert_unmapped("page_up");
    assert_unmapped("page_down");
    assert_unmapped("spacebar");
    overlays.settings_open = () => false;

    overlays.is_active = () => true;
    overlays.drafts_open = () => true;
    assert_mapping("up_arrow", drafts, "drafts_handle_events");
    assert_mapping("down_arrow", drafts, "drafts_handle_events");
    overlays.is_active = () => false;
    overlays.drafts_open = () => false;
});
rewiremock.disable();
