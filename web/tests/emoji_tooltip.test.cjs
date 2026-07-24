"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// One JSDOM window for `document`, `HTMLElement`, and `DocumentFragment`
// so nodes we build and nodes `parse_html` produces share one
// `HTMLElement`, which the module's `instanceof` check requires.
const {window} = new JSDOM("");
set_global("document", window.document);
set_global("HTMLElement", window.HTMLElement);
set_global("DocumentFragment", window.DocumentFragment);

const emoji_tooltip = zrequire("emoji_tooltip");

// Builds the four kinds of emoji element we read names from, matching
// how markdown.ts and status_emoji.hbs render them.
function make_custom_emoji() {
    // Custom emoji: <img> with the canonical name in `alt` and the
    // human-friendly name in `title`.
    const img = document.createElement("img");
    img.classList.add("emoji");
    img.setAttribute("alt", ":heart_eyes:");
    img.setAttribute("title", "heart eyes");
    return img;
}

function make_unicode_emoji() {
    // Unicode emoji: <span> with the canonical name as text content and
    // the human-friendly name in both `title` and `aria-label`.
    const span = document.createElement("span");
    span.classList.add("emoji", "emoji-1f60d");
    span.setAttribute("title", "smiling face with heart eyes");
    span.setAttribute("aria-label", "smiling face with heart eyes");
    span.textContent = ":smiling_face_with_heart_eyes:";
    return span;
}

function make_status_emoji_span() {
    // Unicode status emoji: <span> with the canonical name only in
    // `data-tippy-content`; no text content and no `title`.
    const span = document.createElement("span");
    span.classList.add("emoji", "status-emoji", "status-emoji-name", "emoji-1f4bb");
    span.setAttribute("data-tippy-content", ":working_on_it:");
    return span;
}

run_test("get_canonical_emoji_name reads the name from the DOM", () => {
    assert.equal(emoji_tooltip.get_canonical_emoji_name(make_custom_emoji()), "heart_eyes");
    assert.equal(
        emoji_tooltip.get_canonical_emoji_name(make_unicode_emoji()),
        "smiling_face_with_heart_eyes",
    );
    assert.equal(emoji_tooltip.get_canonical_emoji_name(make_status_emoji_span()), "working_on_it");

    // Custom status emoji <img> carry the name only in
    // `data-tippy-content` (no `alt`).
    const status_img = document.createElement("img");
    status_img.classList.add("emoji", "status-emoji", "status-emoji-name");
    status_img.setAttribute("data-tippy-content", ":late_night_work:");
    assert.equal(emoji_tooltip.get_canonical_emoji_name(status_img), "late_night_work");

    // No `:name:` syntax yields "", so callers can decline to show a tooltip.
    const bare = document.createElement("span");
    bare.classList.add("emoji");
    assert.equal(emoji_tooltip.get_canonical_emoji_name(bare), "");
});

run_test("build_emoji_tooltip_content renders an enlarged copy and :name:", () => {
    const fragment = emoji_tooltip.build_emoji_tooltip_content(
        make_unicode_emoji(),
        "party_popper",
    );

    const name_element = fragment.querySelector(".emoji-tooltip-name");
    assert.equal(name_element.textContent, ":party_popper:");

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji span");
    assert.ok(enlarged_emoji !== null);
    assert.ok(enlarged_emoji.classList.contains("emoji-tooltip-enlarged"));
    // The sprite class is preserved so the enlarged emoji still renders.
    assert.ok(enlarged_emoji.classList.contains("emoji-1f60d"));
    // The decorative copy is hidden from assistive tech (Unicode emoji
    // carry role="img") and its labeling attributes are dropped.
    assert.equal(enlarged_emoji.getAttribute("aria-hidden"), "true");
    assert.equal(enlarged_emoji.getAttribute("title"), null);
    assert.equal(enlarged_emoji.getAttribute("aria-label"), null);
});

run_test("build_emoji_tooltip_content strips status-emoji layout from the copy", () => {
    const fragment = emoji_tooltip.build_emoji_tooltip_content(
        make_status_emoji_span(),
        "working_on_it",
    );

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji span");
    assert.ok(enlarged_emoji !== null);
    // Status-emoji layout classes and `data-tippy-content` are dropped.
    assert.ok(!enlarged_emoji.classList.contains("status-emoji"));
    assert.ok(!enlarged_emoji.classList.contains("status-emoji-name"));
    assert.equal(enlarged_emoji.getAttribute("data-tippy-content"), null);
});

run_test("build_emoji_tooltip_content does not mutate the original element", () => {
    const emoji_element = make_custom_emoji();

    emoji_tooltip.build_emoji_tooltip_content(emoji_element, "heart_eyes");

    // The helper is pure: the original element keeps its attributes/classes.
    assert.equal(emoji_element.getAttribute("title"), "heart eyes");
    assert.equal(emoji_element.getAttribute("alt"), ":heart_eyes:");
    assert.ok(!emoji_element.classList.contains("emoji-tooltip-enlarged"));
});

run_test("show_emoji_tooltip renders content, or declines when unnamed", () => {
    let content = null;
    const instance = {
        reference: make_custom_emoji(),
        setContent(fragment) {
            content = fragment;
        },
    };
    // Named emoji: sets the enlarged content and allows the tooltip to show.
    assert.equal(emoji_tooltip.show_emoji_tooltip(instance), undefined);
    assert.equal(content.querySelector(".emoji-tooltip-name").textContent, ":heart_eyes:");

    // No name: returns false so the delegate skips showing an empty tooltip.
    content = null;
    const bare = document.createElement("span");
    bare.classList.add("emoji");
    assert.equal(emoji_tooltip.show_emoji_tooltip({reference: bare, setContent() {}}), false);
});
