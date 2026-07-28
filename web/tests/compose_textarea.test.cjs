"use strict";

const {strict: assert} = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_textarea = zrequire("compose_textarea");

run_test("get_code_block_ranges", () => {
    function inside(content, substr) {
        return compose_textarea.position_inside_code_block(content, content.indexOf(substr));
    }
    // Whether the char just after the first blank-line delimiter is in code.
    function delimiter_inside(content) {
        return compose_textarea.position_inside_code_block(content, content.indexOf("\n\n\n") + 1);
    }

    assert.ok(!inside("hello\n\n\nworld", "world"));

    // Fenced block at the start of the message; the delimiter after it is outside.
    const start_block = "```\ncode\n```\n\n\npara";
    assert.ok(inside(start_block, "code"));
    assert.ok(!delimiter_inside(start_block));

    // Tilde (~~~) fence; blank lines inside it are code.
    const tilde = "pre\n~~~\naaa\n\n\nbbb\n~~~";
    assert.ok(delimiter_inside(tilde));
    assert.ok(!inside(tilde, "pre"));

    // Two adjacent blocks; the delimiter between them is outside.
    const adjacent = "```\nc1\n```\n\n\n```\nc2\n```";
    assert.ok(!delimiter_inside(adjacent));
    assert.ok(inside(adjacent, "c1"));
    assert.ok(inside(adjacent, "c2"));

    // Indented (4-space) code block; blank lines inside it are code.
    assert.ok(delimiter_inside("    a\n\n\n    b"));

    // Indented text that continues a paragraph is not code.
    assert.ok(!inside("text\n    still text", "still"));

    // An indented block ends at the next non-indented line.
    assert.ok(inside("    code\ntext", "code"));
    assert.ok(!inside("    code\ntext", "text"));

    // A fence opening right after an indented block closes the indented block.
    const indent_then_fence = "    code\n```\nx\n```";
    assert.ok(inside(indent_then_fence, "code"));
    assert.ok(inside(indent_then_fence, "x"));

    // An unclosed fence runs to the end of the content.
    assert.ok(inside("```\nunclosed code", "unclosed"));

    // A longer fence is not closed by a shorter one.
    assert.ok(inside("````\n```\ninner\n````", "inner"));

    // Content with no code has no ranges.
    assert.deepEqual(compose_textarea.get_code_block_ranges("just text\nno code"), []);
});
