"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const thumbnail = mock_esm("../src/thumbnail", {
    get_media_preview_size() {
        return 10;
    },
});

const hash_util = mock_esm("../src/hash_util", {
    decode_stream_topic_from_url() {
        return null;
    },
    decode_dm_recipient_user_ids_from_narrow_url() {
        return null;
    },
});

const message_store = mock_esm("../src/message_store", {
    get() {
        return undefined;
    },
});

const stream_data = mock_esm("../src/stream_data", {
    get_stream_name_from_id() {
        return undefined;
    },
});

const topic_link_util = mock_esm("../src/topic_link_util", {
    get_topic_link_content_with_stream_id() {
        return {label_text_markdown: "", url: ""};
    },
});

const emoji = mock_esm("../src/emoji", {
    get_realm_emoji_url() {
        return undefined;
    },
});

const {postprocess_content} = zrequire("postprocess_content");
const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {web_font_size_px: 16};
initialize_user_settings({user_settings});

run_test("emoji_only", () => {
    // Test emoji-only message
    assert.equal(
        postprocess_content(
            '<p><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span></p>',
        ),
        '<p class="emoji-only"><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span></p>',
    );
    // Test emoji with other text content
    assert.equal(
        postprocess_content(
            '<p><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span> hi</p>',
        ),
        '<p><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span> hi</p>',
    );
    // Test emoji with other node content
    assert.equal(
        postprocess_content(
            '<p><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span> <strong>hi</strong></p>',
        ),
        '<p><span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span> <strong>hi</strong></p>',
    );
});

run_test("ordered_lists", () => {
    assert.equal(
        postprocess_content('<ol start="9"><li>Nine</li><li>Ten</li></ol>'),
        '<ol start="9" class="counter-length-2" style="counter-reset: count 8;"><li>Nine</li><li>Ten</li></ol>',
    );
});

// Care should be taken to present real-world cases here and
// throughout, rather than contrived examples that serve
// only to satisfy 100% test coverage.
run_test("postprocess_basic_links", () => {
    assert.equal(
        postprocess_content(
            '<a href="http://example.com">good</a> ' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png">upload</a> ' +
                '<a href="http://localhost:NNNN">invalid</a> ' +
                '<a href="javascript:alert(1)">unsafe</a> ' +
                '<a href="/#fragment" target="_blank">fragment</a>' +
                "<a>missing href</a>",
        ),
        '<a href="http://example.com" target="_blank" rel="noopener noreferrer" title="http://example.com/">good</a> ' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png" target="_blank" rel="noopener noreferrer" title="translated: Download file.png">upload</a> ' +
            "<a>invalid</a> " +
            "<a>unsafe</a> " +
            '<a href="/#fragment" title="http://zulip.zulipdev.com/#fragment">fragment</a>' +
            "<a>missing href</a>",
    );
});

