"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

const message_store = mock_esm("../src/message_store");
const rows = mock_esm("../src/rows");
const people = mock_esm("../src/people");

const lightbox = zrequire("lightbox");

// Counter to generate unique zjquery selector names.
let test_counter = 0;

function make_media_element($mock_jq, src) {
    // parse_media_data expects an HTMLImageElement, but for testing
    // we use a plain object with `src` (read by canonical_url_of_media)
    // and `to_$` (used by zjquery to wrap in FakeJQuery).
    return {
        src,
        to_$() {
            return $mock_jq;
        },
    };
}

function make_image({img_src, parent_href, parent_aria_label, img_attrs = {}}) {
    test_counter += 1;
    const n = test_counter;
    const $img = $.create(`<img-${n}>`);
    const $parent = $.create(`<parent-${n}>`);

    $img.attr("src", img_src);
    for (const [attr, value] of Object.entries(img_attrs)) {
        $img.attr(attr, value);
    }
    if (parent_href !== undefined) {
        $parent.attr("href", parent_href);
    }
    if (parent_aria_label !== undefined) {
        $parent.attr("aria-label", parent_aria_label);
    }
    $img.set_parent($parent);
    $parent.set_matches("*", true);

    // Not inside any special container by default.
    for (const sel of [
        ".youtube-video",
        ".vimeo-video",
        ".embed-video",
        ".message_inline_video",
        ".preview_content",
    ]) {
        $img.set_closest_results(sel, []);
    }

    // Default to overlay context.
    const $row = $.create(`<row-${n}>`);
    rows.get_closest_row = () => $row;
    rows.is_overlay_row = () => true;
    people.my_full_name = () => "Test User";

    return {$img, $parent, media: make_media_element($img, img_src)};
}

run_test("parse_media_data server-rendered image uses parent href", () => {
    const {media} = make_image({
        img_src: "https://example.com/thumbnail.jpg",
        parent_href: "https://example.com/original.jpg",
        parent_aria_label: "Image title",
    });
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "image");
    assert.equal(result.url, "https://example.com/original.jpg");
    assert.equal(result.source, "https://example.com/original.jpg");
    assert.equal(result.preview, "https://example.com/thumbnail.jpg");
    assert.equal(result.title, "Image title");
    assert.equal(result.user, "Test User");
});

run_test("parse_media_data bare image without parent link", () => {
    // Client-rendered images (e.g., in drafts) are bare <img> tags
    // not wrapped in an <a href>, so url falls back to img src.
    const {media} = make_image({
        img_src: "https://example.com/image.png",
        // No parent_href — simulates a bare <img>.
    });
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "image");
    assert.equal(result.url, "https://example.com/image.png");
    assert.equal(result.source, "https://example.com/image.png");
    assert.equal(result.preview, "https://example.com/image.png");
});

run_test("parse_media_data with data-src-fullsize", () => {
    // Remote images proxied through camo have a separate full-size URL.
    const camo_thumbnail = "https://example.com/camo/thumb?size=300x200";
    const camo_fullsize = "https://example.com/camo/full?size=0x0";
    const original_url = "https://remote.example.com/photo.jpg";

    const {media} = make_image({
        img_src: camo_thumbnail,
        parent_href: original_url,
        img_attrs: {"data-src-fullsize": camo_fullsize},
    });
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "image");
    // source uses the full-size camo URL for lightbox display.
    assert.equal(result.source, camo_fullsize);
    // preview uses the camo thumbnail for the carousel.
    assert.equal(result.preview, camo_thumbnail);
    // url uses the original for the download link.
    assert.equal(result.url, original_url);
});

run_test("parse_media_data with data-transcoded-image", () => {
    const {media} = make_image({
        img_src: "https://example.com/uploads/original.avif",
        parent_href: "https://example.com/uploads/original.avif",
        img_attrs: {"data-transcoded-image": "transcoded.webp"},
    });
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "image");
    // source replaces the filename with the transcoded version.
    assert.equal(result.source, "https://example.com/uploads/transcoded.webp");
    assert.equal(result.preview, "https://example.com/uploads/original.avif");
});

