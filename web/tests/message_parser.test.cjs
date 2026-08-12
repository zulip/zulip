"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_parser = zrequire("message_parser");

const preview_selector = ".message_embed, .youtube-video, .embed-video, .vimeo-video";

run_test("message_has_link_preview", () => {
    const embed_content = '<div class="message_embed">preview</div>';
    $(`<div>${embed_content}</div>`).set_find_results(preview_selector, $.create("embed"));
    assert.equal(message_parser.message_has_link_preview(embed_content), true);

    const youtube_content = '<div class="youtube-video message_inline_image">preview</div>';
    $(`<div>${youtube_content}</div>`).set_find_results(preview_selector, $.create("youtube"));
    assert.equal(message_parser.message_has_link_preview(youtube_content), true);

    const embed_video_content = '<div class="embed-video message_inline_image">preview</div>';
    $(`<div>${embed_video_content}</div>`).set_find_results(
        preview_selector,
        $.create("embed-video"),
    );
    assert.equal(message_parser.message_has_link_preview(embed_video_content), true);

    const vimeo_content = '<div class="vimeo-video message_inline_image">preview</div>';
    $(`<div>${vimeo_content}</div>`).set_find_results(preview_selector, $.create("vimeo"));
    assert.equal(message_parser.message_has_link_preview(vimeo_content), true);

    const plain_content = "<p>plain text</p>";
    $(`<div>${plain_content}</div>`).set_find_results(preview_selector, []);
    assert.equal(message_parser.message_has_link_preview(plain_content), false);
});
