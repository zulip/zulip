"use strict";

const assert = require("node:assert/strict");

const {set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const navigator = {};
set_global("navigator", navigator);

const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

/*
    Note that the test runner automatically registers
    all of our handlers.
*/

run_test("and", () => {
    const args = {
        last: true,
    };

    const html = require("./templates/and.hbs")(args);
    assert.equal(html, "<p>empty and</p>\n<p>last and</p>\n\n");
});

run_test("or", () => {
    const args = {
        last: true,
    };

    const html = require("./templates/or.hbs")(args);
    assert.equal(html, "\n<p>last or</p>\n<p>true or</p>\n");
});

run_test("rendered_markdown", () => {
    const html = require("./templates/rendered_markdown.hbs")();
    const expected_html =
        '<a href="http://example.com" target="_blank" rel="noopener noreferrer" title="http://example.com/">good</a>\n';
    assert.equal(html, expected_html);
});

run_test("numberFormat", () => {
    const args = {
        number: 1000000,
    };

    const html = require("./templates/numberFormat.hbs")(args);
    assert.equal(html, "1,000,000\n");
});

run_test("tooltip_hotkey_hints", () => {
    const args = {
        hotkey_one: "Ctrl",
        hotkey_two: "C",
    };

    const html = require("./templates/tooltip_hotkey_hints.hbs")(args);
    const expected_html = `<span class="tooltip-hotkey-hints"><span class="tooltip-hotkey-hint">${args.hotkey_one}</span><span class="tooltip-hotkey-hint">${args.hotkey_two}</span></span>\n`;
    assert.equal(html, expected_html);
});

run_test("popover_hotkey_hints", () => {
    const args = {
        hotkey_one: "Ctrl",
        hotkey_two: "[",
    };

    const html = require("./templates/popover_hotkey_hints.hbs")(args);
    const expected_html = `<span class="popover-menu-hotkey-hints"><span class="popover-menu-hotkey-hint">${args.hotkey_one}</span><span class="popover-menu-hotkey-hint">${args.hotkey_two}</span></span>\n`;
    assert.equal(html, expected_html);
});

run_test("popover_hotkey_hints mac command", () => {
    const args = {
        hotkey_one: "Ctrl",
        hotkey_two: "[",
    };

    with_overrides(({override}) => {
        override(navigator, "platform", "MacIntel");
        const html = require("./templates/popover_hotkey_hints.hbs")(args);
        const expected_html =
            '<span class="popover-menu-hotkey-hints"><span class="popover-menu-hotkey-hint"><i class="zulip-icon zulip-icon-mac-command" aria-hidden="true"></i></span><span class="popover-menu-hotkey-hint">[</span></span>\n';
        assert.equal(html, expected_html);
    });
});

run_test("popover_hotkey_hints_shift_hotkey", () => {
    const args = {
        hotkey_one: "Shift",
        hotkey_two: "V",
    };

    const html = require("./templates/popover_hotkey_hints.hbs")(args);
    args.hotkey_one = "⇧"; // adjust_shift_hotkey
    const expected_html = `<span class="popover-menu-hotkey-hints popover-contains-shift-hotkey" data-hotkey-hints="${args.hotkey_one},${args.hotkey_two}"><span class="popover-menu-hotkey-hint">${args.hotkey_one}</span><span class="popover-menu-hotkey-hint">${args.hotkey_two}</span></span>\n`;
    assert.equal(html, expected_html);
});

run_test("list_each", ({override}) => {
    assert.equal(
        require("./templates/list_each.hbs")({stuff: [{name: "x"}, {name: "y"}, {name: "z"}]}),
        `\
<b>x</b>, <b>y</b>, and <b>z</b>
<b>x</b> <b>y</b> <b>z</b>
`,
    );
    assert.equal(
        require("./templates/list_each.hbs")({stuff: {}}),
        `\
empty

`,
    );
    override(user_settings, "default_language", "zh-Hans");
    assert.equal(
        require("./templates/list_each.hbs")({stuff: [{name: "水"}, {name: "粥"}, {name: "粥"}]}),
        `\
<b>水</b>、<b>粥</b>和<b>粥</b>
<b>水</b><b>粥</b><b>粥</b>
`,
    );
});