run_test("postprocess_media_and_embeds", () => {
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image message_inline_video">' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline-video-embed.mp4">' +
                '<video src="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline-video-embed.mp4"></video>' +
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
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-video message_inline_video">' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline-video-embed.mp4" target="_blank" rel="noopener noreferrer" class="media-anchor-element">' +
            '<video src="http://zulip.zulipdev.com/user_uploads/w/ha/tever/inline-video-embed.mp4" class="media-video-element media-image-element"></video>' +
            "</a>" +
            "</div>" +
            '<div class="youtube-video message-media-preview-image">' +
            '<a class="media-anchor-element" href="https://www.youtube.com/watch?v=tyKJueEk0XM" target="_blank" rel="noopener noreferrer">' +
            '<img src="https://i.ytimg.com/vi/tyKJueEk0XM/mqdefault.jpg" class="media-image-element" loading="lazy">' +
            "</a>" +
            "</div>" +
            "</div>" +
            '<div class="message_embed">' +
            '<a class="message_embed_image" href="https://example.com/about" style="background-image: url(&quot;https://example.com/preview.jpeg&quot;)" target="_blank" rel="noopener noreferrer" title="https://example.com/about"></a>' +
            '<div class="data-container">' +
            '<div class="message_embed_title">' +
            '<a href="https://example.com/about" class="message-embed-title-link" target="_blank" rel="noopener noreferrer" title="https://example.com/about">About us</a>' +
            "</div>" +
            '<div class="message_embed_description">All about us.</div>' +
            "</div>" +
            "</div>",
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
                '<a href="/user_uploads/path/to/legacy-portrait-image.png" title="legacy-portrait-image.png">' +
                '<img data-original-dimensions="1000x2000" src="/user_uploads/thumbnail/path/to/legacy-portrait-image.png/840x560.webp">' +
                "</a>" +
                "</div>" +
                '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/legacy-landscape-image.png" title="legacy-landscape-image.png">' +
                '<img data-original-dimensions="2000x1000" src="/user_uploads/thumbnail/path/to/legacy-landscape-image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        "<p>Message text</p>" +
            '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/legacy-portrait-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="legacy-portrait-image.png">' +
            '<img data-original-dimensions="1000x2000" src="/user_uploads/thumbnail/path/to/legacy-portrait-image.png/840x560.webp" ' +
            'class="media-image-element portrait-thumbnail" loading="lazy" width="1000" height="2000" style="width: 5em; aspect-ratio: 1000 / 2000;">' +
            "</a>" +
            "</div>" +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/legacy-landscape-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="legacy-landscape-image.png">' +
            '<img data-original-dimensions="2000x1000" src="/user_uploads/thumbnail/path/to/legacy-landscape-image.png/840x560.webp" ' +
            'class="media-image-element landscape-thumbnail" loading="lazy" width="2000" height="1000" style="width: 20em; aspect-ratio: 2000 / 1000;">' +
            "</a>" +
            "</div>" +
            "</div>",
        "** Legacy gallery failed to post-process",
    );

    assert.equal(
        postprocess_content(
            "<p>Message text</p>" +
                '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/legacy-singleton-image.png" title="legacy-singleton-image.png">' +
                '<img data-original-dimensions="1000x1000" src="/user_uploads/thumbnail/path/to/legacy-singleton-image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        "<p>Message text</p>" +
            '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/legacy-singleton-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="legacy-singleton-image.png">' +
            '<img data-original-dimensions="1000x1000" src="/user_uploads/thumbnail/path/to/legacy-singleton-image.png/840x560.webp" ' +
            'class="media-image-element portrait-thumbnail" loading="lazy" width="1000" height="1000" style="width: 10em; aspect-ratio: 1000 / 1000;">' +
            "</a>" +
            "</div>" +
            "</div>",
        "** Legacy singleton gallery failed to post-process",
    );

    assert.equal(
        postprocess_content(
            "<p>" +
                '<img alt="image" class="inline-image" data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/inline-image-wide.png" src="/user_uploads/thumbnail/path/to/inline-image-wide.png/900x600.webp">' +
                " or " +
                '<img alt="image" class="inline-image" data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/inline-image-tall.png" src="/user_uploads/thumbnail/path/to/inline-image-tall.png/600x900.webp">' +
                "</p>",
        ),
        "<p>" +
            '<span class="message-media-inline-image">' +
            '<a href="/user_uploads/path/to/inline-image-wide.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image">' +
            '<img alt="image" class="inline-image image-opens-message media-image-element landscape-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/inline-image-wide.png" ' +
            'src="/user_uploads/thumbnail/path/to/inline-image-wide.png/840x560.webp" loading="lazy" width="900" height="600" style="width: 15em; aspect-ratio: 900 / 600;">' +
            "</a>" +
            "</span>" +
            " or " +
            '<span class="message-media-inline-image">' +
            '<a href="/user_uploads/path/to/inline-image-tall.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image">' +
            '<img alt="image" class="inline-image media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/inline-image-tall.png" ' +
            'src="/user_uploads/thumbnail/path/to/inline-image-tall.png/840x560.webp" loading="lazy" width="600" height="900" style="width: 6.666666666666667em; aspect-ratio: 600 / 900;">' +
            "</a>" +
            "</span>" +
            "</p>",
        "** Inline image gallery with text separator failed to post-process",
    );

    assert.equal(
        postprocess_content(
            "<p>" +
                '<img alt="image" class="inline-image" data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/inline-image-wide.png" src="/user_uploads/thumbnail/path/to/inline-image-wide.png/900x600.webp">' +
                "<br>\n" +
                '<img alt="image" class="inline-image" data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/inline-image-tall.png" src="/user_uploads/thumbnail/path/to/inline-image-tall.png/600x900.webp">' +
                "</p>",
        ),
        "<p>" +
            '<span class="message-thumbnail-gallery">' +
            '<span class="message-media-inline-image message-media-gallery-image">' +
            '<a href="/user_uploads/path/to/inline-image-wide.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image">' +
            '<img alt="image" class="inline-image media-image-element landscape-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/inline-image-wide.png" ' +
            'src="/user_uploads/thumbnail/path/to/inline-image-wide.png/840x560.webp" loading="lazy" width="900" height="600" style="width: 15em; aspect-ratio: 900 / 600;">' +
            "</a>" +
            "</span>" +
            '<span class="message-media-inline-image message-media-gallery-image">' +
            '<a href="/user_uploads/path/to/inline-image-tall.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="image">' +
            '<img alt="image" class="inline-image media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/inline-image-tall.png" ' +
            'src="/user_uploads/thumbnail/path/to/inline-image-tall.png/840x560.webp" loading="lazy" width="600" height="900" style="width: 6.666666666666667em; aspect-ratio: 600 / 900;">' +
            "</a>" +
            "</span>" +
            "</span>\n" +
            "</p>",
        "** Inline image gallery with break separator failed to post-process",
    );

    assert.equal(
        postprocess_content(
            '<p>And here is a gallery in the inline style, with text before the images...<br>\n<img alt="inline-image-01.png" class="inline-image" data-original-content-type="image/png" data-original-dimensions="800x800" data-original-src="/user_uploads/2/17/k0c4iGRefC2aCr4Jxf6NQdfH/inline-image-01.png" src="/user_uploads/thumbnail/2/17/k0c4iGRefC2aCr4Jxf6NQdfH/inline-image-01.png/840x560.webp"><br>\n<img alt="inline-image-02.png" class="inline-image" data-original-content-type="image/png" data-original-dimensions="800x800" data-original-src="/user_uploads/2/3f/B0vUyCSpixMgDLG29fKeUkk6/inline-image-02.png" src="/user_uploads/thumbnail/2/3f/B0vUyCSpixMgDLG29fKeUkk6/inline-image-02.png/840x560.webp"><br>\n...and text after (again, line breaks only, no new paragraphs).</p>' +
                '<p><img alt="inline-image-square.png" class="inline-image" data-original-content-type="image/png" data-original-dimensions="800x800" data-original-src="/user_uploads/2/48/mo114lAto6fft973UYWtik2T/inline-image-square.png" src="/user_uploads/thumbnail/2/48/mo114lAto6fft973UYWtik2T/inline-image-square.png/840x560.webp"></p>' +
                '<p><img alt="inline-image-03.png" class="inline-image" data-original-content-type="image/png" data-original-dimensions="800x800" data-original-src="/user_uploads/2/1e/qsBe-4wztqriUHkB2ukYdauM/inline-image-03.png" src="/user_uploads/thumbnail/2/1e/qsBe-4wztqriUHkB2ukYdauM/inline-image-03.png/840x560.webp"> inline image with trailing text</p>',
        ),
        "<p>And here is a gallery in the inline style, with text before the images...\n" +
            '<span class="message-thumbnail-gallery"><span class="message-media-inline-image message-media-gallery-image">' +
            '<a href="/user_uploads/2/17/k0c4iGRefC2aCr4Jxf6NQdfH/inline-image-01.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="inline-image-01.png">' +
            '<img alt="inline-image-01.png" class="inline-image media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="800x800" data-original-src="/user_uploads/2/17/k0c4iGRefC2aCr4Jxf6NQdfH/inline-image-01.png" ' +
            'src="/user_uploads/thumbnail/2/17/k0c4iGRefC2aCr4Jxf6NQdfH/inline-image-01.png/840x560.webp" ' +
            'loading="lazy" width="800" height="800" style="width: 10em; aspect-ratio: 800 / 800;">' +
            "</a></span>" +
            '<span class="message-media-inline-image message-media-gallery-image">' +
            '<a href="/user_uploads/2/3f/B0vUyCSpixMgDLG29fKeUkk6/inline-image-02.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="inline-image-02.png">' +
            '<img alt="inline-image-02.png" class="inline-image media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="800x800" data-original-src="/user_uploads/2/3f/B0vUyCSpixMgDLG29fKeUkk6/inline-image-02.png" ' +
            'src="/user_uploads/thumbnail/2/3f/B0vUyCSpixMgDLG29fKeUkk6/inline-image-02.png/840x560.webp" ' +
            'loading="lazy" width="800" height="800" style="width: 10em; aspect-ratio: 800 / 800;">' +
            "</a></span></span>\n" +
            "\n" +
            "...and text after (again, line breaks only, no new paragraphs).</p>" +
            '<p><span class="message-thumbnail-gallery"><span class="message-media-inline-image message-media-gallery-image">' +
            '<a href="/user_uploads/2/48/mo114lAto6fft973UYWtik2T/inline-image-square.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="inline-image-square.png">' +
            '<img alt="inline-image-square.png" class="inline-image media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="800x800" data-original-src="/user_uploads/2/48/mo114lAto6fft973UYWtik2T/inline-image-square.png" ' +
            'src="/user_uploads/thumbnail/2/48/mo114lAto6fft973UYWtik2T/inline-image-square.png/840x560.webp" ' +
            'loading="lazy" width="800" height="800" style="width: 10em; aspect-ratio: 800 / 800;">' +
            "</a></span></span></p>" +
            '<p><span class="message-media-inline-image">' +
            '<a href="/user_uploads/2/1e/qsBe-4wztqriUHkB2ukYdauM/inline-image-03.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="inline-image-03.png">' +
            '<img alt="inline-image-03.png" class="inline-image image-opens-message media-image-element portrait-thumbnail" data-original-content-type="image/png" ' +
            'data-original-dimensions="800x800" data-original-src="/user_uploads/2/1e/qsBe-4wztqriUHkB2ukYdauM/inline-image-03.png" ' +
            'src="/user_uploads/thumbnail/2/1e/qsBe-4wztqriUHkB2ukYdauM/inline-image-03.png/840x560.webp" ' +
            'loading="lazy" width="800" height="800" style="width: 10em; aspect-ratio: 800 / 800;">' +
            "</a></span> inline image with trailing text</p>",
        "** Inline image gallery with leading text, break separator failed to post-process",
    );
});

