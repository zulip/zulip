"use strict";

/*
    This whole module is dedicated to adding
    one line of coverage for markdown.js.

    There may be a better way.
*/

const rewiremock = require("rewiremock/node");

const blueslip = require("../../static/js/blueslip");
const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

set_global("page_params", {});
rewiremock("katex").with({
    renderToString: () => {
        throw new Error("some-exception");
    },
});

rewiremock.enable();

const markdown_config = zrequire("markdown_config");

const markdown = zrequire("markdown");

markdown.initialize([], markdown_config.get_helpers());

run_test("katex_throws_unexpected_exceptions", () => {
    blueslip.expect("error", "Error: some-exception");
    const message = {raw_content: "$$a$$"};
    markdown.apply_markdown(message);
});

rewiremock.disable();
