"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const thumbnail = mock_esm("../src/thumbnail");

const {postprocess_content} = zrequire("postprocess_content");
const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

run_test("postprocess_content", () => {
    assert.equal(
        postprocess_content(
            '<a href="http://example.com">good</a> ' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png">upload</a> ' +
                '<a href="http://localhost:NNNN">invalid</a> ' +
                '<a href="javascript:alert(1)">unsafe</a> ' +
                '<a href="/#fragment" target="_blank">fragment</a>' +
                '<div class="message_inline_image">' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.png" title="inline image">upload</a> ' +
                '<a role="button">button</a> ' +
                "</div>",
        ),
        '<a href="http://example.com" target="_blank" rel="noopener noreferrer" title="http://example.com/">good</a> ' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png" target="_blank" rel="noopener noreferrer" title="translated: Download file.png">upload</a> ' +
            "<a>invalid</a> " +
            "<a>unsafe</a> " +
            '<a href="/#fragment" title="http://zulip.zulipdev.com/#fragment">fragment</a>' +
            '<div class="message_inline_image">' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.png" target="_blank" rel="noopener noreferrer" aria-label="inline image">upload</a> ' +
            '<a role="button">button</a> ' +
            "</div>",
    );
});

run_test("ordered_lists", () => {
    assert.equal(
        postprocess_content('<ol start="9"><li>Nine</li><li>Ten</li></ol>'),
        '<ol start="9" class="counter-length-2"><li>Nine</li><li>Ten</li></ol>',
    );
});

run_test("message_inline_animated_image_still", ({override}) => {
    const thumbnail_formats = [
        {
            name: "840x560-anim.webp",
            max_width: 840,
            max_height: 560,
            format: "webp",
            animated: true,
        },
        {
            name: "840x560.webp",
            max_width: 840,
            max_height: 560,
            format: "webp",
            animated: false,
        },
        {
            name: "300x200-anim.webp",
            max_width: 300,
            max_height: 200,
            format: "webp",
            animated: true,
        },
        {
            name: "300x200.webp",
            max_width: 300,
            max_height: 200,
            format: "webp",
            animated: false,
        },
        {
            name: "300x200.jpg",
            max_width: 300,
            max_height: 200,
            format: "jpg",
            animated: false,
        },
    ];
    // TODO: Initialize the real thumbnail.ts rather than mocking it.
    override(thumbnail, "preferred_format", thumbnail_formats[3]);
    override(thumbnail, "animated_format", thumbnail_formats[2]);

    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" loading="lazy">' +
            "</a>" +
            "</div>",
    );

    // Now verify the behavior for animated images.
    override(user_settings, "web_animate_image_previews", "always");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200-anim.webp" data-animated="true" loading="lazy">' +
            "</a>" +
            "</div>",
    );

    // And verify the different behavior for other values of the animation setting.
    override(user_settings, "web_animate_image_previews", "on_hover");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message_inline_image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" data-animated="true" loading="lazy">' +
            "</a>" +
            "</div>",
    );

    override(user_settings, "web_animate_image_previews", "never");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message_inline_image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" data-animated="true" loading="lazy">' +
            "</a>" +
            "</div>",
    );

    // Broken/invalid source URLs in image previews should be
    // dropped. Inspired by a real message found in chat.zulip.org
    // history.
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="https://zulip.%20[Click%20to%20join%20video%20call](https://meeting.example.com/abcd1234)%20example.com/user_uploads/2/ab/abcd1234/image.png" target="_blank" title="image.png">' +
                '<img src="https://zulip.%20[Click%20to%20join%20video%20call](https://meeting.example.com/abcd1234)%20example.com/user_uploads/2/ab/abcd1234/image.png">' +
                "</a>" +
                "</div>",
        ),
        "",
    );
});