run_test("message_image_thumbnailing", ({override}) => {
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
                '<a href="/user_uploads/path/to/landscape-thumbnailed-image.png" title="landscape-thumbnailed-image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/landscape-thumbnailed-image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/landscape-thumbnailed-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="landscape-thumbnailed-image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/landscape-thumbnailed-image.png/300x200.webp" ' +
            'class="media-image-element landscape-thumbnail" loading="lazy" width="3264" height="2448" style="width: 13.333333333333334em; aspect-ratio: 3264 / 2448;">' +
            "</a>" +
            "</div>" +
            "</div>",
    );

    // Test for portrait thumbnails
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/portrait-thumbnailed-image.png" title="portrait-thumbnailed-image.png">' +
                '<img data-original-dimensions="100x200" src="/user_uploads/thumbnail/path/to/portrait-thumbnailed-image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/portrait-thumbnailed-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="portrait-thumbnailed-image.png">' +
            '<img data-original-dimensions="100x200" src="/user_uploads/thumbnail/path/to/portrait-thumbnailed-image.png/300x200.webp" ' +
            'class="media-image-element portrait-thumbnail" loading="lazy" width="100" height="200" style="width: 5em; aspect-ratio: 100 / 200;">' +
            "</a>" +
            "</div>" +
            "</div>",
    );

    // Test for dinky thumbnails
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/dinky-thumbnailed-image.png" title="dinky-thumbnailed-image.png">' +
                '<img data-original-dimensions="1x10" src="/user_uploads/thumbnail/path/to/dinky-thumbnailed-image.png/840x560.webp">' +
                "</a>" +
                "</div>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/dinky-thumbnailed-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="dinky-thumbnailed-image.png">' +
            '<img data-original-dimensions="1x10" src="/user_uploads/thumbnail/path/to/dinky-thumbnailed-image.png/300x200.webp" ' +
            'class="media-image-element dinky-thumbnail extreme-aspect-ratio portrait-thumbnail" loading="lazy" width="1" height="10" style="width: 1px; aspect-ratio: 1 / 10;">' +
            "</a>" +
            "</div>" +
            "</div>",
    );

    // Now verify the behavior for animated images.
    override(user_settings, "web_animate_image_previews", "always");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" title="preview-animated-legacy-image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>" +
                "<p>" +
                '<img alt="preview-animated-image-landscape" class="inline-image" data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/900x600.webp" data-animated="true">' +
                " or " +
                '<img alt="preview-animated-image-portrait" class="inline-image" data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/600x900.webp" data-animated="true">' +
                "</p>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image">' +
            '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-legacy-image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/300x200-anim.webp" ' +
            'data-animated="true" class="media-image-element landscape-thumbnail" loading="lazy" width="3264" height="2448" style="width: 13.333333333333334em; aspect-ratio: 3264 / 2448;">' +
            "</a>" +
            "</div>" +
            "</div>" +
            "<p>" +
            '<span class="message-media-inline-image">' +
            '<a href="/user_uploads/path/to/preview-animated-image-landscape.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-landscape">' +
            '<img alt="preview-animated-image-landscape" class="inline-image image-opens-message media-image-element landscape-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/300x200-anim.webp" data-animated="true" ' +
            'loading="lazy" width="900" height="600" style="width: 15em; aspect-ratio: 900 / 600;">' +
            "</a>" +
            "</span>" +
            " or " +
            '<span class="message-media-inline-image">' +
            '<a href="/user_uploads/path/to/preview-animated-image-portrait.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-portrait">' +
            '<img alt="preview-animated-image-portrait" class="inline-image media-image-element portrait-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/300x200-anim.webp" data-animated="true" ' +
            'loading="lazy" width="600" height="900" style="width: 6.666666666666667em; aspect-ratio: 600 / 900;">' +
            "</a>" +
            "</span>" +
            "</p>",
    );

    // And verify the different behavior for other values of the animation setting.
    override(user_settings, "web_animate_image_previews", "on_hover");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" title="preview-animated-legacy-image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>" +
                "<p>" +
                '<img alt="preview-animated-image-landscape" class="inline-image" data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/900x600.webp" data-animated="true">' +
                " or " +
                '<img alt="preview-animated-image-portrait" class="inline-image" data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/600x900.webp" data-animated="true">' +
                "</p>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-legacy-image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/300x200.webp" ' +
            'data-animated="true" class="media-image-element landscape-thumbnail" loading="lazy" width="3264" height="2448" style="width: 13.333333333333334em; aspect-ratio: 3264 / 2448;">' +
            "</a>" +
            "</div>" +
            "</div>" +
            "<p>" +
            '<span class="message-media-inline-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-image-landscape.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-landscape">' +
            '<img alt="preview-animated-image-landscape" class="inline-image image-opens-message media-image-element landscape-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/300x200.webp" ' +
            'data-animated="true" loading="lazy" width="900" height="600" style="width: 15em; aspect-ratio: 900 / 600;">' +
            "</a>" +
            "</span>" +
            " or " +
            '<span class="message-media-inline-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-image-portrait.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-portrait">' +
            '<img alt="preview-animated-image-portrait" class="inline-image media-image-element portrait-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/300x200.webp" ' +
            'data-animated="true" loading="lazy" width="600" height="900" style="width: 6.666666666666667em; aspect-ratio: 600 / 900;">' +
            "</a>" +
            "</span>" +
            "</p>",
    );

    override(user_settings, "web_animate_image_previews", "never");
    assert.equal(
        postprocess_content(
            '<div class="message_inline_image">' +
                '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" title="preview-animated-legacy-image.png">' +
                '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/840x560.webp" data-animated="true">' +
                "</a>" +
                "</div>" +
                "<p>" +
                '<img alt="preview-animated-image-landscape" class="inline-image" data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/900x600.webp" data-animated="true">' +
                " or " +
                '<img alt="preview-animated-image-portrait" class="inline-image" data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/600x900.webp" data-animated="true">' +
                "</p>",
        ),
        '<div class="message-thumbnail-gallery">' +
            '<div class="message-media-preview-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-legacy-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-legacy-image.png">' +
            '<img data-original-dimensions="3264x2448" src="/user_uploads/thumbnail/path/to/preview-animated-legacy-image.png/300x200.webp" ' +
            'data-animated="true" class="media-image-element landscape-thumbnail" loading="lazy" width="3264" height="2448" style="width: 13.333333333333334em; aspect-ratio: 3264 / 2448;">' +
            "</a>" +
            "</div>" +
            "</div>" +
            "<p>" +
            '<span class="message-media-inline-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-image-landscape.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-landscape">' +
            '<img alt="preview-animated-image-landscape" class="inline-image image-opens-message media-image-element landscape-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="900x600" data-original-src="/user_uploads/path/to/preview-animated-image-landscape.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-landscape.png/300x200.webp" ' +
            'data-animated="true" loading="lazy" width="900" height="600" style="width: 15em; aspect-ratio: 900 / 600;">' +
            "</a>" +
            "</span>" +
            " or " +
            '<span class="message-media-inline-image message_inline_animated_image_still">' +
            '<a href="/user_uploads/path/to/preview-animated-image-portrait.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="preview-animated-image-portrait">' +
            '<img alt="preview-animated-image-portrait" class="inline-image media-image-element portrait-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="600x900" data-original-src="/user_uploads/path/to/preview-animated-image-portrait.png" ' +
            'src="/user_uploads/thumbnail/path/to/preview-animated-image-portrait.png/300x200.webp" ' +
            'data-animated="true" loading="lazy" width="600" height="900" style="width: 6.666666666666667em; aspect-ratio: 600 / 900;">' +
            "</a>" +
            "</span>" +
            "</p>",
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

run_test("inline_images", ({override}) => {
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
            '<img alt="dinky-inline-image" class="inline-image" data-original-content-type="image/png" data-original-dimensions="128x128" data-original-src="/user_uploads/path/to/dinky-inline-image.png" src="/user_uploads/thumbnail/path/to/dinky-inline-image.png/840x560.webp">',
        ),
        '<span class="message-media-inline-image">' +
            '<a href="/user_uploads/path/to/dinky-inline-image.png" target="_blank" rel="noopener noreferrer" class="media-anchor-element" aria-label="dinky-inline-image">' +
            '<img alt="dinky-inline-image" class="inline-image media-image-element dinky-thumbnail portrait-thumbnail" ' +
            'data-original-content-type="image/png" data-original-dimensions="128x128" data-original-src="/user_uploads/path/to/dinky-inline-image.png" ' +
            'src="/user_uploads/thumbnail/path/to/dinky-inline-image.png/840x560.webp" loading="lazy" width="128" height="128" style="width: 128px; aspect-ratio: 128 / 128;">' +
            "</a>" +
            "</span>",
    );

    // Broken/invalid source URLs in image previews should be
    // dropped. Inspired by a real message found in chat.zulip.org
    // history.
    assert.equal(
        postprocess_content(
            '<img class="inline-image" data-original-src="https://zulip.%20[Click%20to%20join%20video%20call](https://meeting.example.com/abcd1234)%20example.com/user_uploads/2/ab/abcd1234/image.png" src="https://zulip.%20[Click%20to%20join%20video%20call](https://meeting.example.com/abcd1234)%20example.com/user_uploads/2/ab/abcd1234/image.png">',
        ),
        "",
    );
});

