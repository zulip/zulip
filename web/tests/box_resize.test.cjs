"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {window} = new JSDOM("");
// Only assign globals our library actually reads (document and
// getComputedStyle). `global.HTMLElement` is intentionally NOT
// overwritten: index.cjs already points it at its own JSDOM's
// HTMLElement, and later tests such as `compose_paste.test.cjs`
// rely on `instanceof HTMLElement` matching elements parsed via
// their DOMParser. Routing the assignments through `set_global`
// ensures the globals are restored after this test, since later
// tests in the same process can be sensitive to seeing a real
// `document.createElement` (e.g., it makes simplebar's `canUseDOM`
// check true, causing it to call `window.addEventListener` at
// module load time, which the test environment doesn't provide).
set_global("document", window.document);
set_global("getComputedStyle", window.getComputedStyle.bind(window));

// `setPointerCapture` / `releasePointerCapture` are not implemented by
// jsdom; stub them on this test's own HTMLElement prototype so our
// pointer event handlers can call them without throwing. We avoid
// stubbing on `global.HTMLElement` since that prototype is shared
// with other tests.
window.HTMLElement.prototype.setPointerCapture = function () {};
window.HTMLElement.prototype.releasePointerCapture = function () {};

const box_resize = zrequire("box_resize");

function make_box() {
    const box = document.createElement("div");
    // Provide a predictable starting rect so tests don't depend on
    // jsdom's layout (which is a no-op).
    let current_rect = {width: 100, height: 80};
    box.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: current_rect.width,
        bottom: current_rect.height,
        width: current_rect.width,
        height: current_rect.height,
    });
    box.set_rect = (width, height) => {
        current_rect = {width, height};
    };
    return box;
}

function fire(handle, type, {clientX = 0, clientY = 0, pointerId = 1} = {}) {
    const event = new window.Event(type, {bubbles: true, cancelable: true});
    Object.assign(event, {clientX, clientY, pointerId});
    handle.dispatchEvent(event);
    return event;
}

run_test("make_resizable creates one handle per direction with expected class", () => {
    const box = make_box();
    box_resize.make_resizable(box, ["top", "right", "bottom_left"]);

    assert.equal(box.children.length, 3);
    const classes = [...box.children].map((h) => h.className);
    assert.ok(classes[0].includes("resizable-box-handle-top"));
    assert.ok(classes[1].includes("resizable-box-handle-right"));
    assert.ok(classes[2].includes("resizable-box-handle-bottom-left"));
    // Underscores in the direction are converted to hyphens for the class.
    assert.ok(!classes[2].includes("bottom_left"));
});

run_test("cleanup removes the handles it added", () => {
    const box = make_box();
    const existing_child = document.createElement("span");
    box.append(existing_child);

    const cleanup = box_resize.make_resizable(box, ["right", "bottom"]);
    assert.equal(box.children.length, 3);

    cleanup();
    assert.equal(box.children.length, 1);
    assert.equal(box.children[0], existing_child);
});

run_test("right handle grows width by 2 * dx and does not touch height", () => {
    const box = make_box();
    box.set_rect(100, 80);
    box_resize.make_resizable(box, ["right"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 40});
    fire(handle, "pointermove", {clientX: 60, clientY: 45});

    // Dragging right by 10: box grows by 20 (10 on each side, centered).
    assert.equal(box.style.width, "120px");
    // `height` is left untouched by an edge-only handle.
    assert.equal(box.style.height, "");
});

run_test("left handle grows width when pointer moves leftward", () => {
    const box = make_box();
    box.set_rect(100, 80);
    box_resize.make_resizable(box, ["left"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 40});
    // Dragging the left edge 15px to the left: the box grows symmetrically
    // by 30px total.
    fire(handle, "pointermove", {clientX: 35, clientY: 40});

    assert.equal(box.style.width, "130px");
});

run_test("top handle grows height when pointer moves upward", () => {
    const box = make_box();
    box.set_rect(100, 80);
    box_resize.make_resizable(box, ["top"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 40});
    fire(handle, "pointermove", {clientX: 50, clientY: 30});

    // Dragging the top edge up by 10 => height grows by 20.
    assert.equal(box.style.height, "100px");
    assert.equal(box.style.width, "");
});

