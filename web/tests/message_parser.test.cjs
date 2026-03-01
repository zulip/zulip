"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const message_parser = zrequire("message_parser");

const preview_selector = ".message_embed, .message_inline_image";

run_test("message_has_link_preview", () => {
    const embed_content = '<div class="message_embed">preview</div>';
    $(`<div>${embed_content}</div>`).set_find_results(preview_selector, $.create("embed"));
    assert.equal(message_parser.message_has_link_preview(embed_content), true);

    const image_content = '<div class="message_inline_image"><img src="x.png"></div>';
    $(`<div>${image_content}</div>`).set_find_results(preview_selector, $.create("image"));
    assert.equal(message_parser.message_has_link_preview(image_content), true);

    const plain_content = "<p>plain text</p>";
    $(`<div>${plain_content}</div>`).set_find_results(preview_selector, []);
    assert.equal(message_parser.message_has_link_preview(plain_content), false);
});