function reply_input(opts) {
    // Builds the raw HTML the server sends when a message starts with a
    // reply prefix: a leading paragraph with [user-mention, anchor], plus
    // at least one extra node so postprocess_content actually runs the
    // reply check (it skips single-node messages).
    const mention_text = opts.silent ? opts.full_name : `@${opts.full_name}`;
    const silent_class = opts.silent ? " silent" : "";
    return (
        `<p>` +
        `<span class="user-mention${silent_class}" data-user-id="${opts.user_id}">` +
        `${mention_text}</span> ` +
        `<a href="${opts.href}">${opts.snippet_html}</a>` +
        `</p>` +
        `<p>Body of the reply.</p>`
    );
}

run_test("reply_pattern_non_silent_same_topic", ({override}) => {
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", (id) => (id === 9 ? "devel" : undefined));
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hello",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /<span class="reply">/u);
    // The reply mention always renders as `@FullName` regardless of silent state.
    assert.match(html, /data-full-name="Hamlet"/u);
    assert.match(html, /@Hamlet/u);
    // Non-silent → no `silent` class on the reply mention.
    assert.doesNotMatch(html, /reply-user-mention[^"]*\bsilent\b/u);
    // Topic link is suppressed when the compose target matches.
    assert.match(html, /referenced-message-topic-link[^"]*\bhidden\b/u);
});

run_test("reply_pattern_silent_strips_leading_at", ({override}) => {
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", () => "devel");
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));

    // Server emits silent mentions as `Hamlet` (no leading `@`). The reply
    // UI must always display `@Hamlet`; the `silent` class carries the
    // state. This is the load-bearing "no text shift" property.
    const html = postprocess_content(
        reply_input({
            silent: true,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hello",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /reply-user-mention[^"]*\bsilent\b/u);
    assert.match(html, /data-full-name="Hamlet"/u);
    assert.match(html, /@Hamlet/u);
});

run_test("reply_pattern_different_topic_shows_link", ({override}) => {
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", () => "devel");
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));

    // Composing in a different topic than the referenced message → topic
    // link is not hidden.
    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hello",
        }),
        "devel",
        "different-topic",
    );

    assert.match(html, /referenced-message-topic-link(?![^"]*\bhidden\b)/u);
    assert.match(html, />#devel &gt; grail</u);
});

run_test("reply_pattern_dm_url_renders", ({override}) => {
    // DM narrows don't decode as channel/topic; they decode as recipient
    // ids. The reply UI still renders, but no topic-link content is set.
    override(hash_util, "decode_stream_topic_from_url", () => null);
    override(hash_util, "decode_dm_recipient_user_ids_from_narrow_url", () => [7]);

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Othello",
            user_id: 7,
            href: "/#narrow/dm/7-Othello/near/42",
            snippet_html: "Hi",
        }),
    );

    assert.match(html, /<span class="reply">/u);
    assert.match(html, /data-full-name="Othello"/u);
});

