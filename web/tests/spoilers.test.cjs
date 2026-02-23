"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const spoilers = zrequire("spoilers");

// This function is taken from rendered_markdown.test.ts and slightly modified.
function make_jquery_each_collection(elems) {
    return {
        each(func) {
            for (const [index, $elem] of elems.entries()) {
                func.call($elem, index, $elem);
            }
        },
    };
}

function make_spoiler_block(title) {
    const $block = $.create(`block-${title}`);
    const $header = $.create(`header-${title}`);
    const $content = $.create(`content-${title}`);

    $content.remove = noop;
    $header.text(title);

    $block.set_find_results(".spoiler-header", $header);
    $block.set_find_results(".spoiler-content", $content);

    return $block;
}

run_test("hide spoilers in notifications", () => {
    const $root = $.create("root element");
    const $spoiler_1 = make_spoiler_block("this is the title");
    const $spoiler_2 = make_spoiler_block("");
    $root.set_find_results(".spoiler-block", make_jquery_each_collection([$spoiler_1, $spoiler_2]));
    spoilers.hide_spoilers_in_notification($root);
    assert.equal($spoiler_1.find(".spoiler-header").text(), "this is the title (…)");
    assert.equal($spoiler_2.find(".spoiler-header").text(), "(…)");
});
