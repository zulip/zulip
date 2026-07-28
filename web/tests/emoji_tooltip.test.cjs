"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const render_status_emoji = require("../templates/status_emoji.hbs");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// One JSDOM window, so nodes we build and nodes `parse_html` produces
// share the `HTMLElement` the module's `instanceof` check needs.
const {window} = new JSDOM("");
set_global("document", window.document);
set_global("HTMLElement", window.HTMLElement);
set_global("DocumentFragment", window.DocumentFragment);

const emoji = zrequire("emoji");
const emoji_codes = zrequire("../../static/generated/emoji/emoji_codes.json");
const linkifiers = zrequire("linkifiers");
const markdown = zrequire("markdown");
const markdown_config = zrequire("markdown_config");
const {initialize_user_settings} = zrequire("user_settings");
const emoji_tooltip = zrequire("emoji_tooltip");

initialize_user_settings({user_settings: {translate_emoticons: false}});
emoji.initialize({
    realm_emoji: {
        1: {
            id: 1,
            name: "green_tick",
            source_url: "/static/generated/emoji/images/emoji/green_tick.png",
            deactivated: false,
        },
    },
    emoji_codes,
});
linkifiers.initialize([]);
markdown.initialize(markdown_config.get_helpers());

function render_message_emoji(raw_content) {
    const message_content = document.createElement("div");
    message_content.innerHTML = markdown.render(raw_content).content;
    const emoji_element = message_content.querySelector(".emoji");
    assert.ok(emoji_element !== null);
    return emoji_element;
}

function render_status_emoji_element(status_emoji_info) {
    const container = document.createElement("div");
    container.innerHTML = render_status_emoji(status_emoji_info);
    const emoji_element = container.querySelector(".status-emoji-name");
    assert.ok(emoji_element !== null);
    return emoji_element;
}

run_test("get_canonical_emoji_name reads the name from the DOM", () => {
    assert.equal(
        emoji_tooltip.get_canonical_emoji_name(render_message_emoji(":heart_eyes:")),
        "heart_eyes",
    );

    // Reading `title` instead of `alt` here would yield `:green tick:`.
    const custom_emoji = render_message_emoji(":green_tick:");
    assert.equal(custom_emoji.getAttribute("title"), "green tick");
    assert.equal(emoji_tooltip.get_canonical_emoji_name(custom_emoji), "green_tick");

    // Status emoji carry the name only in `data-tippy-content`.
    const unicode_status_emoji = render_status_emoji_element(
        emoji.get_emoji_details_by_name("working_on_it"),
    );
    assert.equal(emoji_tooltip.get_canonical_emoji_name(unicode_status_emoji), "working_on_it");

    const custom_status_emoji = render_status_emoji_element(
        emoji.get_emoji_details_by_name("green_tick"),
    );
    assert.equal(custom_status_emoji.nodeName, "IMG");
    assert.equal(custom_status_emoji.getAttribute("alt"), null);
    assert.equal(emoji_tooltip.get_canonical_emoji_name(custom_status_emoji), "green_tick");

    // Nothing we render omits the `:name:`, so build that case by hand.
    const unnamed_emoji = document.createElement("span");
    unnamed_emoji.classList.add("emoji");
    assert.equal(emoji_tooltip.get_canonical_emoji_name(unnamed_emoji), undefined);
});

run_test("build_emoji_tooltip_content renders an enlarged copy and :name:", () => {
    const fragment = emoji_tooltip.build_emoji_tooltip_content(
        render_message_emoji(":heart_eyes:"),
        "heart_eyes",
    );

    assert.equal(fragment.querySelector(".emoji-tooltip-name").textContent, ":heart_eyes:");

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji span");
    assert.ok(enlarged_emoji !== null);
    assert.ok(enlarged_emoji.classList.contains("emoji-tooltip-enlarged"));
    // The sprite class is what actually draws the emoji.
    assert.ok(enlarged_emoji.classList.contains("emoji-1f60d"));
    // The copy keeps markdown's role="img", so it needs hiding from screen
    // readers to avoid announcing an unnamed image.
    assert.equal(enlarged_emoji.getAttribute("role"), "img");
    assert.equal(enlarged_emoji.getAttribute("aria-hidden"), "true");
    assert.equal(enlarged_emoji.getAttribute("title"), null);
    assert.equal(enlarged_emoji.getAttribute("aria-label"), null);
});

run_test("build_emoji_tooltip_content strips status-emoji layout from the copy", () => {
    const fragment = emoji_tooltip.build_emoji_tooltip_content(
        render_status_emoji_element(emoji.get_emoji_details_by_name("working_on_it")),
        "working_on_it",
    );

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji span");
    assert.ok(enlarged_emoji !== null);
    assert.ok(!enlarged_emoji.classList.contains("status-emoji"));
    assert.ok(!enlarged_emoji.classList.contains("status-emoji-name"));
    assert.equal(enlarged_emoji.getAttribute("data-tippy-content"), null);
});

run_test("build_emoji_tooltip_content does not mutate the original element", () => {
    const emoji_element = render_message_emoji(":green_tick:");

    emoji_tooltip.build_emoji_tooltip_content(emoji_element, "green_tick");

    assert.equal(emoji_element.getAttribute("title"), "green tick");
    assert.equal(emoji_element.getAttribute("alt"), ":green_tick:");
    assert.ok(!emoji_element.classList.contains("emoji-tooltip-enlarged"));
});

run_test("show_emoji_tooltip renders content, or declines when unnamed", () => {
    let content = null;
    const instance = {
        reference: render_message_emoji(":green_tick:"),
        setContent(fragment) {
            content = fragment;
        },
    };
    assert.equal(emoji_tooltip.show_emoji_tooltip(instance), undefined);
    assert.equal(content.querySelector(".emoji-tooltip-name").textContent, ":green_tick:");

    // Returning false keeps the delegate from showing an empty tooltip.
    const unnamed_emoji = document.createElement("span");
    unnamed_emoji.classList.add("emoji");
    assert.equal(
        emoji_tooltip.show_emoji_tooltip({reference: unnamed_emoji, setContent() {}}),
        false,
    );
});
