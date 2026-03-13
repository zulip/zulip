/* eslint-disable unicorn/prefer-module, @typescript-eslint/no-require-imports, @typescript-eslint/consistent-type-assertions */

import type assert_module from "node:assert/strict";

import type * as spoilers_module from "../src/spoilers.ts";

import type * as test_lib_types from "./lib/test.cjs";
import type {JQueryMock, ZJQueryHelpers} from "./lib/zjquery_helpers.cts";

const assert: typeof assert_module = require("node:assert/strict") as typeof assert_module;

const {noop, run_test}: typeof test_lib_types = require("./lib/test.cjs") as typeof test_lib_types;

const {create_mock} = require("./lib/zjquery_helpers.cts") as ZJQueryHelpers;

const spoilers = require("../src/spoilers.ts") as typeof spoilers_module;

const get_spoiler_elem = (title: string): JQueryMock => {
    const $block = create_mock(`block-${title}`);
    const $header = create_mock(`header-${title}`);
    const $content = create_mock(`content-${title}`);
    $content[0]!.remove = noop;
    $header.text(title);
    $block.set_find_results(".spoiler-header", [$header[0]!]);
    $block.set_find_results(".spoiler-content", [$content[0]!]);
    return $block;
};

run_test("hide spoilers in notifications", (): void => {
    const $root = create_mock("root element");
    const $spoiler_1 = get_spoiler_elem("this is the title");
    const $spoiler_2 = get_spoiler_elem("");
    $root.set_find_results(".spoiler-block", [$spoiler_1[0]!, $spoiler_2[0]!]);

    const $root_jquery = $root as unknown as JQuery;
    spoilers.hide_spoilers_in_notification($root_jquery);

    assert.equal($spoiler_1.find(".spoiler-header").text(), "this is the title (…)");
    assert.equal($spoiler_2.find(".spoiler-header").text(), "(…)");
});
