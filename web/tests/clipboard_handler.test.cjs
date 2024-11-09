"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test} = require("./lib/test.cjs");

const clipboard_handler = zrequire("clipboard_handler");
const stream_data = zrequire("stream_data");

const stream = {
    name: "Stream",
    description: "Color and  Lights",
    stream_id: 1,
    subscribed: true,
    type: "stream",
};

const markdown_stream = {
    name: "<Stream*$`&>",
    description: "Colors and lights",
    stream_id: 2,
    subscribe: true,
    type: "stream",
};

stream_data.add_sub(stream);
stream_data.add_sub(markdown_stream);

const normal_stream_with_topic =
    "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic";
const markdown_stream_with_normal_topic =
    "http://zulip.zulipdev.com/#narrow/channel/2-.3CStream*.24.60.26.3E/topic/normal.20topic";
const normal_stream_with_markdown_topic =
    "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/.3C.24topic.60*.26.3E";
const markdown_stream_with_markdown_topic =
    "http://zulip.zulipdev.com/#narrow/channel/2-.3CStream*.24.60.26.3E/topic/.3C.24topic.60*.26.3E";
const invalid_stream = "http://zulip.zulipdev.com/#narrow/stream/99-Stream";
const normal_stream_no_topic = "http://zulip.zulipdev.com/#narrow/channel/1-Stream";
const markdown_stream_no_topic =
    "http://zulip.zulipdev.com/#narrow/channel/2-.3CStream*.24.60.26.3E";
const link_to_message =
    "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/86";
run_test("generate_formatted_url", () => {
    assert.equal(
        clipboard_handler.generate_formatted_link(normal_stream_with_topic),
        `<a href="${normal_stream_with_topic}">#Stream>normal topic</a>`,
    );

    assert.equal(
        clipboard_handler.generate_formatted_link(markdown_stream_with_normal_topic),
        `<a href="${markdown_stream_with_normal_topic}">#&lt;Stream*$\`&&gt;>normal topic</a>`,
    );

    assert.equal(
        clipboard_handler.generate_formatted_link(normal_stream_with_markdown_topic),
        `<a href="${normal_stream_with_markdown_topic}">#Stream>&lt;$topic\`*&&gt;</a>`,
    );

    assert.equal(
        clipboard_handler.generate_formatted_link(markdown_stream_with_markdown_topic),
        `<a href="${markdown_stream_with_markdown_topic}">#&lt;Stream*$\`&&gt;>&lt;$topic\`*&&gt;</a>`,
    );

    assert.equal(clipboard_handler.generate_formatted_link(invalid_stream), "Invalid stream");

    assert.equal(
        clipboard_handler.generate_formatted_link(normal_stream_no_topic),
        `<a href="${normal_stream_no_topic}">#Stream</a>`,
    );

    assert.equal(
        clipboard_handler.generate_formatted_link(markdown_stream_no_topic),
        `<a href="${markdown_stream_no_topic}">#&lt;Stream*$\`&&gt;</a>`,
    );
    assert.equal(
        clipboard_handler.generate_formatted_link(link_to_message),
        `<a href="${link_to_message}">#Stream>normal topic@86</a>`,
    );
});

global.ClipboardItem = class {
    constructor(items) {
        this.items = items;
    }
};

global.navigator = {
    clipboard: {},
};

run_test("copy_to_clipboard", async ({override}) => {
    const after_copy_cb = make_stub();

    // replacing navigator.clipboard.write with custom function
    override(global.navigator.clipboard, "write", () => Promise.resolve());

    // ensuring that function returns early when link in invalid
    await clipboard_handler.copy_to_clipboard(invalid_stream, after_copy_cb.f);
    assert.deepEqual(after_copy_cb.num_calls, 0);

    // ensuring function is beign called and after_copy_cb is triggered when link is correct
    await clipboard_handler.copy_to_clipboard(normal_stream_with_topic, after_copy_cb.f);
    assert.deepEqual(global.navigator.clipboard.write(), Promise.resolve());
    assert.deepEqual(after_copy_cb.num_calls, 1);
});
