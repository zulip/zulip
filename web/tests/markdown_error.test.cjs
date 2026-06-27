"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {default: katex} = mock_esm("katex", {default: {}});

const markdown_config = zrequire("markdown_config");
const markdown = zrequire("markdown");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

markdown.initialize(markdown_config.get_helpers());

run_test("katex_throws_unexpected_exceptions", ({override}) => {
    const message = {raw_content: "$$a$$"};
    override(katex, "renderToString", () => {
        throw new Error("some-exception");
    });
    assert.throws(() => markdown.render(message.raw_content), {
        name: "Error",
        message: "some-exception\nPlease report this to https://zulip.com/development-community/",
    });
});