run_test("reply_pattern_invalid_url_leaves_paragraph_intact", () => {
    // External link → not a valid topic/DM URL → no reply UI; the
    // original <p> survives (mention and anchor still present in raw form).
    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "https://example.com/some/page",
            snippet_html: "click here",
        }),
    );

    assert.doesNotMatch(html, /<span class="reply">/u);
    assert.match(html, /class="user-mention"/u);
});

run_test("reply_pattern_preserves_inline_html_in_snippet", ({override}) => {
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", () => "devel");
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));

    // The snippet HTML inside the anchor — emoji spans, <strong>, etc. —
    // must survive into the rendered reply line via {{{content_html}}}.
    const snippet_html =
        'hello <span aria-label="wave" class="emoji emoji-1f44b" role="img" title="wave">:wave:</span> <strong>world</strong>';
    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html,
        }),
        "devel",
        "grail",
    );

    assert.match(html, /class="emoji emoji-1f44b"/u);
    assert.match(html, /<strong>world<\/strong>/u);
});

run_test("reply_pattern_substitutes_realm_emoji_shortcodes", ({override}) => {
    // The server's markdown processor doesn't expand emoji shortcodes
    // inside link text (it wraps the link's text in AtomicString). On the
    // receiving side, we substitute realm emoji shortcodes with their
    // image element so custom emoji render as glyphs instead of literal
    // text in the reply snippet.
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", () => "devel");
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));
    override(emoji, "get_realm_emoji_url", (name) =>
        name === "zulip" ? "/realm-emoji/zulip.png" : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "All about headlights :zulip: running :unknown_emoji:",
        }),
        "devel",
        "grail",
    );

    // Known realm emoji becomes an <img>.
    assert.match(
        html,
        /<img[^>]*class="emoji"[^>]*alt=":zulip:"[^>]*src="\/realm-emoji\/zulip\.png"/u,
    );
    // Unknown shortcodes are left as-is.
    assert.match(html, /:unknown_emoji:/u);
});