run_test("corner handle grows both dimensions with correct signs", () => {
    const box = make_box();
    box.set_rect(200, 100);
    box_resize.make_resizable(box, ["top_left"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 50});
    // Move 5 left, 8 up: both dx_sign and dy_sign are -1 for top_left,
    // so width grows by 2*5 = 10 and height grows by 2*8 = 16.
    fire(handle, "pointermove", {clientX: 45, clientY: 42});

    assert.equal(box.style.width, "210px");
    assert.equal(box.style.height, "116px");
});

run_test("on_resize callback fires once per pointermove after pointerdown", () => {
    const box = make_box();
    box.set_rect(100, 80);
    let call_count = 0;
    box_resize.make_resizable(box, ["bottom_right"], () => {
        call_count += 1;
    });
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 0, clientY: 0});
    assert.equal(call_count, 0);
    fire(handle, "pointermove", {clientX: 5, clientY: 5});
    fire(handle, "pointermove", {clientX: 10, clientY: 10});
    assert.equal(call_count, 2);

    fire(handle, "pointerup", {clientX: 10, clientY: 10});
    fire(handle, "pointermove", {clientX: 20, clientY: 20});
    assert.equal(call_count, 2);
});

run_test("pointerup stops subsequent pointermove events from resizing", () => {
    const box = make_box();
    box.set_rect(100, 80);
    box_resize.make_resizable(box, ["right"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 40});
    fire(handle, "pointermove", {clientX: 60, clientY: 40});
    assert.equal(box.style.width, "120px");

    fire(handle, "pointerup", {clientX: 60, clientY: 40});
    fire(handle, "pointermove", {clientX: 200, clientY: 40});
    // Width should not have changed after pointerup.
    assert.equal(box.style.width, "120px");
});

run_test("pointercancel stops subsequent pointermove events from resizing", () => {
    const box = make_box();
    box.set_rect(100, 80);
    box_resize.make_resizable(box, ["right"]);
    const handle = box.children[0];

    fire(handle, "pointerdown", {clientX: 50, clientY: 40});
    fire(handle, "pointermove", {clientX: 60, clientY: 40});
    assert.equal(box.style.width, "120px");

    // The browser can take the gesture away at any time; we must
    // tear the listeners down or subsequent moves would keep resizing.
    fire(handle, "pointercancel", {clientX: 60, clientY: 40});
    fire(handle, "pointermove", {clientX: 200, clientY: 40});
    assert.equal(box.style.width, "120px");
});

run_test("resize clamps to CSS min and max bounds during a single drag", () => {
    const box = make_box();
    box.set_rect(100, 80);
    // Jsdom does not resolve the element's real computed style from a
    // stylesheet, so we stub getComputedStyle to return the min/max
    // bounds we want to test against. The library only calls it on
    // `box`, so we don't need a passthrough.
    const original_get_computed_style = global.getComputedStyle;
    global.getComputedStyle = () => ({
        minWidth: "60px",
        maxWidth: "140px",
        minHeight: "0px",
        maxHeight: "none",
    });

    try {
        box_resize.make_resizable(box, ["right"]);
        const handle = box.children[0];

        fire(handle, "pointerdown", {clientX: 50, clientY: 40});

        // Overshoot the max: raw would be 100 + 2*100 = 300, clamp to 140.
        fire(handle, "pointermove", {clientX: 150, clientY: 40});
        assert.equal(box.style.width, "140px");

        // Pull back within bounds: raw is 100 + 2*10 = 120, no clamp.
        fire(handle, "pointermove", {clientX: 60, clientY: 40});
        assert.equal(box.style.width, "120px");

        // Undershoot the min: raw would be 100 - 2*40 = 20, clamp to 60.
        fire(handle, "pointermove", {clientX: 10, clientY: 40});
        assert.equal(box.style.width, "60px");
    } finally {
        global.getComputedStyle = original_get_computed_style;
    }
});
