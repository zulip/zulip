"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

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
        [false, "1-精选 - 译文"], // 1-.E7.B2.BE.E9.80.89.20-.20.E8.AF.91.E6.96.87
        [false, "1-精选 - 原创"], // 1-.E7.B2.BE.E9.80.89.20-.20.E5.8E.9F.E5.88.9B
        [false, "1-ビデオゲーム"], // 1-.E3.83.93.E3.83.87.E3.82.AA.E3.82.B2.E3.83.BC.E3.83.A0
        [false, "1-goûta à l'œuf brûlé"], // 1-go.C3.BBta.20.C3.A0.20l'.C5.93uf.20br.C3.BBl.C3.A9
        [true, "1-(2+3)%5"], // 1-.282.2B3.29.255
        [true, "1-$um @nd m%d"], // 1-.24um.20.40nd.20m.25d
        [true, "1-books.2C-film.2C-tv.2C-and-games"], // 1-books.2E2C-film.2E2C-tv.2E2C-and-games
        [true, "1-test-stream-autocomplete"], // 1-test-stream-autocomplete
        [true, "1-ñoño"], // 1-.C3.B1o.C3.B1o
        [true, "1-యశ"], // 1-.E0.B0.AF.E0.B0.B6
        [true, "1-l'été"], // 1-l'.C3.A9t.C3.A9
        [true, "1-书籍"], // 1-.E4.B9.A6.E7.B1.8D
    ];

    for (const [include_slug, channel_slug] of test_cases) {
        if (include_slug) {
            assert.equal(
                internal_url.encode_slug(1, channel_slug),
                internal_url.encodeHashComponent(channel_slug),
            );
        } else {
            assert.ok(Number(internal_url.encode_slug(1, channel_slug)) === 1);
        }
    }
});