run_test("reply_pattern_uses_message_store_for_moved_message", ({override}) => {
    // If the referenced message has been moved, we should compute the
    // topic-link from the current message_store state, not the (stale)
    // URL hash.
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "old-topic",
        message_id: "42",
    }));
    override(message_store, "get", (id) =>
        id === 42 ? {is_stream: true, stream_id: 11, topic: "new-topic"} : undefined,
    );
    override(stream_data, "get_stream_name_from_id", (id) => (id === 11 ? "support" : undefined));
    let received_opts;
    override(topic_link_util, "get_topic_link_content_with_stream_id", (opts) => {
        received_opts = opts;
        return {label_text_markdown: "#support > new-topic", url: "/#narrow/.../new"};
    });

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/old-topic/near/42",
            snippet_html: "Hi",
        }),
        "devel",
        "old-topic",
    );

    assert.deepEqual(received_opts, {
        stream_id: 11,
        topic_name: "new-topic",
        message_id: undefined,
    });
    // After the move, the compose target ("devel"/"old-topic") doesn't
    // match the message's actual location, so the topic link is shown.
    assert.match(html, /referenced-message-topic-link(?![^"]*\bhidden\b)/u);
});

run_test("reply_pattern_extra_text_between_nodes_skips_reply", () => {
    // A paragraph with real text between the mention and the link is an
    // ordinary sentence, not a reply prefix, so it's left untouched.
    const html = postprocess_content(
        '<p><span class="user-mention" data-user-id="5">@Hamlet</span> said ' +
            '<a href="/#narrow/channel/9-devel/topic/grail/near/42">hi</a></p>' +
            "<p>Body.</p>",
    );
    assert.doesNotMatch(html, /<span class="reply">/u);
    assert.match(html, /class="user-mention"/u);
});

run_test("reply_pattern_dm_without_near_still_renders", ({override}) => {
    // A DM reply URL with no /near/ segment can't recover a message id, so we
    // never hit the store (the default mock get is left uninvoked); the reply
    // still renders from the sender's snippet.
    override(hash_util, "decode_stream_topic_from_url", () => null);
    override(hash_util, "decode_dm_recipient_user_ids_from_narrow_url", () => [7]);

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Othello",
            user_id: 7,
            href: "/#narrow/dm/7-Othello",
            snippet_html: "Hi",
        }),
    );

    assert.match(html, /<span class="reply">/u);
});

run_test("reply_pattern_unknown_stream_falls_back_to_empty_topic_link", ({override}) => {
    // The referenced stream isn't locally known, so get_stream_name_from_id and
    // get_topic_link_content_with_stream_id return their empty defaults; the
    // reply still renders, with the topic link shown (location can't be matched).
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hi",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /<span class="reply">/u);
});

function override_same_topic_reply(override) {
    override(hash_util, "decode_stream_topic_from_url", () => ({
        stream_id: 9,
        topic_name: "grail",
        message_id: "42",
    }));
    override(stream_data, "get_stream_name_from_id", () => "devel");
    override(topic_link_util, "get_topic_link_content_with_stream_id", () => ({
        label_text_markdown: "#devel > grail",
        url: "/#narrow/channel/9-devel/topic/grail/near/42",
    }));
}

