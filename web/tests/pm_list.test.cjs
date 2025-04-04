"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const pm_list = zrequire("pm_list");

run_test("update_dom_with_unread_counts", () => {
    let counts;

    const $total_count = $.create("total-count-stub");
    const $private_li = $("#direct-messages-section-header");
    $private_li.set_find_results(".unread_count", $total_count);

    counts = {
        direct_message_count: 10,
    };

    pm_list.set_count(counts.direct_message_count);
    assert.equal($total_count.text(), "10");
    assert.equal($total_count.hasClass("hide"), false);

    counts = {
        direct_message_count: 0,
    };

    pm_list.set_count(counts.direct_message_count);
    assert.equal($total_count.text(), "");
    assert.equal($total_count.hasClass("hide"), true);
});
