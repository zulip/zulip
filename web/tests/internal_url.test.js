"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const internal_url = zrequire("../shared/src/internal_url");

run_test("test encodeHashComponent", () => {
    const decoded = "https://www.zulipexample.com";
    const encoded = "https.3A.2F.2Fwww.2Ezulipexample.2Ecom";
    const result = internal_url.encodeHashComponent(decoded);
    assert.equal(result, encoded);
});

run_test("test decodeHashComponent", () => {
    const decoded = "https://www.zulipexample.com";
    const encoded = "https.3A.2F.2Fwww.2Ezulipexample.2Ecom";
    const result = internal_url.decodeHashComponent(encoded);
    assert.equal(result, decoded);
});

run_test("test stream_id_to_slug", () => {
    const maybe_get_stream_name = () => "onetwo three";
    const result = internal_url.stream_id_to_slug(123, maybe_get_stream_name);
    assert.equal(result, "123-onetwo-three");
});

run_test("test stream_id_to_slug failed lookup", () => {
    const maybe_get_stream_name = () => undefined;
    const result = internal_url.stream_id_to_slug(123, maybe_get_stream_name);
    assert.equal(result, "123-unknown");
});

run_test("test encode_stream_id", () => {
    const maybe_get_stream_name = () => "stream (with brackets)";
    const result = internal_url.encode_stream_id(123, maybe_get_stream_name);
    assert.equal(result, "123-stream-.28with-brackets.29");
});

run_test("test by_stream_url", () => {
    const maybe_get_stream_name = () => "a test stream";
    const result = internal_url.by_stream_url(123, maybe_get_stream_name);
    assert.equal(result, "#narrow/stream/123-a-test-stream");
});

run_test("test by_stream_topic_url", () => {
    const maybe_get_stream_name = () => "a test stream";
    const result = internal_url.by_stream_topic_url(123, "test topic", maybe_get_stream_name);
    assert.equal(result, "#narrow/stream/123-a-test-stream/topic/test.20topic");
});

run_test("test_by_conversation_and_time_url", () => {
    const maybe_get_stream_name = () => "a test stream";

    let message = {
        type: "stream",
        stream_id: 99,
        topic: "testing",
        id: 42,
    };

    assert.equal(
        internal_url.by_conversation_and_time_url(
            "http://zulip.zulipdev.com/",
            message,
            [15],
            maybe_get_stream_name,
            177,
        ),
        "http://zulip.zulipdev.com/#narrow/stream/99-a-test-stream/topic/testing/near/42",
    );

    message = {
        type: "private",
        stream_id: 15,
        topic: "testing",
        id: 43,
    };

    assert.equal(
        internal_url.by_conversation_and_time_url(
            "http://zulip.zulipdev.com/",
            message,
            [15],
            maybe_get_stream_name,
            173,
        ),
        "http://zulip.zulipdev.com/#narrow/pm-with/15-pm/near/43",
    );

    message = {
        type: "private",
        stream_id: 15,
        topic: "testing",
        id: 43,
    };

    assert.equal(
        internal_url.by_conversation_and_time_url(
            "http://zulip.zulipdev.com/",
            message,
            [15],
            maybe_get_stream_name,
            177,
        ),
        "http://zulip.zulipdev.com/#narrow/dm/15-dm/near/43",
    );
});
