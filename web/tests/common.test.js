"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

mock_esm("tippy.js", {
    default(arg) {
        arg._tippy = {setContent: noop};
        return arg._tippy;
    },
});

set_global("document", {});
const navigator = set_global("navigator", {});

const common = zrequire("common");

run_test("phrase_match", () => {
    assert.ok(common.phrase_match("tes", "test"));
    assert.ok(common.phrase_match("Tes", "test"));
    assert.ok(common.phrase_match("Tes", "Test"));
    assert.ok(common.phrase_match("tes", "Stream Test"));

    assert.ok(!common.phrase_match("tests", "test"));
    assert.ok(!common.phrase_match("tes", "hostess"));
});

run_test("adjust_mac_kbd_tags non-mac", ({override}) => {
    override(navigator, "platform", "Windows");

    // The adjust_mac_kbd_tags has a really simple guard
    // at the top, and we just test the early-return behavior
    // by trying to pass it garbage.
    common.adjust_mac_kbd_tags("selector-that-does-not-exist");
});

run_test("adjust_mac_kbd_tags mac", ({override}) => {
    const keys_to_test_mac = new Map([
        ["Backspace", "Delete"],
        ["Enter", "Return"],
        ["Home", "←"],
        ["End", "→"],
        ["PgUp", "↑"],
        ["PgDn", "↓"],
        ["Ctrl", "⌘"],
        ["Alt", "⌥"],
        ["#stream_name", "#stream_name"],
        ["Ctrl+K", "Ctrl+K"],
        ["[", "["],
        ["X", "X"],
        ["data-mac-following-key", "data-mac-following-key"],
    ]);

    const fn_shortcuts = new Set(["Home", "End", "PgUp", "PgDn"]);

    override(navigator, "platform", "MacIntel");
    $("<span>").contents = () => $("<contents-stub>");

    const test_items = [];
    let key_no = 1;

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        const $stub = $.create("hotkey_" + key_no);
        $stub.text(old_key);
        assert.equal($stub.hasClass("arrow-key"), false);
        if (fn_shortcuts.has(old_key)) {
            $stub.before = ($elem) => {
                assert.equal($elem.selector, "<kbd>");
            };
        }
        if (old_key === "data-mac-following-key") {
            $stub.attr("data-mac-following-key", "⌥");
            $stub.after = ($plus, $elem) => {
                assert.equal($plus.selector, "<contents-stub>");
                assert.equal($elem.selector, "<kbd>");
                assert.equal($elem.text(), $stub.attr("data-mac-following-key"));
            };
        }
        test_item.$stub = $stub;
        test_item.mac_key = mac_key;
        test_item.adds_arrow_key = fn_shortcuts.has(old_key);
        test_items.push(test_item);
        key_no += 1;
    }

    const children = test_items.map((test_item) => ({to_$: () => test_item.$stub}));

    $.create(".markdown kbd", {children});

    common.adjust_mac_kbd_tags(".markdown kbd");

    for (const test_item of test_items) {
        assert.equal(test_item.$stub.text(), test_item.mac_key);
        assert.equal(test_item.$stub.hasClass("arrow-key"), test_item.adds_arrow_key);
    }
});

run_test("adjust_mac_hotkey_hints non-mac", ({override}) => {
    override(navigator, "platform", "Windows");

    // The adjust_mac_hotkey_hints has a really simple guard
    // at the top, and we just test the early-return behavior
    // by trying to pass it garbage.
    common.adjust_mac_hotkey_hints("not-an-array");
});

// Test default values of adjust_mac_hotkey_hints
// Expected values
run_test("adjust_mac_hotkey_hints mac expected", ({override}) => {
    const keys_to_test_mac = new Map([
        [["Backspace"], ["Delete"]],
        [["Enter"], ["Return"]],
        [["Home"], ["Fn", "←"]],
        [["End"], ["Fn", "→"]],
        [["PgUp"], ["Fn", "↑"]],
        [["PgDn"], ["Fn", "↓"]],
        [["Ctrl"], ["⌘"]],
    ]);

    override(navigator, "platform", "MacIntel");

    const test_items = [];

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        common.adjust_mac_hotkey_hints(old_key);

        test_item.mac_key = mac_key;
        test_item.adjusted_key = old_key;
        test_items.push(test_item);
    }

    for (const test_item of test_items) {
        assert.deepStrictEqual(test_item.mac_key, test_item.adjusted_key);
    }
});

// Test non-default values of adjust_mac_hotkey_hints
// Random values
run_test("adjust_mac_hotkey_hints mac random", ({override}) => {
    const keys_to_test_mac = new Map([
        [
            ["Ctrl", "["],
            ["⌘", "["],
        ],
        [
            ["Ctrl", "K"],
            ["⌘", "K"],
        ],
        [
            ["Shift", "G"],
            ["Shift", "G"],
        ],
        [["Space"], ["Space"]],
    ]);

    override(navigator, "platform", "MacIntel");

    const test_items = [];

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        common.adjust_mac_hotkey_hints(old_key);

        test_item.mac_key = mac_key;
        test_item.adjusted_key = old_key;
        test_items.push(test_item);
    }

    for (const test_item of test_items) {
        assert.deepStrictEqual(test_item.mac_key, test_item.adjusted_key);
    }
});

run_test("show password", () => {
    const password_selector = "#id_password ~ .password_visibility_toggle";

    $(password_selector)[0] = noop;

    function set_attribute(type) {
        $("#id_password").attr("type", type);
    }

    function check_assertion(type, present_class, absent_class) {
        assert.equal($("#id_password").attr("type"), type);
        assert.ok($(password_selector).hasClass(present_class));
        assert.ok(!$(password_selector).hasClass(absent_class));
    }

    const click_ev = {
        preventDefault() {},
        stopPropagation() {},
    };

    const key_ev = {
        key: "Enter",
        preventDefault() {},
        stopPropagation() {},
    };

    set_attribute("password");
    common.setup_password_visibility_toggle("#id_password", password_selector);

    const click_handler = $(password_selector).get_on_handler("click");

    const key_handler = $(password_selector).get_on_handler("keydown");

    click_handler(click_ev);
    check_assertion("text", "fa-eye", "fa-eye-slash");

    click_handler(click_ev);
    check_assertion("password", "fa-eye-slash", "fa-eye");

    key_handler(key_ev);
    check_assertion("text", "fa-eye", "fa-eye-slash");

    key_handler(key_ev);
    check_assertion("password", "fa-eye-slash", "fa-eye");

    click_handler(click_ev);

    common.reset_password_toggle_icons("#id_password", password_selector);
    check_assertion("password", "fa-eye-slash", "fa-eye");
});
