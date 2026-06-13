"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const dom = new JSDOM("");
set_global("document", dom.window.document);
set_global("HTMLElement", dom.window.HTMLElement);
set_global("DocumentFragment", dom.window.DocumentFragment);

// Add emoji tooltip template to the test DOM.
const template = dom.window.document.createElement("template");
template.id = "emoji-tooltip-template";
template.innerHTML =
    '<div class="emoji-tooltip-content">' +
    '<div class="emoji-tooltip-emoji"></div>' +
    '<div class="emoji-tooltip-name"></div>' +
    "</div>";
dom.window.document.body.append(template);

const emoji_tooltip = zrequire("emoji_tooltip");

run_test("build_emoji_tooltip_content: image emoji", () => {
    // Custom emoji have title with spaces (markdown replaces _ with space).
    const emoji_element = document.createElement("img");
    emoji_element.setAttribute("title", "heart eyes");
    emoji_element.classList.add("emoji");

    const fragment = emoji_tooltip.build_emoji_tooltip_content(emoji_element, "heart eyes");

    // The tooltip must show canonical :name: with underscores, not spaces.
    const name_el = fragment.querySelector(".emoji-tooltip-name");
    assert.equal(name_el.textContent, ":heart_eyes:");

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji img");
    assert.ok(enlarged_emoji !== null);
    assert.ok(enlarged_emoji.classList.contains("emoji-tooltip-enlarged"));
    assert.equal(enlarged_emoji.getAttribute("title"), null);
    assert.equal(enlarged_emoji.getAttribute("aria-label"), null);

    // Original should retain its state except for aria-label persistence.
    assert.equal(emoji_element.getAttribute("title"), "heart eyes");
    assert.equal(emoji_element.getAttribute("aria-label"), "heart eyes");
    assert.ok(!emoji_element.classList.contains("emoji-tooltip-enlarged"));
});

run_test("build_emoji_tooltip_content: span emoji", () => {
    // Standard emoji have both title and aria-label with spaces.
    const emoji_element = document.createElement("span");
    emoji_element.classList.add("emoji", "emoji-1f60d");
    emoji_element.setAttribute("aria-label", "smiling face with heart eyes");
    emoji_element.setAttribute("title", "smiling face with heart eyes");
    emoji_element.textContent = "\u{1F60D}";

    const fragment = emoji_tooltip.build_emoji_tooltip_content(
        emoji_element,
        "smiling face with heart eyes",
    );

    // The tooltip must show canonical :name: with underscores.
    const name_el = fragment.querySelector(".emoji-tooltip-name");
    assert.equal(name_el.textContent, ":smiling_face_with_heart_eyes:");

    const enlarged_emoji = fragment.querySelector(".emoji-tooltip-emoji span");
    assert.ok(enlarged_emoji !== null);
    assert.ok(enlarged_emoji.classList.contains("emoji-tooltip-enlarged"));
    assert.equal(enlarged_emoji.getAttribute("title"), null);
    assert.equal(enlarged_emoji.getAttribute("aria-label"), null);

    // Existing aria-label should not be overwritten.
    assert.equal(emoji_element.getAttribute("aria-label"), "smiling face with heart eyes");
});

run_test("build_emoji_tooltip_content: repeated hover persistence", () => {
    // Custom emoji: title has spaces, no aria-label initially.
    const emoji_element = document.createElement("img");
    emoji_element.setAttribute("title", "green tick");
    emoji_element.classList.add("emoji");

    // First hover: caller reads name (with spaces) and removes title.
    let name = emoji_element.getAttribute("title") ?? emoji_element.getAttribute("aria-label");
    emoji_element.removeAttribute("title");
    assert.equal(name, "green tick");

    emoji_tooltip.build_emoji_tooltip_content(emoji_element, name);

    assert.equal(emoji_element.getAttribute("title"), null);
    assert.equal(emoji_element.getAttribute("aria-label"), "green tick");

    // Second hover: name should still resolve via aria-label.
    name = emoji_element.getAttribute("title") ?? emoji_element.getAttribute("aria-label");
    assert.equal(name, "green tick");

    const fragment = emoji_tooltip.build_emoji_tooltip_content(emoji_element, name);
    const name_el = fragment.querySelector(".emoji-tooltip-name");
    // Must render canonical :name: with underscores despite input having spaces.
    assert.equal(name_el.textContent, ":green_tick:");
});
