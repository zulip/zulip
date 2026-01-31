"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const preview_urls = zrequire("preview_urls");

run_test("is_url_previewable", () => {
    const previewable_urls = [
        "https://github.com/zulip/zulip/issues/1",
        "https://github.com/zulip/zulip/issues/12345",
        "https://github.com/zulip/zulip/pull/42",
        "https://www.github.com/zulip/zulip/issues/99",
        "https://www.github.com/zulip/zulip/pull/1000",
        "http://github.com/zulip/zulip/issues/321",
        "http://www.github.com/zulip/zulip/pull/555",
        "https://github.com/zulip/zulip/issues/98765",
        "https://github.com/zulip/zulip/pull/7654",
        "https://www.github.com/zulip/zulip/issues/777",
    ];

    const non_previewable_urls = [
        "https://dummy.com/zulip/zulip/issues/1", // wrong domain
        "https://github.io/zulip/zulip/issues/2", // wrong domain
        "ftp://github.com/zulip/zulip/issues/3", // wrong protocol
        "https://github.com:8080/zulip/zulip/issues/4", // has port
        "https://github.com/zulip/zulip/wiki/Setup", // wrong path
        "https://www.github.com/zulip/zulip/discussions/5", // wrong path
        "https://github.com/zulip/zulip/commit/abcdef", // not issue/pull
        "https://www.github.com/zulip", // too short path
        "http://example.com/zulip/zulip/issues/6", // wrong domain
        "invalid_url", // invalid format
    ];

    for (const url of previewable_urls) {
        assert.equal(preview_urls.is_url_previewable(url), true);
    }

    for (const url of non_previewable_urls) {
        assert.equal(preview_urls.is_url_previewable(url), false);
    }
});
