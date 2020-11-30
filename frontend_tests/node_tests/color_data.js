"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

zrequire("color_data");

run_test("pick_color", () => {
    color_data.colors = ["blue", "orange", "red", "yellow"];

    color_data.reset();

    color_data.claim_colors([
        {color: "orange"},
        {foo: "whatever"},
        {color: "yellow"},
        {color: "bogus"},
    ]);

    const expected_colors = [
        "blue",
        "red",
        // ok, now we'll cycle through all colors
        "blue",
        "orange",
        "red",
        "yellow",
        "blue",
        "orange",
        "red",
        "yellow",
        "blue",
        "orange",
        "red",
        "yellow",
    ];

    for (const expected_color of expected_colors) {
        assert.equal(color_data.pick_color(), expected_color);
    }

    color_data.claim_color("blue");
    assert.equal(color_data.pick_color(), "orange");
});
