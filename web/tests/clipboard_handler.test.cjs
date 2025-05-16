"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const settings_config = zrequire("settings_config");
mock_esm("../src/user_settings", {
    user_settings: {
        web_channel_default_view: settings_config.web_channel_default_view_values.channel_feed.code,
    },
});
const clipboard_handler = zrequire("clipboard_handler");
const stream_data = zrequire("stream_data");
const people = zrequire("people");

const hamlet = {
    user_id: 15,
    email: "hamlet@example.com",
    full_name: "Hamlet",
};

people.add_active_user(hamlet);

run_test("copy_link_to_clipboard", async ({override}) => {
    const stream = {
        name: "Stream",
        description: "Color and Lights",
        stream_id: 1,
        subscribed: true,
        type: "stream",
    };
    stream_data.add_sub(stream);
    const {window} = new JSDOM();
    global.document = window.document;

    // Mock DataTransfer for testing purposes
    class MockDataTransfer {
        constructor() {
            this.data = {};
        }

        setData(type, value) {
            this.data[type] = value;
        }

        getData(type) {
            return this.data[type] || "";
        }
    }

    // Store the copy event callback and clipboardData
    let clipboardData;
    let copyEventCallback;
    override(window.document, "addEventListener", (event, callback) => {
        if (event === "copy") {
            copyEventCallback = callback;
        }
    });

    // Stub execCommand to trigger the copy event
    override(window.document, "execCommand", (command) => {
        if (command === "copy" && copyEventCallback) {
            const copyEvent = new window.Event("copy", {bubbles: true, cancelable: true});
            copyEvent.clipboardData = new MockDataTransfer();
            copyEventCallback(copyEvent);
            clipboardData = copyEvent.clipboardData;
        }
        return true;
    });

    // Helper function to simulate clipboard handling
    async function simulateClipboardData(link) {
        await clipboard_handler.copy_link_to_clipboard(link);
        return {
            plainText: clipboardData.getData("text/plain"),
            htmlText: clipboardData.getData("text/html"),
            markdownText: clipboardData.getData("text/x-gfm"),
        };
    }

    const normal_stream_with_topic =
        "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic";
    const normal_stream_with_topic_and_message =
        "http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/1";
    const normal_stream = "http://zulip.zulipdev.com/#narrow/channel/1-Stream/";
    const dm_message = "http://zulip.zulipdev.com/#narrow/dm/15-dm/near/43";

    let clipboardDataResult = await simulateClipboardData(normal_stream_with_topic);
    assert.equal(clipboardDataResult.plainText, normal_stream_with_topic);
    assert.equal(
        clipboardDataResult.htmlText,
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic">#Stream > normal topic</a>`,
    );
    assert.equal(
        clipboardDataResult.markdownText,
        `[#Stream > normal topic](http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic)`,
    );

    clipboardDataResult = await simulateClipboardData(normal_stream_with_topic_and_message);
    assert.equal(clipboardDataResult.plainText, normal_stream_with_topic_and_message);
    assert.equal(
        clipboardDataResult.htmlText,
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/1">#Stream > normal topic @ 💬</a>`,
    );
    assert.equal(
        clipboardDataResult.markdownText,
        `[#Stream > normal topic @ 💬](http://zulip.zulipdev.com/#narrow/channel/1-Stream/topic/normal.20topic/near/1)`,
    );

    clipboardDataResult = await simulateClipboardData(normal_stream);
    assert.equal(clipboardDataResult.plainText, normal_stream);
    assert.equal(
        clipboardDataResult.htmlText,
        `<a href="http://zulip.zulipdev.com/#narrow/channel/1-Stream/">#Stream</a>`,
    );
    assert.equal(
        clipboardDataResult.markdownText,
        `[#Stream](http://zulip.zulipdev.com/#narrow/channel/1-Stream/)`,
    );

    clipboardDataResult = await simulateClipboardData(dm_message);
    assert.equal(clipboardDataResult.plainText, dm_message);
});
