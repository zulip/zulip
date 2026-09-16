"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

set_global("document", "document-stub");
class TransitionEvent {
    constructor(propertyName) {
        this.propertyName = propertyName;
    }
}
set_global("TransitionEvent", TransitionEvent);

const message_lists = mock_esm("../src/message_lists", {current: undefined});
const message_viewport = mock_esm("../src/message_viewport");

const scroll_to_bottom_button = zrequire("scroll_to_bottom_button");

const $container = () => $("#scroll-to-bottom-button-container");
const $clickable_area = () => $("#scroll-to-bottom-button-clickable-area");

function set_feed(override, {bottom_visible = true, empty = false} = {}) {
    override(message_viewport, "bottom_rendered_message_visible", () => bottom_visible, {
        unused: false,
    });
    override(message_lists, "current", {visibly_empty: () => empty});
}

function is_shown() {
    return $container().hasClass("show");
}

function mouse_scroll() {
    scroll_to_bottom_button.show_scroll_to_bottom_button();
    scroll_to_bottom_button.hide_scroll_to_bottom();
}

function keydown(modifiers = {}) {
    $(document).get_on_handler("keydown")({
        shiftKey: false,
        ctrlKey: false,
        metaKey: false,
        ...modifiers,
    });
}

function test(label, f) {
    run_test(label, (helpers) => {
        clock.reset();
        $container().set_matches(":hover", false);
        scroll_to_bottom_button.initialize();
        f(helpers);
    });
}

test("hidden outside message views", ({override}) => {
    override(message_lists, "current", undefined);
    $container().addClass("show");

    scroll_to_bottom_button.hide_scroll_to_bottom();
    assert.ok(!is_shown());
});

test("hidden at the bottom of the feed", ({override}) => {
    set_feed(override);

    mouse_scroll();
    assert.ok(!is_shown());

    $container().addClass("show");
    scroll_to_bottom_button.hide_scroll_to_bottom();
    assert.ok(!is_shown());
});

test("hidden in an empty feed", ({override}) => {
    set_feed(override, {bottom_visible: false, empty: true});
    $container().addClass("show");

    scroll_to_bottom_button.hide_scroll_to_bottom();
    assert.ok(!is_shown());
});

test("shown by a mouse scroll above the bottom", ({override}) => {
    set_feed(override, {bottom_visible: false});

    scroll_to_bottom_button.show_scroll_to_bottom_button();
    assert.ok(is_shown());

    scroll_to_bottom_button.hide_scroll_to_bottom();
    assert.ok(is_shown());
});

test("not shown by a keyboard scroll", ({override}) => {
    set_feed(override, {bottom_visible: false});

    scroll_to_bottom_button.hide_scroll_to_bottom();
    assert.ok(!is_shown());
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
    scroll_to_bottom_button.hide_scroll_to_bottom();

    clock.tick(4500);
    mouse_scroll();
    clock.tick(2999);
    assert.ok(is_shown());

    clock.tick(1);
    assert.ok(!is_shown());
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
