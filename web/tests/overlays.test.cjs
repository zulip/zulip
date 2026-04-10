"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

mock_esm("../src/mouse_drag", {
    is_drag: () => false,
});

mock_esm("../src/overlay_util", {
    disable_scrolling() {},
    enable_scrolling() {},
});

run_test("settings overlay does not close on backdrop click when select is open", () => {
    const overlays = zrequire("overlays");

    // Minimal DOM-ish setup required by overlays.open_overlay/close_overlay.
    $(".app");
    $("#navbar-fixed-container");

    const $settings_overlay = $("#settings_overlay_container");
    $settings_overlay.attr("data-overlay", "settings");
    $settings_overlay.set_matches("div.overlay", true);
    $settings_overlay.set_matches(".exit, .exit-sign, .overlay-content, .exit span", false);
    $settings_overlay.addClass("overlay");

    let overlay_closed = false;
    overlays.open_overlay({
        name: "settings",
        $overlay: $settings_overlay,
        on_close() {
            overlay_closed = true;
        },
    });
    assert.ok($settings_overlay.hasClass("show"));

    const $select = $.create("#test_select");
    $select.set_matches("select", true);
    $select.set_closest_results("#settings_overlay_container", [$settings_overlay[0]]);
    set_global("document", {
        activeElement: $select[0],
    });

    overlays.initialize();
    const handler = $("body").get_on_handler("click", "div.overlay, div.overlay .exit");
    handler({target: $settings_overlay[0]});

    assert.ok($settings_overlay.hasClass("show"));
    assert.equal(overlay_closed, false);

    overlays.close_overlay("settings");
    assert.equal(overlay_closed, true);
});

