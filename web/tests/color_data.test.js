"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const color_data = zrequire("color_data");

run_test("pick_color", () => {
    color_data.reset();

    color_data.claim_colors([
        {color: color_data.colors[1]},
        {foo: "whatever"},
        {color: color_data.colors[3]},
        {color: "bogus"},
    ]);

    const expected_colors = [
        color_data.colors[0],
        color_data.colors[2],
        ...color_data.colors.slice(4),
        // ok, now we'll cycle through all colors
        ...color_data.colors,
        ...color_data.colors,
        ...color_data.colors,
    ];

    for (const expected_color of expected_colors) {
        assert.equal(color_data.pick_color(), expected_color);
    }

    color_data.claim_color(color_data.colors[0]);
    assert.equal(color_data.pick_color(), color_data.colors[1]);
});
