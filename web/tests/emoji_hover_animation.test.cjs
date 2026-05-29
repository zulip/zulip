"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const {initialize_user_settings} = zrequire("user_settings");
const emoji_hover_animation = zrequire("emoji_hover_animation");

const user_settings = {web_animate_image_previews: "on_hover"};
initialize_user_settings({user_settings});

const TRIGGER_SELECTOR = ".emoji-animation-hover-area, img.emoji[data-animated-url]";
const ANIMATED_EMOJI_SELECTOR = "img.emoji[data-animated-url]";

function get_trigger_handler() {
    emoji_hover_animation.initialize();
    return $("body").get_on_handler("mouseenter mouseleave focusin focusout", TRIGGER_SELECTOR);
}

// Builds an animated emoji stub in the state the `realm_emoji` partial
// renders for `on_hover` mode: showing the still frame, with both URLs
// available for the swap.
function make_animated_emoji(name, {inside_hover_area = false} = {}) {
    const $emoji = $.create(name);
    $emoji.attr("src", `${name}-still.png`);
    $emoji.attr("data-still-url", `${name}-still.png`);
    $emoji.attr("data-animated-url", `${name}-animated.png`);
    $emoji.set_matches(".emoji-animation-hover-area", false);
    $emoji.set_matches(ANIMATED_EMOJI_SELECTOR, true);
    $emoji.set_matches(":hover", false);
    $emoji.set_closest_results(
        ".emoji-animation-hover-area",
        inside_hover_area ? [$.create(`${name}-ancestor-area`)] : [],
    );
    return $emoji;
}

function make_hover_area(name, emojis) {
    const $area = $.create(name);
    $area.set_matches(".emoji-animation-hover-area", true);
    $area.set_matches(ANIMATED_EMOJI_SELECTOR, false);
    $area.set_matches(":hover", false);
    $area.set_find_results(ANIMATED_EMOJI_SELECTOR, emojis);
    return $area;
}

function hover(handler, $trigger) {
    $trigger.set_matches(":hover", true);
    handler.call($trigger[0]);
}

function unhover(handler, $trigger) {
    $trigger.set_matches(":hover", false);
    handler.call($trigger[0]);
}

run_test("emoji is its own trigger", () => {
    const handler = get_trigger_handler();
    const $emoji = make_animated_emoji("img.solo-emoji");

    hover(handler, $emoji);
    assert.equal($emoji.attr("src"), "img.solo-emoji-animated.png");

    unhover(handler, $emoji);
    assert.equal($emoji.attr("src"), "img.solo-emoji-still.png");
});

run_test("ancestor hover area owns the swap", () => {
    const handler = get_trigger_handler();
    const $first = make_animated_emoji("img.first-emoji", {inside_hover_area: true});
    const $second = make_animated_emoji("img.second-emoji", {inside_hover_area: true});
    const $area = make_hover_area(".reaction-pill", [...$first, ...$second]);

    // Hovering the area animates every animated emoji inside it.
    hover(handler, $area);
    assert.equal($first.attr("src"), "img.first-emoji-animated.png");
    assert.equal($second.attr("src"), "img.second-emoji-animated.png");

    unhover(handler, $area);
    assert.equal($first.attr("src"), "img.first-emoji-still.png");
    assert.equal($second.attr("src"), "img.second-emoji-still.png");

    // The emoji's own event is a no-op, so the same pointer movement
    // doesn't run the swap twice.
    hover(handler, $area);
    hover(handler, $first);
    assert.equal($first.attr("src"), "img.first-emoji-animated.png");
    unhover(handler, $first);
    assert.equal(
        $first.attr("src"),
        "img.first-emoji-animated.png",
        "leaving the emoji for elsewhere in the hover area keeps it animating",
    );
});

run_test("keyboard focus animates too", () => {
    const handler = get_trigger_handler();
    const $emoji = make_animated_emoji("img.focusable-emoji");
    const $area = make_hover_area(".emoji-picker-cell", [...$emoji]);

    $area.trigger("focusin");
    handler.call($area[0]);
    assert.equal($emoji.attr("src"), "img.focusable-emoji-animated.png");

    // Moving the mouse off a still-focused trigger must not stop it.
    hover(handler, $area);
    unhover(handler, $area);
    assert.equal($emoji.attr("src"), "img.focusable-emoji-animated.png");

    $area.trigger("focusout");
    handler.call($area[0]);
    assert.equal($emoji.attr("src"), "img.focusable-emoji-still.png");
});

run_test("emoji with no animated URL is left alone", () => {
    const handler = get_trigger_handler();
    const $area = make_hover_area(".pill-with-static-emoji", []);
    const $static_emoji = $.create("img.static-emoji");
    $static_emoji.attr("src", "static.png");
    $static_emoji.set_matches(".emoji-animation-hover-area", false);
    $static_emoji.set_matches(ANIMATED_EMOJI_SELECTOR, false);
    $static_emoji.set_matches(":hover", false);

    hover(handler, $area);
    hover(handler, $static_emoji);
    assert.equal($static_emoji.attr("src"), "static.png");
});

run_test("other animation settings never animate", ({override}) => {
    const handler = get_trigger_handler();

    for (const setting of ["always", "never"]) {
        const $emoji = make_animated_emoji(`img.emoji-${setting}`);
        override(user_settings, "web_animate_image_previews", setting);
        hover(handler, $emoji);
        assert.equal(
            $emoji.attr("src"),
            `img.emoji-${setting}-still.png`,
            `hovering must not animate in ${setting} mode`,
        );
    }
});
