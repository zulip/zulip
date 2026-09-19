"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

let appended_banners = [];
let closed_banners = [];

mock_esm("../src/banners", {
    append(banner, $container) {
        appended_banners.push({banner, container_selector: $container.selector});
    },
    close($banner) {
        closed_banners.push($banner.selector);
    },
});

mock_esm("../src/i18n", {
    $t({defaultMessage}) {
        return defaultMessage;
    },
});

const popup_banners = zrequire("popup_banners");

run_test("open_error_popup_banner", () => {
    appended_banners = [];
    closed_banners = [];

    popup_banners.open_error_popup_banner("<strong>Bad request</strong>", 1500);

    assert.equal(appended_banners.length, 1);
    assert.equal(appended_banners[0].container_selector, "#popup_banners_wrapper");

    const {banner} = appended_banners[0];
    assert.equal(banner.intent, "danger");
    assert.equal(banner.label.toString(), "<strong>Bad request</strong>");
    assert.deepEqual(banner.buttons, []);
    assert.equal(banner.close_button, true);
    assert.equal(banner.custom_classes, "global-error-popup-banner popup-banner");

    const $banner = $("#popup_banners_wrapper .global-error-popup-banner");
    assert.equal($banner.hasClass("fade-out"), false);

    clock.tick(1500);
    assert.equal($banner.hasClass("fade-out"), true);
    assert.deepEqual(closed_banners, []);

    clock.tick(300);
    assert.deepEqual(closed_banners, ["#popup_banners_wrapper .global-error-popup-banner"]);

    clock.reset();
});