run_test("parse_media_data with original dimensions", () => {
    const {media} = make_image({
        img_src: "https://example.com/image.png",
        parent_href: "https://example.com/image.png",
        img_attrs: {"data-original-dimensions": "1920x1080"},
    });
    const result = lightbox.parse_media_data(media);

    assert.equal(result.original_width_px, 1920);
    assert.equal(result.original_height_px, 1080);
});

run_test("parse_media_data with loading placeholder", () => {
    const {$img, media} = make_image({
        img_src: "https://example.com/image.png",
        parent_href: "https://example.com/image.png",
    });
    $img[0].classList.add("image-loading-placeholder");
    const result = lightbox.parse_media_data(media);

    // Loading placeholders clear the preview.
    assert.equal(result.preview, "");
    assert.equal(result.source, "https://example.com/image.png");
});

run_test("parse_media_data inline video", () => {
    const {$img, media} = make_image({
        img_src: "https://example.com/camo/video-thumb",
        parent_href: "https://example.com/video.mp4",
    });
    // Override to indicate this is an inline video.
    $img.set_closest_results(".message_inline_video", $img);
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "inline-video");
    // source uses the non-camo'd href for direct playback.
    assert.equal(result.source, "https://example.com/video.mp4");
    assert.equal(result.preview, "https://example.com/camo/video-thumb");
});

run_test("parse_media_data YouTube video", () => {
    const {$img, $parent, media} = make_image({
        img_src: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        parent_href: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    });
    $img.set_closest_results(".youtube-video", $img);
    $parent.attr("data-id", "dQw4w9WgXcQ");
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "youtube-video");
    assert.equal(result.source, "https://www.youtube.com/embed/dQw4w9WgXcQ");
});

run_test("parse_media_data YouTube video with start time", () => {
    const {$img, $parent, media} = make_image({
        img_src: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        parent_href: "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120",
    });
    $img.set_closest_results(".youtube-video", $img);
    $parent.attr("data-id", "dQw4w9WgXcQ");
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "youtube-video");
    assert.equal(result.source, "https://www.youtube.com/embed/dQw4w9WgXcQ?start=120");
});

run_test("parse_media_data Vimeo video", () => {
    const {$img, $parent, media} = make_image({
        img_src: "https://i.vimeocdn.com/video/123456_640.jpg",
        parent_href: "https://vimeo.com/123456",
    });
    $img.set_closest_results(".vimeo-video", $img);
    $parent.attr("data-id", "123456");
    const result = lightbox.parse_media_data(media);

    assert.equal(result.type, "vimeo-video");
    assert.equal(result.source, "https://player.vimeo.com/video/123456");
});

run_test("parse_media_data message row context", () => {
    const {media} = make_image({
        img_src: "https://example.com/image.png",
        parent_href: "https://example.com/image.png",
    });

    // Override context to message row instead of overlay.
    rows.is_overlay_row = () => false;
    rows.id = () => 42;
    message_store.get = () => ({sender_full_name: "Alice"});

    const result = lightbox.parse_media_data(media);

    assert.equal(result.user, "Alice");
    assert.equal(result.type, "image");
});

run_test("parse_media_data unknown message", () => {
    const {media} = make_image({
        img_src: "https://example.com/image2.png",
        parent_href: "https://example.com/image2.png",
    });

    rows.is_overlay_row = () => false;
    rows.id = () => 999;
    message_store.get = () => undefined;

    blueslip.expect("error", "Lightbox for unknown message");
    const result = lightbox.parse_media_data(media);

    assert.equal(result.user, undefined);
});

run_test("parse_media_data asset map cache", () => {
    const img_src = "https://example.com/cached.png";

    message_store.get = () => ({sender_full_name: "Bob"});

    const {media: media1} = make_image({
        img_src,
        parent_href: img_src,
    });
    // make_image resets to overlay context; restore message row context.
    rows.is_overlay_row = () => false;
    rows.id = () => 100;

    const result1 = lightbox.parse_media_data(media1);
    assert.equal(result1.user, "Bob");

    // Second call with same message_id and canonical URL returns cache.
    const {media: media2} = make_image({
        img_src,
        parent_href: img_src,
    });
    rows.is_overlay_row = () => false;
    rows.id = () => 100;

    const result2 = lightbox.parse_media_data(media2);
    assert.equal(result2, result1);
});
