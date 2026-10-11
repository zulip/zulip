"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const bulleted_numbered_list_util = zrequire("bulleted_numbered_list_util");

run_test("get_prefix", () => {
    // Plain text
    assert.equal(bulleted_numbered_list_util.get_prefix("plain text"), "");
    assert.equal(bulleted_numbered_list_util.get_prefix(""), "");

    // Bullets: -, *, +
    assert.equal(bulleted_numbered_list_util.get_prefix("- item"), "- ");
    assert.equal(bulleted_numbered_list_util.get_prefix("* item"), "* ");
    assert.equal(bulleted_numbered_list_util.get_prefix("+ item"), "+ ");

    // Numbered
    assert.equal(bulleted_numbered_list_util.get_prefix("1. item"), "1. ");
    assert.equal(bulleted_numbered_list_util.get_prefix("42. item"), "42. ");

    // Space-indented
    assert.equal(bulleted_numbered_list_util.get_prefix("  - item"), "  - ");
    assert.equal(bulleted_numbered_list_util.get_prefix("   1. item"), "   1. ");
    assert.equal(bulleted_numbered_list_util.get_prefix(" ".repeat(4) + "plain"), " ".repeat(4));

    // Tab-indented
    assert.equal(bulleted_numbered_list_util.get_prefix("\t- item"), "\t- ");
    assert.equal(bulleted_numbered_list_util.get_prefix("\t1. item"), "\t1. ");
    assert.equal(bulleted_numbered_list_util.get_prefix("\tplain"), "\t");

    // Heading
    assert.equal(bulleted_numbered_list_util.get_prefix("# Heading"), "# ");
    assert.equal(bulleted_numbered_list_util.get_prefix("### H3"), "### ");

    // Blockquote
    assert.equal(bulleted_numbered_list_util.get_prefix("> quote"), "> ");
    assert.equal(bulleted_numbered_list_util.get_prefix(">> nested quote"), ">> ");
    assert.equal(bulleted_numbered_list_util.get_prefix("> - list inside quote"), "> - ");
    assert.equal(bulleted_numbered_list_util.get_prefix("> # heading inside quote"), "> # ");
});

run_test("bulleted_numbered_list_util helpers", () => {
    assert.equal(bulleted_numbered_list_util.get_last_line("a\nb\nc"), "c");
    assert.equal(bulleted_numbered_list_util.get_indent(" ".repeat(3) + "abc"), " ".repeat(3));
    assert.equal(bulleted_numbered_list_util.get_indent("\tabc"), "\t");
    assert.ok(bulleted_numbered_list_util.is_bulleted("- abc"));
    assert.ok(bulleted_numbered_list_util.is_bulleted("* abc"));
    assert.ok(bulleted_numbered_list_util.is_bulleted("+ abc"));
    assert.ok(!bulleted_numbered_list_util.is_bulleted("abc"));
    assert.ok(bulleted_numbered_list_util.is_numbered("1. abc"));
    assert.ok(!bulleted_numbered_list_util.is_numbered("abc"));
    assert.equal(bulleted_numbered_list_util.strip_bullet("- abc"), "abc");
    assert.equal(bulleted_numbered_list_util.strip_numbering("1. abc"), "abc");
    assert.ok(bulleted_numbered_list_util.is_list_item("  - abc"));
    assert.ok(bulleted_numbered_list_util.is_list_item("  1. abc"));
    assert.ok(!bulleted_numbered_list_util.is_list_item("  abc"));
});
