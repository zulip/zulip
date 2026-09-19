"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

set_global("document", "document-stub");
class TransitionEvent {
    constructor(propertyName) {
        this.propertyName = propertyName;
    }
}
set_global("TransitionEvent", TransitionEvent);

// The button hides itself 3 seconds after a scroll finishes, unless
// the mouse is hovering over it. Timers get distinct handles, so that
// a test notices one that was left running.
let hide_timer_callback;
let last_timer_id = 0;
const running_timers = new Set();
set_global("setInterval", (callback, delay) => {
    assert.equal(delay, 3000);
    hide_timer_callback = callback;
    last_timer_id += 1;
    running_timers.add(last_timer_id);
    return last_timer_id;
});
set_global("clearInterval", (id) => {
    running_timers.delete(id);
});

const message_lists = mock_esm("../src/message_lists", {current: undefined});
const message_scroll_state = mock_esm("../src/message_scroll_state", {
    actively_scrolling: false,
});
const message_viewport = mock_esm("../src/message_viewport");
const tippyjs = mock_esm("../src/tippyjs");

const scroll_to_bottom_button = zrequire("scroll_to_bottom_button");

const $container = () => $("#scroll-to-bottom-button-container");
const $icon = () => $("#scroll-to-bottom-button .zulip-icon");
const $clickable_area = () => $("#scroll-to-bottom-button-clickable-area");

function set_feed(
    override,
    {end_rendered = true, bottom_visible = true, view = "topic", id = 1} = {},
) {
    override(message_viewport, "bottom_rendered_message_visible", () => bottom_visible, {
        unused: false,
    });
    override(message_lists, "current", {
        id,
        visibly_empty: () => view === "empty",
        view: {is_end_rendered: () => end_rendered},
        data: {
            filter: {
                can_show_next_unread_topic_conversation_button: () => view === "topic",
                can_show_next_unread_dm_conversation_button: () => view === "dm",
            },
        },
    });
}

function assert_shown() {
    assert.ok($container().hasClass("show"));
}

function assert_hidden() {
    assert.ok(!$container().hasClass("show"));
    assert.equal(running_timers.size, 0);
}

function assert_scroll_to_bottom_mode() {
    assert.equal(scroll_to_bottom_button.mode, "scroll_to_bottom");
    assert.ok($icon().hasClass("zulip-icon-chevron-down"));
    assert.ok(!$icon().hasClass("zulip-icon-arrow-right"));
    assert.equal(
        $clickable_area().attr("data-tooltip-template-id"),
        "scroll-to-bottom-button-tooltip-template",
    );
}

function assert_next_unread_mode(mode, tooltip_template_id) {
    assert.equal(scroll_to_bottom_button.mode, mode);
    assert.ok($icon().hasClass("zulip-icon-arrow-right"));
    assert.ok(!$icon().hasClass("zulip-icon-chevron-down"));
    assert.equal($clickable_area().attr("data-tooltip-template-id"), tooltip_template_id);
    // The button stays until the user leaves the bottom of the feed.
    assert.equal(running_timers.size, 0);
}

function setup(override) {
    $icon().addClass("zulip-icon-chevron-down");
    $clickable_area().attr("data-tooltip-template-id", "scroll-to-bottom-button-tooltip-template");
    $container().set_matches(":hover", false);
    scroll_to_bottom_button.initialize();

    // Start every test with the button hidden, in its scroll to
    // bottom mode, regardless of what the previous test did; the
    // container is a fresh element, so showing the scroll to bottom
    // button always works, and a keypress then hides it.
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    keydown();
    running_timers.clear();
    hide_timer_callback = undefined;
    assert_hidden();
    assert_scroll_to_bottom_mode();
}

function keydown(modifiers = {}) {
    $(document).get_on_handler("keydown")({
        shiftKey: false,
        ctrlKey: false,
        metaKey: false,
        ...modifiers,
    });
}

