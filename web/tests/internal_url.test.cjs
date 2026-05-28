"use strict";

const assert = require("node:assert/strict");

const url_encoding_test_cases = require("../../zerver/tests/fixtures/url_encoding_test_cases.json");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const internal_url = zrequire("internal_url");

run_test("test encodeHashComponent", () => {
    for (const test of url_encoding_test_cases) {
        assert.equal(internal_url.encodeHashComponent(test.input), test.expected_output);
    }
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
    assert.equal(result, "#narrow/channel/123-a-test-stream");
});

run_test("test by_channel_topic_list_url", () => {
    const maybe_get_stream_name = () => "a test stream";
    const result = internal_url.by_channel_topic_list_url(123, maybe_get_stream_name);
    assert.equal(result, "#topics/channel/123-a-test-stream");
});

run_test("test by_stream_topic_url", () => {
    const maybe_get_stream_name = () => "a test stream";
    // Test stream_topic_url is a traditional topic link when the
    // message_id to be encoded is undefined.
    let result = internal_url.by_stream_topic_url(123, "test topic", maybe_get_stream_name);
    assert.equal(result, "#narrow/channel/123-a-test-stream/topic/test.20topic");

    // Test stream_topic_url is a topic permaling when the
    // message_id to be encoded is not undefined.
    result = internal_url.by_stream_topic_url(123, "test topic", maybe_get_stream_name, 12);
    assert.equal(result, "#narrow/channel/123-a-test-stream/topic/test.20topic/with/12");
});

run_test("test encode_slug", () => {
    // The test cases include stream id to mirror how
    // internal_url.encode_stream_id works.
    const test_cases = [
        // diff=0, ratio=1.0 → included (pure ASCII)
        ["1-test-stream-autocomplete", true],
        // 1-books.2C-film.2C-tv.2C-and-games;
        // diff=6, ratio=1.214 → included (ASCII with commas)
        ["1-books,-film,-tv,-and-games", true],
        // 1-.E7.B2.BE.E9.80.89.20-.20.E8.AF.91.E6.96.87;
        // diff=36, ratio=5.0 → excluded (Chinese with spaces)
        ["1-精选 - 译文", false],
        // 1-go.C3.BBta.20.C3.A0.20l.27.C5.93uf.20br.C3.BBl.C3.A9;
        // diff=33, ratio=2.571 → excluded (many accented Latin chars)
        ["1-goûta à l'œuf brûlé", false],
        // 1-.E0.B0.AF.E0.B0.B6;
        // diff=16, ratio=5.0 → excluded (very short non-Latin slug)
        ["1-యశ", false],
        // 1-.282.2B3.29.255;
        // diff=8, ratio=1.889 → excluded (ASCII special chars, short slug)
        ["1-(2+3)%5", false],
        // 1-abcdefghijklmnop-.C3.A9.C3.A9;
        // diff=10, ratio=1.476 → included (at diff limit)
        ["1-abcdefghijklmnop-éé", true],
        // 1-abcdefghijklmno-.C3.A9.C3.A9;
        // diff=10, ratio=1.5 exactly → included (at ratio limit)
        ["1-abcdefghijklmno-éé", true],
        // 1-abcdefghijklmnopqrstu-.C3.A9.C3.A9.2E;
        // diff=12, ratio=1.444 → excluded (over diff limit)
        ["1-abcdefghijklmnopqrstu-éé.", false],
        // 1-abcd-.C3.A9;
        // diff=5, ratio=1.625 → excluded (over ratio limit)
        ["1-abcd-é", false],
    ];

    for (const [channel_slug, should_encode_slug] of test_cases) {
        if (should_encode_slug) {
            assert.equal(
                internal_url.encode_slug(1, channel_slug),
                internal_url.encodeHashComponent(channel_slug),
            );
        } else {
            assert.ok(Number(internal_url.encode_slug(1, channel_slug)) === 1);
        }
    }
});