run_test("reply_pattern_media_only_renders_badge_and_thumbnail", ({override}) => {
    override_same_topic_reply(override);
    // The referenced message is image-only. We classify it from its own
    // content — not the sender's stored snippet text — so the badge is the
    // same in every locale, and re-inject its thumbnail in a card cell.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<div class="message_inline_image">' +
                      '<a href="/user_uploads/x/photo.png" title="photo.png">' +
                      '<img src="/user_uploads/thumbnail/x/photo.png/840x560.webp"></a></div>',
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Image photo.png",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /<span class="reply">/u);
    assert.match(html, /reply-type-badge">[^<]*Image</u);
    assert.match(html, /photo\.png/u);
    // Thumbnail rendered in its own card cell, sourced from the message.
    assert.match(html, /reply-thumbnail-cell/u);
    assert.match(html, /class="reply-line-thumbnail"/u);
    assert.match(html, /src="\/user_uploads\/thumbnail\/x\/photo\.png\/840x560\.webp"/u);
});

run_test("reply_pattern_link_preview_renders_badge_and_thumbnail", ({override}) => {
    override_same_topic_reply(override);
    // The referenced message is a bare link with a website preview: its only
    // top-level text is the link itself, so it counts as media (Link badge +
    // preview thumbnail) rather than being quoted as inline text.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><a href="https://e.com">https://e.com</a></p>' +
                      '<div class="message_embed">' +
                      '<a class="message_embed_image" href="https://e.com" ' +
                      'style="background-image: url(&quot;https://e.com/p.jpg&quot;)"></a>' +
                      '<div class="message_embed_title"><a href="https://e.com">About</a></div></div>',
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Link About",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /reply-type-badge">[^<]*Link</u);
    assert.match(html, /About/u);
    assert.match(html, /src="https:\/\/e\.com\/p\.jpg"/u);
});

run_test("reply_pattern_math_only_renders_badge", ({override}) => {
    override_same_topic_reply(override);
    // Display math renders inside a `<p>`, and its MathML carries text — so
    // without dropping `.katex-display` first, the message would look like it
    // has quotable inline text and we'd keep the sender's flattened snippet
    // ("Math x^2") instead of re-deriving the locale-correct Math badge.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><span class="katex-display"><span class="katex">' +
                      '<span class="katex-mathml"><math><semantics>' +
                      '<annotation encoding="application/x-tex">x^2</annotation>' +
                      "</semantics></math></span></span></span></p>",
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Math x^2",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /reply-type-badge">[^<]*Math</u);
    assert.match(html, /x\^2/u);
});

run_test("reply_pattern_widget_renders_badge_from_submessages", ({override}) => {
    override_same_topic_reply(override);
    // A poll's rendered content is the literal "/poll …" command text, which
    // must not be treated as quotable inline text. The badge and question
    // come from the message's submessages.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  content: "<p>/poll Lunch?</p>",
                  submessages: [
                      {
                          content: JSON.stringify({
                              widget_type: "poll",
                              extra_data: {question: "Lunch?"},
                          }),
                      },
                  ],
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Poll Lunch?",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /reply-type-badge">[^<]*Poll</u);
    assert.match(html, /Lunch\?/u);
    // The raw "/poll" command text is never shown as the snippet.
    assert.doesNotMatch(html, /\/poll/u);
});

run_test("reply_pattern_text_message_keeps_sender_snippet", ({override}) => {
    override_same_topic_reply(override);
    // A reply to an ordinary text message keeps the sender's rendered snippet
    // and shows no type badge, even though the message is in the store.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content: "<p>Hello there</p>",
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hello there",
        }),
        "devel",
        "grail",
    );

    assert.doesNotMatch(html, /reply-type-badge/u);
    assert.match(html, />Hello there</u);
});

run_test("reply_pattern_text_snippet_rederives_mention_as_pill", ({override}) => {
    override_same_topic_reply(override);
    // The referenced message contains a mention. The sender's stored snippet
    // flattens it to plain text (the AtomicString link label), but we re-derive
    // the snippet from the referenced message itself so the mention renders as a
    // pill — matching the compose preview.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><span class="user-mention" data-user-id="11">@Cordelia</span>' +
                      " can you take a look?</p>",
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Cordelia can you take a look?",
        }),
        "devel",
        "grail",
    );

    assert.match(
        html,
        /<span class="user-mention" data-user-id="11">@Cordelia<\/span> can you take a look\?/u,
    );
});

run_test("reply_pattern_text_snippet_falls_back_when_message_uncached", ({override}) => {
    override_same_topic_reply(override);
    // The referenced message isn't in the local store, so we can't re-derive;
    // fall back to the sender's stored (flattened) snippet.
    override(message_store, "get", () => undefined);

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "the stored snippet text",
        }),
        "devel",
        "grail",
    );

    assert.match(html, />the stored snippet text</u);
});

run_test("reply_pattern_text_snippet_to_a_reply_drops_nested_pointer", ({override}) => {
    override_same_topic_reply(override);
    // The referenced message is itself a reply: its content starts with a reply
    // pointer line. Re-deriving shows the body, not the nested pointer.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><span class="user-mention" data-user-id="11">@Iago</span> ' +
                      '<a href="/#narrow/channel/9-devel/topic/grail/near/7">earlier snippet</a></p>' +
                      "<p>the actual body</p>",
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "earlier snippet",
        }),
        "devel",
        "grail",
    );

    assert.match(html, />the actual body</u);
    assert.doesNotMatch(html, /earlier snippet/u);
});

