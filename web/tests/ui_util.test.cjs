"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const ui_util = zrequire("ui_util");

run_test("potentially_collapse_quotes", ({override_rewire}) => {
    const $element = $.create("message-content");
    let children = [];
    $element.children = () => children;

    children = [
        $.create("normal paragraph 1"),
        $.create("blockquote"),
        $.create("normal paragraph 2"),
        $.create("user said paragraph"),
        $.create("message quote"),
        $.create("normal paragraph 3"),
    ];
    override_rewire(ui_util, "get_collapsible_status_array", () => [
        false,
        true,
        false,
        true,
        true,
        false,
    ]);
    // When there are both collapsible and non-collapsible elements, for
    // multiple collapsible elements in a row, only the first element
    // should be collapsed, and the rest's text should be removed. Non-
    // collapsible elements should not be touched.
    let collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, true);
    let expected_texts = ["never-been-set", "[…]", "never-been-set", "[…]", "", "never-been-set"];
    assert.deepEqual(
        $element.children().map(($el) => $el.text()),
        expected_texts,
    );

    children = [
        $.create("normal paragraph 4"),
        $.create("normal paragraph 5"),
        $.create("normal paragraph 6"),
    ];
    override_rewire(ui_util, "get_collapsible_status_array", () => [false, false, false]);
    // For all non-collapsible elements, none should be collapsed.
    collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, false);
    expected_texts = ["never-been-set", "never-been-set", "never-been-set"];
    assert.deepEqual(
        $element.children().map(($el) => $el.text()),
        expected_texts,
    );

    children = [$.create("blockquote 1"), $.create("blockquote 2"), $.create("blockquote 3")];
    override_rewire(ui_util, "get_collapsible_status_array", () => [true, true, true]);
    // For all collapsible elements, none should be collapsed.
    collapsed = ui_util.potentially_collapse_quotes($element);
    assert.equal(collapsed, false);
    expected_texts = ["never-been-set", "never-been-set", "never-been-set"];
    assert.deepEqual(
        $element.children().map(($el) => $el.text()),
        expected_texts,
    );
});

run_test("replace_emoji_name_with_emoji_unicode", () => {
    const $emoji = $.create("span").attr("class", "emoji emoji-1f419");
    $emoji.is = () => false;

    const octopus_emoji = "🐙";
    assert.equal(octopus_emoji, ui_util.convert_emoji_element_to_unicode($emoji));

    $emoji.attr("class", "emoji emoji-1f468-200d-1f373");
    const man_cook_emoji = "👨‍🍳";
    assert.equal(man_cook_emoji, ui_util.convert_emoji_element_to_unicode($emoji));
});

run_test("ublockorigin_hidden_img_restored", () => {
    // This needs to stub out so much that zjquery doesn't have, we just
    // make it from scratch.

    const ublockorigin_attr = "xzotehdedxqo";

    let filter_called;
    let remove_attribute_called;
    let $img;

    const make_img = (attributes) => {
        const img_element = {
            // `<element>.attributes` is a NamedNodeMap, but we can't create one here.
            // However we just need to iterate over it, so we can simulate it with an array.
            attributes,
            removeAttribute(attr) {
                remove_attribute_called = true;
                assert.equal(attr, ublockorigin_attr);
            },
        };

        const $i = {
            filter(param) {
                filter_called = true;
                assert.equal(param, ":hidden");
                return $img;
            },
            each(f) {
                f(0, img_element);
            },
        };

        return $i;
    };

    // Case 0:
    // uBlock Origin attribute present and removed

    filter_called = false;
    remove_attribute_called = false;

    $img = make_img([
        {name: "class", value: "img"},
        {name: "src", value: "/not-gravatar.png"},
        {name: ublockorigin_attr, value: ""},
    ]);
    ui_util.restore_ublockorigin_hidden_img($img);

    assert.ok(filter_called);
    assert.ok(remove_attribute_called);

    // Case 1:
    // No uBlock Origin attribute, no attributes removed.

    filter_called = false;
    remove_attribute_called = false;

    $img = make_img([
        {name: "class", value: "img"},
        {name: "src", value: "/not-gravatar.png"},
    ]);
    ui_util.restore_ublockorigin_hidden_img($img);

    assert.ok(filter_called);
    assert.ok(!remove_attribute_called);

    // Case 2:
    // uBlock Origin attribute present but not empty. No
    // attributes removed.

    filter_called = false;
    remove_attribute_called = false;

    $img = make_img([
        {name: "class", value: "img"},
        {name: ublockorigin_attr, value: "oops"},
        {name: "src", value: "/not-gravatar.png"},
    ]);
    ui_util.restore_ublockorigin_hidden_img($img);

    assert.ok(filter_called);
    assert.ok(!remove_attribute_called);

    // Case 3:
    // uBlock Origin attribute present along with another
    // mystery attribute. No attributes removed.

    filter_called = false;
    remove_attribute_called = false;

    $img = make_img([
        {name: "class", value: "img"},
        {name: "src", value: "/not-gravatar.png"},
        {name: ublockorigin_attr, value: ""},
        {name: "mysteryattribute", value: ""},
    ]);
    ui_util.restore_ublockorigin_hidden_img($img);

    assert.ok(filter_called);
    assert.ok(!remove_attribute_called);
});
