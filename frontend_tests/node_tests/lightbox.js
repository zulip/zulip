"use strict";

const {strict: assert} = require("assert");

const {rewiremock, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

set_global("Image", class Image {});
rewiremock("../../static/js/overlays").with({
    close_overlay: () => {},

    close_active: () => {},
    open_overlay: () => {},
});
rewiremock("../../static/js/popovers").with({
    hide_all: () => {},
});

const message_store = rewiremock("../../static/js/message_store").with({});
const rows = zrequire("rows");

const lightbox = zrequire("lightbox");

rows.__Rewire__("is_draft_row", () => false);

run_test("pan_and_zoom", (override) => {
    const img = $.create("img-stub");
    const link = $.create("link-stub");
    const msg = $.create("msg-stub");

    $(img).closest = () => [];

    img.set_parent(link);
    link.closest = () => msg;

    override(rows, "id", (row) => {
        assert.equal(row, msg);
        return 1234;
    });

    img.attr("src", "example");

    let fetched_zid;

    message_store.get = (zid) => {
        fetched_zid = zid;
        return "message-stub";
    };

    override(lightbox, "render_lightbox_list_images", () => {});

    lightbox.open(img);

    assert.equal(fetched_zid, 1234);
});

run_test("youtube", (override) => {
    const href = "https://youtube.com/some-random-clip";
    const img = $.create("img-stub");
    const link = $.create("link-stub");
    const msg = $.create("msg-stub");

    override(rows, "id", (row) => {
        assert.equal(row, msg);
        return 4321;
    });

    $(img).attr("src", href);

    $(img).closest = (sel) => {
        if (sel === ".youtube-video") {
            // We just need a nonempty array to
            // set is_youtube_video to true.
            return ["whatever"];
        }
        return [];
    };

    img.set_parent(link);
    link.closest = () => msg;
    link.attr("href", href);

    override(lightbox, "render_lightbox_list_images", () => {});

    lightbox.open(img);
    assert.equal($(".image-actions .open").attr("href"), href);
});
