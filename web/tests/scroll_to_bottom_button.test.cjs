"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

set_global("document", "document-stub");
class TransitionEvent {
    constructor(propertyName) {
        this.propertyName = propertyName;
    }
}
set_global("TransitionEvent", TransitionEvent);

const message_lists = mock_esm("../src/message_lists", {current: undefined});
const message_scroll_state = mock_esm("../src/message_scroll_state", {
    actively_scrolling: false,
});
const message_viewport = mock_esm("../src/message_viewport", {
    is_animating_scroll: () => false,
});
const narrow_state = mock_esm("../src/narrow_state", {
    stream_id: () => 101,
    topic: () => "current topic",
    pm_ids_string: () => "31,32",
});
const stream_list = mock_esm("../src/stream_list", {
    get_sorted_channel_ids_for_next_unread_navigation: () => [
        {channel_id: 101, is_collapsed: false},
    ],
});
const tippyjs = mock_esm("../src/tippyjs");
const topic_generator = mock_esm("../src/topic_generator");
const ui_util = mock_esm("../src/ui_util");

const scroll_to_bottom_button = zrequire("scroll_to_bottom_button");

const $container = () => $("#scroll-to-bottom-button-container");
const $icon = () => $("#scroll-to-bottom-button .zulip-icon");
const $clickable_area = () => $("#scroll-to-bottom-button-clickable-area");

const appearance = {
    scroll_to_bottom: {
        icon: "chevron-down",
        tooltip_template_id: "scroll-to-bottom-button-tooltip-template",
    },
    next_unread_topic: {
        icon: "arrow-right",
        tooltip_template_id: "next-unread-topic-button-tooltip-template",
    },
    next_unread_dm_conversation: {
        icon: "arrow-right",
        tooltip_template_id: "next-unread-dm-conversation-button-tooltip-template",
    },
};

function set_feed(
    override,
    {
        bottom_visible = true,
        fetched_end_rendered = true,
        newest = "found",
        empty = false,
        view = "other",
        other_unread_conversation = true,
        id = 1,
    } = {},
) {
    override(message_viewport, "bottom_rendered_message_visible", () => bottom_visible, {
        unused: false,
    });
    override(
        topic_generator,
        "has_next_unread_topic",
        (stream_id, topic, channels_info) => {
            assert.equal(stream_id, narrow_state.stream_id());
            assert.equal(topic, narrow_state.topic());
            assert.deepEqual(
                channels_info,
                stream_list.get_sorted_channel_ids_for_next_unread_navigation(),
            );
            return other_unread_conversation;
        },
        {unused: false},
    );
    override(
        topic_generator,
        "get_next_unread_pm_string",
        (user_ids_string) => {
            assert.equal(user_ids_string, narrow_state.pm_ids_string());
            return other_unread_conversation ? "33" : undefined;
        },
        {unused: false},
    );
    override(message_lists, "current", {
        id,
        visibly_empty: () => empty,
        view: {is_fetched_end_rendered: () => fetched_end_rendered},
        data: {
            fetch_status: {
                has_found_newest: () => newest === "found",
                can_load_newer_messages: () => newest === "not_fetched",
            },
            filter: {
                can_show_next_unread_topic_conversation_button: () => view === "topic",
                can_show_next_unread_dm_conversation_button: () => view === "dm",
            },
        },
    });
}

function is_shown() {
    return $container().hasClass("show");
}

function assert_shows(mode) {
    assert.ok(is_shown());
    for (const icon of ["chevron-down", "arrow-right"]) {
        assert.equal($icon().hasClass(`zulip-icon-${icon}`), icon === appearance[mode].icon);
    }
    assert.equal(
        $clickable_area().attr("data-tooltip-template-id"),
        appearance[mode].tooltip_template_id,
    );
}

function mouse_scroll() {
    scroll_to_bottom_button.handle_non_keyboard_scroll();
    scroll_to_bottom_button.update();
}

function show_arrow(override) {
    set_feed(override, {view: "topic"});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");
}

function keydown(modifiers = {}) {
    $(document).get_on_handler("keydown")({
        shiftKey: false,
        ctrlKey: false,
        metaKey: false,
        ...modifiers,
    });
}

let clicks;

function click() {
    const event_calls = [];
    $("body").get_on_handler(
        "click",
        "#scroll-to-bottom-button-clickable-area",
    )({
        preventDefault() {
            event_calls.push("preventDefault");
        },
        stopPropagation() {
            event_calls.push("stopPropagation");
        },
    });
    assert.deepEqual(event_calls, ["preventDefault", "stopPropagation"]);
}

