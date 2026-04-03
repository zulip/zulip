"use strict";

const assert = require("node:assert/strict");

const {make_reaction} = require("./lib/example_reaction.cjs");
const {run_test} = require("./lib/test.cjs");

run_test("make_reaction: basic fields", () => {
    const reaction = make_reaction({
        emoji_name: "wave",
        user_id: 3,
    });

    assert.equal(reaction.emoji_name, "wave");
    assert.equal(reaction.user_id, 3);
    assert.equal(reaction.reaction_type, "unicode_emoji");
    assert.ok(reaction.emoji_code);
});
