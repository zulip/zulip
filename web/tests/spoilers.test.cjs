"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const spoilers = zrequire("spoilers");

const get_spoiler_elem = (title) => {
    const $block = $.create(`block-${title}`);
    const $header = $.create(`header-${title}`);
    const $content = $.create(`content-${title}`);
    $content[0].remove = noop;
    $header.text(title);
    $block.set_find_results(".spoiler-header", $header);
    $block.set_find_results(".spoiler-content", $content);
    return $block;
};

run_test("hide spoilers in notifications", () => {
    const $root = $.create("root element");
    const $spoiler_1 = get_spoiler_elem("this is the title");
    const $spoiler_2 = get_spoiler_elem("");
    $root.set_find_results(".spoiler-block", [$spoiler_1[0], $spoiler_2[0]]);
    spoilers.hide_spoilers_in_notification($root);
    assert.equal($spoiler_1.find(".spoiler-header").text(), "this is the title (…)");
    assert.equal($spoiler_2.find(".spoiler-header").text(), "(…)");
});