run_test("reply_pattern_text_snippet_keeps_a_non_message_link_line", ({override}) => {
    override_same_topic_reply(override);
    // First block is a mention + a non-message link (no `/near/`): not a reply
    // pointer, so it's kept rather than dropped.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><span class="user-mention" data-user-id="11">@Cordelia</span> ' +
                      '<a href="https://example.com">the site</a></p>',
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Cordelia the site",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /user-mention[^>]*>@Cordelia<\/span>/u);
    assert.match(html, /the site/u);
});

run_test("reply_pattern_text_snippet_keeps_reply_line_with_extra_text", ({override}) => {
    override_same_topic_reply(override);
    // A first block that looks like a reply pointer but carries extra trailing
    // text is not treated as a droppable reply line.
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content:
                      '<p><span class="user-mention" data-user-id="11">@Iago</span> ' +
                      '<a href="/#narrow/channel/9-devel/topic/grail/near/7">snip</a> and more</p>',
              }
            : undefined,
    );

    const html = postprocess_content(
        reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "x",
        }),
        "devel",
        "grail",
    );

    assert.match(html, /and more/u);
});

run_test("reply_pattern_edit_history_diff_wrapper_renders_card", ({override}) => {
    override_same_topic_reply(override);
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content: "<p>Hello there</p>",
              }
            : undefined,
    );
    // The message-edit-history diff wraps the whole message in a single <div>.
    // The reply line inside must still render as the reply card (not a raw
    // link), and the wrapping <div> is preserved.
    const html = postprocess_content(
        `<div>${reply_input({
            silent: false,
            full_name: "Hamlet",
            user_id: 5,
            href: "/#narrow/channel/9-devel/topic/grail/near/42",
            snippet_html: "Hello there",
        })}</div>`,
        "devel",
        "grail",
    );

    assert.match(html, /^<div>/u);
    assert.match(html, /<span class="reply">/u);
    assert.match(html, />Hello there</u);
});

run_test("reply_pattern_edit_history_mention_toggle_renders_card", ({override}) => {
    override_same_topic_reply(override);
    override(message_store, "get", (id) =>
        id === 42
            ? {
                  is_stream: true,
                  stream_id: 9,
                  topic: "grail",
                  submessages: [],
                  content: "<p>Hello there</p>",
              }
            : undefined,
    );
    // Edit-history diff for an edit that TOGGLED the mention: the mention is
    // split across highlight spans. The reply must still render as the card
    // (not a blue link), with the mention diff preserved inside it.
    const diff =
        "<div><p>" +
        '<span class="highlight_text_inserted"><span class="user-mention silent" data-user-id="9">' +
        '<span class="mention-content-wrapper">Hamlet</span></span></span> ' +
        '<span class="highlight_text_deleted"><span class="user-mention" data-user-id="9">' +
        '<span class="mention-content-wrapper">@Hamlet</span></span></span> ' +
        '<a href="/#narrow/channel/9-devel/topic/grail/near/42">Hello there</a>' +
        "</p><p>the body</p></div>";
    const html = postprocess_content(diff, "devel", "grail");

    // Renders the card, not a bare link, and keeps the highlight spans so the
    // toggle still reads as a change.
    assert.match(html, /<span class="reply">/u);
    assert.match(html, /highlight_text_inserted/u);
    assert.match(html, /highlight_text_deleted/u);
    assert.match(html, /reply-user-mention/u);
});

run_test("reply_in_quote_block_is_delinked", () => {
    // A scheduled reminder quotes a reply message's raw content inside a
    // blockquote. Server-generated, it isn't de-linked at compose time, so its
    // `@user [snippet](near)` pointer would render as a stray blue link. We
    // de-link it: the snippet becomes plain text while the mention pill stays.
    const reminder_html =
        "<p>You requested a reminder for the following message.</p>" +
        "<blockquote>" +
        '<p><span class="user-mention" data-user-id="5">@Hamlet</span> ' +
        '<a href="/#narrow/channel/9-devel/topic/grail/near/42">Original message.</a></p>' +
        "<p>my reply body</p>" +
        "</blockquote>";
    const html = postprocess_content(reminder_html);

    // The near-link is gone, but its text and the mention pill remain.
    assert.doesNotMatch(html, /<a [^>]*href="[^"]*\/near\/42"/u);
    assert.match(html, /Original message\./u);
    assert.match(html, /class="user-mention"/u);
    assert.match(html, /my reply body/u);
});

run_test("quote_block_without_reply_line_is_untouched", () => {
    // A plain quote (no reply pointer) must pass through unchanged.
    const html = postprocess_content(
        "<p>intro</p><blockquote><p>just a normal quoted line</p></blockquote>",
    );
    assert.match(html, /just a normal quoted line/u);
});

run_test("quote_block_with_non_reply_link_is_untouched", () => {
    // A quoted line that has two children but isn't a reply pointer (no
    // mention, no `/near/` link) keeps its link rather than being de-linked.
    const html = postprocess_content(
        "<p>intro</p><blockquote>" +
            '<p><strong>bold</strong> <a href="https://example.com">external</a></p>' +
            "</blockquote>",
    );
    assert.match(html, /<a [^>]*href="https:\/\/example\.com"/u);
});
