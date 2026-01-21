"use strict";

const assert = require("node:assert/strict");

const autosize = require("../src/autosize.ts");

const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

run_test("watch sets data-replicated-value and reacts to input", () => {
    const $textarea = $("<textarea>");
    $textarea.wrap = (html) => {
        const $parent = $(html);
        $textarea.set_parent($parent);
    };

    autosize.watch($textarea);

    $textarea.val("hello");
    $textarea.trigger("input");

    assert.equal($textarea.parent().attr("data-replicated-value"), "hello");
});

run_test("manual_resize triggers input event", () => {
    let input_triggered = false;

    const $textarea = $("<textarea>");
    $textarea.on("input", () => {
        input_triggered = true;
    });

    autosize.manual_resize($textarea);

    assert.ok(input_triggered);
});

run_test("watch ignores empty jquery object", () => {
    // This forces the 'if (!textarea) return' check to run.
    const $empty = {
        0: undefined,
        length: 0,
    };

    // Should return immediately without calling .wrap() or .parent()
    autosize.watch($empty);
});

run_test("watch uses existing parent if valid", () => {
    const $container = $("<div>");
    $container.addClass("autosize-container");

    const $textarea = $("<textarea>");
    $textarea.set_parent($container);

    autosize.watch($textarea);

    $textarea.val("existing parent");
    $textarea.trigger("input");

    assert.equal($container.attr("data-replicated-value"), "existing parent");
});
