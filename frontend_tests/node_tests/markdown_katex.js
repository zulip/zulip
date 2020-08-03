"use strict";

/*
    This whole module is dedicated to adding
    one line of coverage for markdown.js.

    There may be a better way.
*/

const rewiremock = require("rewiremock/node");

const markdown_config = zrequire("markdown_config");

set_global("page_params", {});

zrequire("hash_util");
zrequire("message_store");
zrequire("people");
zrequire("stream_data");
zrequire("user_groups");

const markdown = rewiremock.proxy(() => zrequire("markdown"), {
    katex: {
        renderToString: () => {
            throw new Error("some-exception");
        },
    },
});

markdown.initialize([], markdown_config.get_helpers());

run_test("katex_throws_unexpected_exceptions", () => {
    blueslip.expect("error", "Error: some-exception");
    const message = {raw_content: "$$a$$"};
    markdown.apply_markdown(message);
});