function test(label, f) {
    run_test(label, (helpers) => {
        clock.reset();
        $container().set_matches(":hover", false);
        $icon().addClass("zulip-icon-chevron-down");
        $clickable_area().attr(
            "data-tooltip-template-id",
            appearance.scroll_to_bottom.tooltip_template_id,
        );
        clicks = [];
        scroll_to_bottom_button.initialize(
            Object.fromEntries(
                Object.keys(appearance).map((mode) => [
                    mode,
                    () => {
                        clicks.push(mode);
                    },
                ]),
            ),
        );

        // The module keeps its state between tests. A mouse scroll
        // above the bottom followed by a keypress resets it, apart
        // from a pending animated scroll, which tests must finish.
        set_feed(helpers.override, {bottom_visible: false});
        mouse_scroll();
        keydown();
        assert.ok(!is_shown());

        f(helpers);
    });
}

test("hidden outside message views", ({override}) => {
    override(message_lists, "current", undefined);
    $container().addClass("show");

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("hidden outside message views even during a scroll", ({override}) => {
    override(message_lists, "current", undefined);
    override(message_scroll_state, "actively_scrolling", true);
    $container().addClass("show");

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("not updated until the scroll has finished", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    set_feed(override);
    override(message_scroll_state, "actively_scrolling", true);
    scroll_to_bottom_button.update();
    assert.ok(is_shown());

    override(message_scroll_state, "actively_scrolling", false);
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("not updated until an animated scroll is over", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    set_feed(override);
    const callbacks = [];
    override(message_viewport, "is_animating_scroll", () => true);
    override(message_viewport, "after_animated_scroll", (callback) => {
        callbacks.push(callback);
    });
    scroll_to_bottom_button.update();
    scroll_to_bottom_button.update();
    assert.ok(is_shown());
    assert.equal(callbacks.length, 1);

    override(message_viewport, "is_animating_scroll", () => false);
    callbacks[0]();
    assert.ok(!is_shown());

    // The next animated scroll is waited for again.
    override(message_viewport, "is_animating_scroll", () => true);
    scroll_to_bottom_button.update();
    assert.equal(callbacks.length, 2);

    override(message_viewport, "is_animating_scroll", () => false);
    callbacks[1]();
});

test("hidden at the bottom of the feed", ({override}) => {
    set_feed(override);

    mouse_scroll();
    assert.ok(!is_shown());

    $container().addClass("show");
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("hidden in an empty feed", ({override}) => {
    set_feed(override, {bottom_visible: false, empty: true});

    scroll_to_bottom_button.handle_non_keyboard_scroll();
    assert.ok(!is_shown());

    $container().addClass("show");
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("shown when newer messages are fetched but not rendered", ({override}) => {
    set_feed(override, {fetched_end_rendered: false});

    mouse_scroll();
    assert.ok(is_shown());
});

test("shown when newer messages are yet to be fetched", ({override}) => {
    set_feed(override, {newest: "not_fetched"});

    mouse_scroll();
    assert.ok(is_shown());
});

test("not shown while the newest messages are being fetched", ({override}) => {
    set_feed(override, {newest: "loading"});

    mouse_scroll();
    assert.ok(!is_shown());
});

test("shown by a mouse scroll above the bottom", ({override}) => {
    set_feed(override, {bottom_visible: false});

    scroll_to_bottom_button.handle_non_keyboard_scroll();
    assert.ok(is_shown());

    scroll_to_bottom_button.update();
    assert.ok(is_shown());
});

test("not shown by a keyboard scroll", ({override}) => {
    set_feed(override, {bottom_visible: false});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("hiding stops the wait", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    keydown();
    assert.equal(clock.countTimers(), 0);
});

test("hidden three seconds after the scroll", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    clock.tick(2999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
});

test("stays while the mouse is over it", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    $container().set_matches(":hover", true);
    clock.tick(6000);
    assert.ok(is_shown());

    $container().set_matches(":hover", false);
    clock.tick(3000);
    assert.ok(!is_shown());
});

test("the three seconds start when the scroll finishes", ({override}) => {
    set_feed(override, {bottom_visible: false});
    scroll_to_bottom_button.handle_non_keyboard_scroll();

    clock.tick(5000);
    assert.ok(is_shown());

    scroll_to_bottom_button.update();
    clock.tick(2999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
});

test("an update does not restart the three seconds", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    clock.tick(2000);
    scroll_to_bottom_button.update();
    assert.equal(clock.countTimers(), 1);
    clock.tick(999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
    assert.equal(clock.countTimers(), 0);
});

test("another mouse scroll restarts the three seconds", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    clock.tick(2000);
    mouse_scroll();
    clock.tick(2999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
});

test("a keyboard scroll does not make a later hide come early", ({override}) => {
    set_feed(override, {bottom_visible: false});
    mouse_scroll();

    clock.tick(1000);
    keydown();
    scroll_to_bottom_button.update();

    clock.tick(4500);
    mouse_scroll();
    clock.tick(2999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
});

test("a click scrolls to the bottom", ({override}) => {
    override(narrow_state, "is_message_feed_visible", () => true);
    override(ui_util, "blur_active_element", noop);

    click();
    assert.deepEqual(clicks, ["scroll_to_bottom"]);
});

test("a click on the arrow goes to the next unread conversation", ({override}) => {
    override(narrow_state, "is_message_feed_visible", () => true);
    override(ui_util, "blur_active_element", noop);

    show_arrow(override);
    click();
    assert.deepEqual(clicks, ["next_unread_topic"]);

    set_feed(override, {view: "dm"});
    scroll_to_bottom_button.update();
    click();
    assert.deepEqual(clicks, ["next_unread_topic", "next_unread_dm_conversation"]);
});

test("a click takes focus off the button before acting", ({override}) => {
    override(narrow_state, "is_message_feed_visible", () => true);
    override(ui_util, "blur_active_element", () => {
        clicks.push("blur");
    });

    click();
    assert.deepEqual(clicks, ["blur", "scroll_to_bottom"]);
});

test("a click does nothing once the message feed is hidden", ({override}) => {
    override(narrow_state, "is_message_feed_visible", () => false);

    click();
    assert.deepEqual(clicks, []);
});

test("hidden by a keypress without modifiers", () => {
    for (const modifier of ["shiftKey", "ctrlKey", "metaKey"]) {
        $container().addClass("show");
        keydown({[modifier]: true});
        assert.ok(is_shown());
    }

    keydown();
    assert.ok(!is_shown());
});

test("tooltip is destroyed once the button has faded out", () => {
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

test("next unread topic at the bottom of a topic or channel view", ({override}) => {
    set_feed(override, {view: "topic"});

    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");
});

test("next unread DM conversation at the bottom of a DM view", ({override}) => {
    set_feed(override, {view: "dm"});

    scroll_to_bottom_button.update();
    assert_shows("next_unread_dm_conversation");
});

test("no arrow without another unread topic", ({override}) => {
    set_feed(override, {view: "topic", other_unread_conversation: false});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("no arrow without another unread DM conversation", ({override}) => {
    set_feed(override, {view: "dm", other_unread_conversation: false});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow comes and goes with other unread conversations", ({override}) => {
    show_arrow(override);

    set_feed(override, {view: "topic", other_unread_conversation: false});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());

    show_arrow(override);
});

test("no arrow in an empty view", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", empty: true});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("scroll to bottom becomes the arrow at the bottom", ({override}) => {
    set_feed(override, {view: "topic", bottom_visible: false});
    mouse_scroll();
    assert_shows("scroll_to_bottom");

    $container().set_matches(":hover", true);
    set_feed(override, {view: "topic"});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    $container().set_matches(":hover", false);
    clock.tick(3000);
    assert_shows("next_unread_topic");
    assert.equal(clock.countTimers(), 0);
});

test("scroll to bottom hides at the bottom if nothing else is unread", ({override}) => {
    set_feed(override, {view: "topic", bottom_visible: false});
    mouse_scroll();
    assert_shows("scroll_to_bottom");

    set_feed(override, {view: "topic", other_unread_conversation: false});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("an open tooltip follows the mode", ({override}) => {
    set_feed(override, {view: "topic"});
    let tooltip_content;
    $clickable_area()[0]._tippy = {
        setContent(content) {
            tooltip_content = content;
        },
    };
    override(tippyjs, "get_tooltip_content", (reference) =>
        reference.getAttribute("data-tooltip-template-id"),
    );

    scroll_to_bottom_button.update();
    assert.equal(tooltip_content, appearance.next_unread_topic.tooltip_template_id);

    // Its content is only set again when the mode changes.
    tooltip_content = undefined;
    scroll_to_bottom_button.update();
    assert.equal(tooltip_content, undefined);
});

test("arrow stays through keypresses", ({override}) => {
    show_arrow(override);

    keydown();
    assert_shows("next_unread_topic");
});

test("arrow stays through a scroll that ends at the bottom", ({override}) => {
    show_arrow(override);

    // A newly arrived message is below the screen until the feed
    // has scrolled to it.
    set_feed(override, {view: "topic", bottom_visible: false});
    override(message_scroll_state, "actively_scrolling", true);
    mouse_scroll();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic"});
    override(message_scroll_state, "actively_scrolling", false);
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    // The finished scroll is forgotten.
    set_feed(override, {view: "topic", bottom_visible: false});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow stays while the feed has yet to scroll to a new message", ({override}) => {
    show_arrow(override);

    set_feed(override, {view: "topic", bottom_visible: false});
    let update_after_animated_scroll;
    override(message_viewport, "is_animating_scroll", () => true);
    override(message_viewport, "after_animated_scroll", (callback) => {
        update_after_animated_scroll = callback;
    });
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic"});
    override(message_viewport, "is_animating_scroll", () => false);
    update_after_animated_scroll();
    assert_shows("next_unread_topic");
});

test("arrow becomes scroll to bottom after a mouse scroll away", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", bottom_visible: false});

    override(message_scroll_state, "actively_scrolling", true);
    mouse_scroll();
    assert_shows("next_unread_topic");

    override(message_scroll_state, "actively_scrolling", false);
    scroll_to_bottom_button.update();
    assert_shows("scroll_to_bottom");

    clock.tick(3000);
    assert.ok(!is_shown());
});

test("arrow hides after a keyboard scroll away", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", bottom_visible: false});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
    // The icon is not swapped while the button fades out.
    assert.ok($icon().hasClass("zulip-icon-arrow-right"));

    scroll_to_bottom_button.handle_non_keyboard_scroll();
    assert_shows("scroll_to_bottom");
});

test("a mouse scroll in the previous view does not count", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", bottom_visible: false});
    override(message_scroll_state, "actively_scrolling", true);
    mouse_scroll();

    override(message_scroll_state, "actively_scrolling", false);
    set_feed(override, {view: "topic", bottom_visible: false, id: 2});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("a mouse scroll only counts for the update that follows it", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", bottom_visible: false});
    override(message_scroll_state, "actively_scrolling", true);
    mouse_scroll();

    override(message_scroll_state, "actively_scrolling", false);
    set_feed(override, {view: "topic", newest: "loading"});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic", bottom_visible: false});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow under the mouse becomes scroll to bottom", ({override}) => {
    show_arrow(override);
    $container().set_matches(":hover", true);
    set_feed(override, {view: "topic", bottom_visible: false, id: 2});

    scroll_to_bottom_button.update();
    assert_shows("scroll_to_bottom");

    $container().set_matches(":hover", false);
    clock.tick(3000);
    assert.ok(!is_shown());
});

test("arrow stays while a conversation that ends on the screen loads", ({override}) => {
    show_arrow(override);

    // Opening the view scrolls the feed.
    set_feed(override, {view: "topic", newest: "loading", id: 2});
    mouse_scroll();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic", id: 2});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");
});

test("arrow stays while an empty view loads", ({override}) => {
    show_arrow(override);

    set_feed(override, {view: "topic", newest: "loading", empty: true, id: 2});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic", newest: "not_fetched", empty: true, id: 2});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");
});

test("arrow hides once a conversation turns out to continue below the screen", ({override}) => {
    show_arrow(override);

    set_feed(override, {view: "topic", newest: "loading", id: 2});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    set_feed(override, {view: "topic", bottom_visible: false, id: 2});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow hides in a loading view that already continues below the screen", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", newest: "loading", bottom_visible: false, id: 2});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow takes the mode of the view that is loading", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "dm", newest: "loading", id: 2});

    scroll_to_bottom_button.update();
    assert_shows("next_unread_dm_conversation");
});

test("arrow hides while a view that offers none loads", ({override}) => {
    show_arrow(override);
    set_feed(override, {newest: "loading", id: 2});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("hidden button stays hidden until the view has loaded", ({override}) => {
    set_feed(override, {view: "topic", newest: "loading"});

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());

    show_arrow(override);
});

test("scroll to bottom hides in a view that is loading", ({override}) => {
    set_feed(override, {view: "topic", bottom_visible: false});
    mouse_scroll();
    assert_shows("scroll_to_bottom");

    set_feed(override, {view: "topic", newest: "loading", empty: true, id: 2});
    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});

test("arrow hides after a fetch that failed for good", ({override}) => {
    show_arrow(override);
    set_feed(override, {view: "topic", newest: "loading", empty: true, id: 2});
    scroll_to_bottom_button.update();
    assert_shows("next_unread_topic");

    scroll_to_bottom_button.hide_after_failed_fetch();
    assert.ok(!is_shown());

    scroll_to_bottom_button.update();
    assert.ok(!is_shown());
});