run_test("outside message views", ({override}) => {
    setup(override);
    override(message_lists, "current", undefined);

    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_hidden();

    $container().addClass("show");
    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("empty feed", ({override}) => {
    setup(override);
    set_feed(override, {view: "empty"});

    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_hidden();

    $container().addClass("show");
    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("scroll to bottom after a mouse scroll", ({override}) => {
    setup(override);
    set_feed(override, {bottom_visible: false});

    // The button appears as soon as the scroll starts...
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_shown();
    assert_scroll_to_bottom_mode();

    // ...and starts its hide timer once the scroll finishes.
    scroll_to_bottom_button.update();
    assert_shown();
    assert.equal(running_timers.size, 1);

    // The timer keeps waiting while the mouse is over the button.
    $container().set_matches(":hover", true);
    hide_timer_callback();
    assert_shown();
    assert.equal(running_timers.size, 1);

    $container().set_matches(":hover", false);
    hide_timer_callback();
    assert_hidden();

    // Seeing the last rendered message is not enough when there are
    // more messages to render or fetch.
    set_feed(override, {end_rendered: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_shown();
    assert_scroll_to_bottom_mode();
});

run_test("scroll to bottom after a keyboard scroll", ({override}) => {
    setup(override);
    set_feed(override, {bottom_visible: false});

    // Keyboard scrolls skip show_scroll_to_bottom_button, so the
    // button stays hidden.
    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("keypress hides the scroll to bottom button", ({override}) => {
    setup(override);
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    scroll_to_bottom_button.update();
    assert_shown();

    keydown({shiftKey: true});
    assert_shown();

    keydown();
    assert_hidden();
});

run_test("next unread topic at the bottom of a topic", ({override}) => {
    setup(override);
    set_feed(override);

    // An open tooltip would otherwise keep saying "Scroll to bottom".
    let tooltip_content;
    $clickable_area()[0]._tippy = {
        setContent(content) {
            tooltip_content = content;
        },
    };
    override(tippyjs, "get_tooltip_content", (reference) => {
        assert.equal(reference, $clickable_area()[0]);
        return reference.getAttribute("data-tooltip-template-id");
    });

    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");
    assert.equal(tooltip_content, "next-unread-topic-button-tooltip-template");

    // Nothing changes while the user stays at the bottom, even if
    // they scroll within the visible area or type a reply.
    tooltip_content = undefined;
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    scroll_to_bottom_button.update();
    keydown();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");
    assert.equal(tooltip_content, undefined);
});

run_test("next unread DM conversation at the bottom of a DM view", ({override}) => {
    setup(override);
    set_feed(override, {view: "dm"});

    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode(
        "next_unread_dm_conversation",
        "next-unread-dm-conversation-button-tooltip-template",
    );
});

run_test("nothing to offer at the bottom of other views", ({override}) => {
    setup(override);
    set_feed(override, {view: "other"});

    scroll_to_bottom_button.update();
    assert_hidden();

    // Moving from the bottom of a topic to the bottom of, e.g., the
    // combined feed hides the button without swapping its icon while
    // it fades out.
    set_feed(override, {view: "topic"});
    scroll_to_bottom_button.update();
    assert_shown();
    set_feed(override, {view: "other"});
    scroll_to_bottom_button.update();
    assert_hidden();
    assert.ok($icon().hasClass("zulip-icon-arrow-right"));
});

run_test("spectators have no unread messages", ({override}) => {
    setup(override);
    set_feed(override);
    page_params.is_spectator = true;

    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("mouse scroll away from the bottom", ({override}) => {
    setup(override);
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");

    // The button waits for the scroll to finish before changing...
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");

    // ...and then offers to scroll back to the bottom.
    scroll_to_bottom_button.update();
    assert_shown();
    assert_scroll_to_bottom_mode();
    assert.equal(running_timers.size, 1);
});

run_test("keyboard scroll away from the bottom", ({override}) => {
    setup(override);
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();

    // The button hides without swapping its icon while it fades out.
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.update();
    assert_hidden();
    assert.ok($icon().hasClass("zulip-icon-arrow-right"));

    // The next mouse scroll shows the scroll to bottom button right
    // away, since there is no visible button to keep steady.
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert_shown();
    assert_scroll_to_bottom_mode();
});

run_test("fetch completing during a mouse scroll away from the bottom", ({override}) => {
    setup(override);
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();

    // Nothing but the end of the scroll gets to decide what to show,
    // so a fetch completing halfway through leaves the arrow alone.
    set_feed(override, {bottom_visible: false});
    override(message_scroll_state, "actively_scrolling", true);
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");

    override(message_scroll_state, "actively_scrolling", false);
    scroll_to_bottom_button.update();
    assert_shown();
    assert_scroll_to_bottom_mode();
    assert.equal(running_timers.size, 1);
});

run_test("autoscroll that ends at the bottom", ({override}) => {
    setup(override);
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();

    // A new message arriving at the bottom of the feed briefly hides
    // the last message until the feed autoscrolls to show it; the
    // button should not flicker through its scroll to bottom mode.
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");

    // That scroll is over, so a later keyboard scroll away from the
    // bottom hides the button as usual.
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("tooltip is destroyed once the button has faded out", ({override}) => {
    setup(override);
    const transitionend = $container().get_on_handler("transitionend");

    // No tooltip has been created yet.
    transitionend({originalEvent: new TransitionEvent("visibility")});

    let tooltip_destroyed = false;
    $clickable_area()[0]._tippy = {
        destroy() {
            tooltip_destroyed = true;
        },
    };

    transitionend({originalEvent: new TransitionEvent("opacity")});
    assert.ok(!tooltip_destroyed);

    $container().addClass("show");
    transitionend({originalEvent: new TransitionEvent("visibility")});
    assert.ok(!tooltip_destroyed);

    $container().removeClass("show");
    transitionend({originalEvent: new TransitionEvent("visibility")});
    assert.ok(tooltip_destroyed);
});

run_test("narrow change during a mouse scroll away from the bottom", ({override}) => {
    setup(override);
    set_feed(override);
    scroll_to_bottom_button.update();
    assert_shown();
    assert_next_unread_mode("next_unread_topic", "next-unread-topic-button-tooltip-template");

    // A mouse scroll starts, so the button waits for it to finish...
    set_feed(override, {bottom_visible: false});
    override(message_scroll_state, "actively_scrolling", true);
    scroll_to_bottom_button.show_scroll_to_bottom_button();

    // ...but the user moves to another conversation before it does,
    // landing above the bottom of that view.
    override(message_scroll_state, "actively_scrolling", false);
    set_feed(override, {bottom_visible: false, id: 2});
    scroll_to_bottom_button.update();
    assert_hidden();
});

run_test("a scroll finishing again does not leak a hide timer", ({override}) => {
    setup(override);
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    scroll_to_bottom_button.update();
    assert_shown();
    assert.equal(running_timers.size, 1);

    // The wait starts over, rather than leaving the previous timer
    // running: a leaked one would hide the button as soon as the
    // mouse left it, however recently the last scroll finished.
    scroll_to_bottom_button.update();
    assert.equal(running_timers.size, 1);
});
