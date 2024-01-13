"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const pm_list = zrequire("pm_list");

run_test("update_dom_with_unread_counts", () => {
    let counts;

    const $total_count = $.create("total-count-stub");
    const $private_li = $(
        ".direct-messages-container #private_messages_section #private_messages_section_header",
    );
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
