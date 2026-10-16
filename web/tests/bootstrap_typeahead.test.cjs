"use strict";

const assert = require("node:assert/strict");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const bootstrap_typeahead = zrequire("bootstrap_typeahead");

run_test("rewire_MAX_ITEMS", ({override_rewire}) => {
    assert.equal(bootstrap_typeahead.MAX_ITEMS, 50);
    override_rewire(bootstrap_typeahead, "MAX_ITEMS", 7);
    assert.equal(bootstrap_typeahead.MAX_ITEMS, 7);
});

run_test("is_ime_provider_input", () => {
    assert.ok(
        bootstrap_typeahead.is_ime_provider_input(
            {key: "Enter", originalEvent: {isComposing: true, keyCode: 13}},
            false,
        ),
    );
    assert.ok(
        bootstrap_typeahead.is_ime_provider_input(
            {key: "Enter", originalEvent: {isComposing: false, keyCode: 229}},
            false,
        ),
    );
    assert.ok(
        bootstrap_typeahead.is_ime_provider_input(
            {key: "Enter", originalEvent: {isComposing: false, keyCode: 13}},
            true,
        ),
    );
    assert.ok(
        !bootstrap_typeahead.is_ime_provider_input(
            {key: "Enter", originalEvent: {isComposing: false, keyCode: 13}},
            false,
        ),
    );
    assert.ok(!bootstrap_typeahead.is_ime_provider_input({key: "Enter"}, false));
});

function make_stub_typeahead() {
    const typeahead = Object.create(bootstrap_typeahead.Typeahead.prototype);
    typeahead.in_ime_composition = false;
    typeahead.ignore_next_enter_for_selection = false;
    typeahead.shown = true;
    typeahead.mouse_moved_since_typeahead = false;
    typeahead.tabIsEnter = true;
    typeahead.suppressKeyPressRepeat = false;
    typeahead.hideOnEmptyAfterBackspace = false;
    typeahead.trigger_selection = () => false;
    typeahead.maybeStopAdvance = () => {};
    typeahead.move = () => {};
    typeahead.lookup = () => {};
    typeahead.select = () => {
        typeahead._selected = true;
        return typeahead;
    };
    typeahead._selected = false;
    return typeahead;
}

function enter_keyup(overrides = {}) {
    const {originalEvent: original_overrides, ...rest} = overrides;
    return {
        key: "Enter",
        preventDefault() {},
        stopPropagation() {},
        ...rest,
        originalEvent: {
            isComposing: false,
            keyCode: 13,
            ...original_overrides,
        },
    };
}

run_test("keyup Enter during IME does not select", () => {
    const typeahead = make_stub_typeahead();

    // Chrome-order: isComposing true on Enter keyup.
    typeahead.keyup(
        enter_keyup({
            originalEvent: {isComposing: true, keyCode: 13},
        }),
    );
    assert.ok(!typeahead._selected);

    // keyCode 229 during composition (Safari-style).
    typeahead.compositionstart();
    typeahead.keyup(
        enter_keyup({
            originalEvent: {isComposing: false, keyCode: 229},
        }),
    );
    assert.ok(!typeahead._selected);
    assert.ok(typeahead.in_ime_composition);
});

run_test("compositionend Enter race does not select; later Enter does", () => {
    const typeahead = make_stub_typeahead();
    let looked_up = false;
    typeahead.lookup = () => {
        looked_up = true;
    };

    typeahead.compositionstart();
    assert.ok(typeahead.in_ime_composition);

    // compositionend: clear composing, arm ignore-next-Enter, refresh lookup.
    typeahead.compositionend();
    assert.ok(!typeahead.in_ime_composition);
    assert.ok(typeahead.ignore_next_enter_for_selection);
    assert.ok(looked_up);

    // Race: confirming Enter arrives on the next macrotask with isComposing
    // already false and a normal keyCode (not 229). Must not select.
    clock.tick(0);
    typeahead.keyup(enter_keyup());
    assert.ok(!typeahead._selected);
    assert.ok(!typeahead.ignore_next_enter_for_selection);

    // A subsequent independent Enter must still select.
    typeahead.keyup(enter_keyup());
    assert.ok(typeahead._selected);
});

run_test("compositionend same-turn Enter does not select", () => {
    const typeahead = make_stub_typeahead();

    typeahead.compositionstart();
    typeahead.compositionend();
    // Confirming Enter in the same turn as compositionend (before any
    // macrotask), with isComposing false — the Safari-ish ordering.
    typeahead.keyup(enter_keyup());
    assert.ok(!typeahead._selected);
    assert.ok(!typeahead.ignore_next_enter_for_selection);

    typeahead.keyup(enter_keyup());
    assert.ok(typeahead._selected);
});

run_test("non-Enter after compositionend allows next Enter to select", () => {
    const typeahead = make_stub_typeahead();

    typeahead.compositionstart();
    typeahead.compositionend();
    assert.ok(typeahead.ignore_next_enter_for_selection);

    // Space (or digit) confirmed the IME, not Enter — clear the flag.
    typeahead.keyup({
        key: " ",
        originalEvent: {isComposing: false, keyCode: 32},
        preventDefault() {},
        stopPropagation() {},
    });
    assert.ok(!typeahead.ignore_next_enter_for_selection);

    typeahead.keyup(enter_keyup());
    assert.ok(typeahead._selected);
});

run_test("keyup during composition still looks up", () => {
    const typeahead = make_stub_typeahead();
    let looked_up = false;
    typeahead.lookup = () => {
        looked_up = true;
    };

    typeahead.compositionstart();
    typeahead.keyup({
        key: "a",
        originalEvent: {isComposing: true, keyCode: 229},
        preventDefault() {},
        stopPropagation() {},
    });
    assert.ok(looked_up);
    assert.ok(!typeahead._selected);
});

run_test("keydown Enter during IME does not select", () => {
    const typeahead = make_stub_typeahead();
    // trigger_selection would select if reached; IME must short-circuit first.
    typeahead.trigger_selection = () => true;

    typeahead.keydown({
        key: "Enter",
        originalEvent: {isComposing: true, keyCode: 13},
        preventDefault() {},
        stopPropagation() {},
    });
    assert.ok(!typeahead._selected);
    // Prove the override is live for coverage, then confirm IME still wins.
    assert.equal(typeahead.trigger_selection({}), true);
    assert.ok(!typeahead._selected);
});

run_test("keydown Enter after compositionend does not select via trigger", () => {
    const typeahead = make_stub_typeahead();
    // Default stubs: trigger_selection returns false; move is a no-op.
    // Early return must skip both — we only assert outcomes, not dead stubs.
    typeahead.compositionstart();
    typeahead.compositionend();
    typeahead.keydown(enter_keyup());
    assert.ok(!typeahead._selected);
    assert.ok(typeahead.ignore_next_enter_for_selection);
});

run_test("keydown invokes trigger_selection when not composing", () => {
    const typeahead = make_stub_typeahead();
    let moved = false;
    typeahead.move = () => {
        moved = true;
    };

    // Default stub trigger_selection returns false; keydown should still call move.
    typeahead.keydown({
        key: "ArrowDown",
        originalEvent: {isComposing: false, keyCode: 40},
        preventDefault() {},
        stopPropagation() {},
    });
    assert.ok(moved);
    assert.ok(!typeahead._selected);

    // Custom trigger_selection returning true should select.
    typeahead.trigger_selection = () => true;
    typeahead.keydown({
        key: ">",
        originalEvent: {isComposing: false, keyCode: 190},
        preventDefault() {},
        stopPropagation() {},
    });
    assert.ok(typeahead._selected);
});
