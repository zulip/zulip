"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

set_global("Image", class Image {});
mock_esm("../../static/js/overlays", {
    close_overlay: () => {},

    close_active: () => {},
    open_overlay: () => {},
});
mock_esm("../../static/js/popovers", {
    hide_all: () => {},
});

const message_store = mock_esm("../../static/js/message_store");
const rows = zrequire("rows");

const lightbox = zrequire("lightbox");

function test(label, f) {
    run_test(label, ({override}) => {
        lightbox.clear_for_testing();
        f({override});
    });
}

test("pan_and_zoom", ({override}) => {
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

test("youtube", ({override}) => {
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
