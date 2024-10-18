"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const try_stream_topic_syntax_text = mock_esm("../src/copy_and_paste").try_stream_topic_syntax_text;
const clipboard_handler = zrequire("clipboard_handler");

run_test("clipboard_handler", ({override}) => {
    // Mocking jQuery element
    const $link_element = $.create("link-element");

    // Mock data to simulate clipboard-text
    const stream_topic_link_element_data = "https://example.com/stream/1234-topic";
    $link_element.data("clipboard-text", stream_topic_link_element_data);

    // Mock try_stream_topic_syntax_text
    override(try_stream_topic_syntax_text, "try_stream_topic_syntax_text", () => "#**stream_name > topic_name**");

    // Spy to ensure hide_popover is called
    let hide_popover_called = false;
    const hide_popover = (instance) => {
        hide_popover_called = true;
        assert.equal(instance, "popover_instance");
    };

    // Mock navigator.clipboard.write
    global.navigator = {
        clipboard: {
            write(items) {
                // Assert that clipboard data is correct
                assert.equal(items.length, 1);
                assert.equal(items[0]["text/plain"].type, "text/plain");
                assert.equal(items[0]["text/html"].type, "text/html");
                return Promise.resolve();
            },
        },
    };

    // Call clipboard_handler with the mocks
    clipboard_handler($link_element, hide_popover, "popover_instance");

    // Check if hide_popover was called
    assert.equal(hide_popover_called, true);
});
