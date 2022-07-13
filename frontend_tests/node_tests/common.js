"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = () => {};

mock_esm("tippy.js", {
    default: (arg) => {
        arg._tippy = {setContent: noop};
        return arg._tippy;
    },
});

set_global("document", {});
const navigator = set_global("navigator", {});

const common = zrequire("common");

run_test("basics", () => {
    common.autofocus("#home");
    $.get_initialize_function()();
    assert.ok($("#home").is_focused());
    $.clear_initialize_function();
});

run_test("phrase_match", () => {
    assert.ok(common.phrase_match("tes", "test"));
    assert.ok(common.phrase_match("Tes", "test"));
    assert.ok(common.phrase_match("Tes", "Test"));
    assert.ok(common.phrase_match("tes", "Stream Test"));

    assert.ok(!common.phrase_match("tests", "test"));
    assert.ok(!common.phrase_match("tes", "hostess"));
});

run_test("copy_data_attribute_value", ({override}) => {
    const admin_emails_val = "iago@zulip.com";

    const $input = $.create("input");

    let removed;
    $input.remove = () => {
        removed = true;
    };

    override(document, "createElement", () => $input);
    override(document, "execCommand", noop);

    $("body").append = noop;
    $($input).val = (arg) => {
        assert.equal(arg, admin_emails_val);
        return {
            trigger: noop,
        };
    };

    const $elem = {};
    let faded_in = false;
    let faded_out = false;

    $elem.data = (key) => {
        assert.equal(key, "admin-emails");
        return admin_emails_val;
    };
    $elem.fadeOut = (val) => {
        assert.equal(val, 250);
        faded_out = true;
    };
    $elem.fadeIn = (val) => {
        assert.equal(val, 1000);
        faded_in = true;
    };
    common.copy_data_attribute_value($elem, "admin-emails");
    assert.ok(removed);
    assert.ok(faded_in);
    assert.ok(faded_out);
});

run_test("adjust_mac_shortcuts non-mac", ({override}) => {
    override(navigator, "platform", "Windows");

    // The adjust_mac_shortcuts has a really simple guard
    // at the top, and we just test the early-return behavior
    // by trying to pass it garbage.
    common.adjust_mac_shortcuts("selector-that-does-not-exist");
});

// Test non-default value of adjust_mac_shortcuts boolean parameter:
// `kbd_elem = false`.
run_test("adjust_mac_shortcuts mac non-defaults", ({override}) => {
    const keys_to_test_mac = new Map([
        ["Backspace", "Delete"],
        ["Enter", "Return"],
        ["Home", "←"],
        ["End", "→"],
        ["PgUp", "↑"],
        ["PgDn", "↓"],
        ["Ctrl", "⌘"],
        ["X + Shift", "X + Shift"],
        ["⌘ + Return", "⌘ + Return"],
        ["Enter or Backspace", "Enter or Backspace"],
        ["#stream_name", "#stream_name"],
        ["Ctrl+K", "Ctrl+K"],
    ]);

    const fn_shortcuts = new Set(["Home", "End", "PgUp", "PgDn"]);
    const inserted_fn_key = "<code>Fn</code> + ";

    override(navigator, "platform", "MacIntel");

    const kbd_element = false;

    const test_items = [];
    let key_no = 1;

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        const $stub = $.create("hotkey_" + key_no);
        $stub.text(old_key);
        assert.equal($stub.hasClass("arrow-key"), false);
        if (fn_shortcuts.has(old_key)) {
            $stub.before = ($elem) => {
                assert.equal($elem, inserted_fn_key);
            };
        }
        test_item.$stub = $stub;
        test_item.mac_key = mac_key;
        test_item.adds_arrow_key = fn_shortcuts.has(old_key) && kbd_element;
        test_items.push(test_item);
        key_no += 1;
    }

    const children = test_items.map((test_item) => ({to_$: () => test_item.$stub}));

    $.create(".markdown_content", {children});

    common.adjust_mac_shortcuts(".markdown_content", kbd_element);

    for (const test_item of test_items) {
        assert.equal(test_item.$stub.text(), test_item.mac_key);
        assert.equal(test_item.$stub.hasClass("arrow-key"), test_item.adds_arrow_key);
    }
});

// Test default value of adjust_mac_shortcuts boolean parameter:
// `kbd_elem = true`.
run_test("adjust_mac_shortcuts mac defaults", ({override}) => {
    const keys_to_test_mac = new Map([
        ["Backspace", "Delete"],
        ["Enter", "Return"],
        ["Home", "←"],
        ["End", "→"],
        ["PgUp", "↑"],
        ["PgDn", "↓"],
        ["Ctrl", "⌘"],
        ["[", "["],
        ["X", "X"],
    ]);

    const fn_shortcuts = new Set(["Home", "End", "PgUp", "PgDn"]);
    const inserted_fn_key = "<kbd>Fn</kbd> + ";

    override(navigator, "platform", "MacIntel");

    const kbd_element = true;

    const test_items = [];
    let key_no = 1;

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        const $stub = $.create("hotkey_" + key_no);
        $stub.text(old_key);
        assert.equal($stub.hasClass("arrow-key"), false);
        if (fn_shortcuts.has(old_key)) {
            $stub.before = ($elem) => {
                assert.equal($elem, inserted_fn_key);
            };
        }
        test_item.$stub = $stub;
        test_item.mac_key = mac_key;
        test_item.adds_arrow_key = fn_shortcuts.has(old_key) && kbd_element;
        test_items.push(test_item);
        key_no += 1;
    }

    const children = test_items.map((test_item) => ({to_$: () => test_item.$stub}));

    $.create(".hotkeys_table kbd", {children});

    common.adjust_mac_shortcuts(".hotkeys_table kbd");

    for (const test_item of test_items) {
        assert.equal(test_item.$stub.text(), test_item.mac_key);
        assert.equal(test_item.$stub.hasClass("arrow-key"), test_item.adds_arrow_key);
    }
});

run_test("show password", () => {
    const password_selector = "#id_password ~ .password_visibility_toggle";

    $(password_selector)[0] = () => {};

    function set_attribute(type) {
        $("#id_password").attr("type", type);
    }

    function check_assertion(type, present_class, absent_class) {
        assert.equal($("#id_password").attr("type"), type);
        assert.ok($(password_selector).hasClass(present_class));
        assert.ok(!$(password_selector).hasClass(absent_class));
    }

    const ev = {
        preventDefault: () => {},
        stopPropagation: () => {},
    };

    set_attribute("password");
    common.setup_password_visibility_toggle("#id_password", password_selector);

    const handler = $(password_selector).get_on_handler("click");

    handler(ev);
    check_assertion("text", "fa-eye", "fa-eye-slash");

    handler(ev);
    check_assertion("password", "fa-eye-slash", "fa-eye");

    handler(ev);

    common.reset_password_toggle_icons("#id_password", password_selector);
    check_assertion("password", "fa-eye-slash", "fa-eye");
});
