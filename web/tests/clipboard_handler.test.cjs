"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test} = require("./lib/test.cjs");

const clipboard_handler = zrequire("clipboard_handler");
const stream_data = zrequire("stream_data");

run_test("get_stream_topic_details", () => {
    const stream = {
        name: "Stream",
        description: "Color and  Lights",
        stream_id: 1,
        subscribed: true,
        type: "stream",
    };
    stream_data.add_sub(stream);
    assert.deepEqual(
        clipboard_handler.get_stream_topic_details(
            "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic",
        ),
        {stream_name: "Stream", topic_name: "normal topic", message_id: undefined},
    );
    assert.deepEqual(
        clipboard_handler.get_stream_topic_details(
            "http://zulip.zulipdev.com/#narrow/channel/2-Stream/topic/normal.20topic",
        ),
        null,
    );
});

run_test("url_to_html_format", () => {
    const stream_topic_details_1 = {
        stream_name: "stream1",
        topic_name: "topic1",
        message_id: "1",
    };
    const stream_topic_details_2 = {
        stream_name: "stream2",
        topic_name: "topic2",
        message_id: undefined,
    };
    const stream_topic_details_3 = {
        stream_name: "stream3",
        topic_name: undefined,
        message_id: undefined,
    };
    const stream_topic_details_4 = {
        stream_name: undefined,
        topic_name: undefined,
        message_id: undefined,
    };
    const normal_stream_with_topic_and_message =
        "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/111";
    const normal_stream_with_topic =
        "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic";
    const normal_stream = "http://zulip.zulipdev.com/#narrow/channel/1-Stream";
    const invalid_stream = "http://zulip.zulipdev.com/#narrow/stream/99-Stream";

    assert.equal(
        clipboard_handler.url_to_html_format(
            ...Object.values(stream_topic_details_1),
            normal_stream_with_topic_and_message,
        ),
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/111">#stream1 > topic1 @1</a>`,
    );
    assert.equal(
        clipboard_handler.url_to_html_format(
            stream_topic_details_2.stream_name,
            stream_topic_details_2.topic_name,
            stream_topic_details_2.message_id,
            normal_stream_with_topic,
        ),
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic">#stream2 > topic2</a>`,
    );
    assert.equal(
        clipboard_handler.url_to_html_format(
            stream_topic_details_3.stream_name,
            stream_topic_details_3.topic_name,
            stream_topic_details_3.message_id,
            normal_stream,
        ),
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream">#stream3</a>`,
    );
    assert.equal(
        clipboard_handler.url_to_html_format(
            stream_topic_details_4.stream_name,
            stream_topic_details_4.topic_name,
            stream_topic_details_4.message_id,
            invalid_stream,
        ),
        `<a href="http://zulip.zulipdev.com/#narrow/stream/99-Stream">http://zulip.zulipdev.com/#narrow/stream/99-Stream</a>`,
    );
});

// Mock ClipboardItem
global.ClipboardItem = class {
    constructor(data) {
        this.data = data;
    }
};

// Mock global.navigator.clipboard
global.navigator = {
    clipboard: {},
};

run_test("copy_to_clipboard", async ({override}) => {
    const stream = {
        name: "Stream",
        description: "Color and  Lights",
        stream_id: 1,
        subscribed: true,
        type: "stream",
    };

    stream_data.add_sub(stream);

    const cb = make_stub();
    const invalid_stream = "http://zulip.zulipdev.com/#narrow/stream/99-Stream";
    const normal_stream_with_topic =
        "http://zulip.zulipdev.com/#narrow/stream/1-Stream/topic/Topic";

    // Replacing navigator.clipboard.write with custom function
    override(global.navigator.clipboard, "write", () => Promise.resolve());

    // Ensuring that function returns early when link is invalid
    await clipboard_handler.copy_to_clipboard(invalid_stream, cb.f);
    assert.deepEqual(cb.num_calls, 0);

    // Ensuring function is being called and cb is triggered when link is correct
    await clipboard_handler.copy_to_clipboard(normal_stream_with_topic, cb.f);
    assert.deepEqual(cb.num_calls, 1);
});
