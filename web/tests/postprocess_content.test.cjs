"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const thumbnail = mock_esm("../src/thumbnail");

const {postprocess_content} = zrequire("postprocess_content");
const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {web_font_size_px: 16};
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
                "</div>" +
                '<div class="message_inline_image message_inline_video">' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.mp4">' +
                '<video src="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.mp4"></video>' +
                "</a>" +
                "</div>" +
                '<div class="youtube-video message_inline_image">' +
                '<a class="" href="https://www.youtube.com/watch?v=tyKJueEk0XM">' +
                '<img src="https://i.ytimg.com/vi/tyKJueEk0XM/default.jpg">' +
                "</a>" +
                "</div>" +
                '<div class="message_embed">' +
                '<a class="message_embed_image" href="https://example.com/about" style="background-image: url(&quot;https://example.com/preview.jpeg&quot;)"></a>' +
                '<div class="data-container">' +
                '<div class="message_embed_title">' +
                '<a href="https://example.com/about">About us</a>' +
                "</div>" +
                '<div class="message_embed_description">All about us.</div>' +
                "</div>" +
                "</div>",
        ),
        '<a href="http://example.com" target="_blank" rel="noopener noreferrer" title="http://example.com/">good</a> ' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png" target="_blank" rel="noopener noreferrer" title="translated: Download file.png">upload</a> ' +
            "<a>invalid</a> " +
            "<a>unsafe</a> " +
            '<a href="/#fragment" title="http://zulip.zulipdev.com/#fragment">fragment</a>' +
            '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.png" target="_blank" rel="noopener noreferrer" aria-label="inline image">upload</a> ' +
            '<a role="button">button</a> ' +
            "</div>" +
            '<div class="message_inline_image message_inline_video">' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.mp4" target="_blank" rel="noopener noreferrer" class="media-anchor-element">' +
            '<video src="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline.mp4" class="media-video-element media-image-element"></video>' +
            "</a>" +
            "</div>" +
            '<div class="youtube-video message_inline_image">' +
            '<a class="media-anchor-element" href="https://www.youtube.com/watch?v=tyKJueEk0XM" target="_blank" rel="noopener noreferrer">' +
            '<img src="https://i.ytimg.com/vi/tyKJueEk0XM/mqdefault.jpg" class="media-image-element" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>" +
            '<div class="message_embed">' +
            '<a class="message_embed_image" href="https://example.com/about" style="background-image: url(&quot;https://example.com/preview.jpeg&quot;)" target="_blank" rel="noopener noreferrer" title="https://example.com/about"></a>' +
            '<div class="data-container">' +
            '<div class="message_embed_title">' +
            '<a href="https://example.com/about" target="_blank" rel="noopener noreferrer" class="message-embed-title-link" title="https://example.com/about">About us</a>' +
            "</div>" +
            '<div class="message_embed_description">All about us.</div>' +
            "</div>" +
            "</div>",
    );
});

run_test("ordered_lists", () => {
    assert.equal(
        postprocess_content('<ol start="9"><li>Nine</li><li>Ten</li></ol>'),
        '<ol start="9" class="counter-length-2" style="counter-reset: count 8;"><li>Nine</li><li>Ten</li></ol>',
    );
});

run_test("inline_image_galleries", ({override}) => {
    const thumbnail_formats = [
        {
            name: "840x560.webp",
            max_width: 840,
            max_height: 560,
            format: "webp",
            animated: false,
        },
    ];
    override(thumbnail, "preferred_format", thumbnail_formats[0]);
    assert.equal(
        postprocess_content(
            "<p>Message text</p>" +
                '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="1000x2000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>" +
                '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="2000x1000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>" +
                "<p>Message text</p>" +
                '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="1000x1000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        "<p>Message text</p>" +
            '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="1000x2000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" class="media-image-element portrait-thumbnail" width="1000" height="2000" style="width: 5em;" loading="lazy">' +
            "</a>" +
            "</div>" +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="2000x1000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" class="media-image-element landscape-thumbnail" width="2000" height="1000" style="width: 20em;" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>" +
            "<p>Message text</p>" +
            '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="1000x1000" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp" class="media-image-element portrait-thumbnail" width="1000" height="1000" style="width: 10em;" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>",
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

    // Test for landscape thumbnails
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" class="media-image-element landscape-thumbnail" width="3264" height="2448" style="width: 13.333333333333334em;" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>",
    );

    // Test for portrait thumbnails
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="100x200" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="100x200" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" class="media-image-element portrait-thumbnail" width="100" height="200" style="width: 5em;" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>",
    );

    // Test for dinky thumbnails
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/image.png" title="image.png">' +
                '<img data-original-dimensions="1x10" src="/user_uploads/thumbnail/path/to/image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="1x10" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" class="media-image-element dinky-thumbnail extreme-aspect-ratio portrait-thumbnail" width="1" height="10" style="width: 1px;" loading="lazy">' +
            "</a>" +
            "</div>" +
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
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200-anim.webp" data-animated="true" class="media-image-element landscape-thumbnail" width="3264" height="2448" style="width: 13.333333333333334em;" loading="lazy">' +
            "</a>" +
            "</div>" +
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
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" data-animated="true" class="media-image-element landscape-thumbnail" width="3264" height="2448" style="width: 13.333333333333334em;" loading="lazy">' +
            "</a>" +
            "</div>" +
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
        '<div class="message-thumbnail-gallery">' +
            '<div class="message_inline_image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/image.png/300x200.webp" data-animated="true" class="media-image-element landscape-thumbnail" width="3264" height="2448" style="width: 13.333333333333334em;" loading="lazy">' +
            "</a>" +
            "</div>" +
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
