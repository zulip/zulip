/*
    This whole module is dedicated to adding
    one line of coverage for markdown.js.

    There may be a better way.
*/

const markdown_config = zrequire("markdown_config");

set_global("marked", zrequire("marked", "third/marked/lib/marked"));
set_global("page_params", {});

zrequire("emoji");
zrequire("fenced_code");
zrequire("hash_util");
zrequire("message_store");
zrequire("people");
zrequire("stream_data");
zrequire("user_groups");

set_global("katex", {
    renderToString: () => {
        throw new Error("some-exception");
    },
});

const markdown = zrequire("markdown");

markdown.initialize([], markdown_config.get_helpers());

run_test("katex_throws_unexpected_exceptions", () => {
    blueslip.expect("error", "Error: some-exception");
    const message = {raw_content: "$$a$$"};
    markdown.apply_markdown(message);
});
