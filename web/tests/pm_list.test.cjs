"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

run_test("update_dom_with_unread_counts", () => {
    const pm_list = zrequire("pm_list");
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

run_test("build_direct_messages_list", ({override}) => {
    const pm_list_data = mock_esm("../src/pm_list_data");
    const pm_list_dom = mock_esm("../src/pm_list_dom");
    const pm_list = zrequire("pm_list");

    const conversations_to_be_shown = [
        {
            recipients: "Alice",
            user_ids_string: "101",
            unread: 0,
            is_zero: true,
            is_active: false,
            is_deactivated: false,
            is_current_user: false,
            url: "#narrow/dm/101-Alice",
            status_emoji_info: {emoji_code: "20"},
            user_circle_class: "user-circle-offline",
            is_group: false,
            is_bot: false,
            has_unread_mention: false,
        },
    ];

    const pm_list_info = {
        conversations_to_be_shown,
        more_conversations_unread_count: 0,
    };

    override(pm_list_data, "get_list_info", () => pm_list_info);

    const expected_pm_li = {
        type: "li",
        key: "101",
    };
    const more_li = {
        type: "li",
        key: "more_private_conversations",
    };

    override(pm_list_dom, "keyed_pm_li", () => expected_pm_li);
    override(pm_list_dom, "more_private_conversations_li", () => more_li);
    override(pm_list_dom, "pm_ul", (children) => ({
        type: "ul",
        children,
    }));

    // When all conversations are shown, we don't show the "More conversations" li.
    let dom_ast = pm_list._build_direct_messages_list({
        all_conversations_shown: true,
        conversations_to_be_shown,
        search_term: "",
    });

    assert.deepEqual(dom_ast.children.length, 1);
    assert.deepEqual(dom_ast.children[0], expected_pm_li);

    // Test that "More conversations" is shown when not all conversations are visible.
    dom_ast = pm_list._build_direct_messages_list({
        all_conversations_shown: false,
        conversations_to_be_shown,
        search_term: "",
    });
    assert.deepEqual(dom_ast.children.length, 2);
    assert.deepEqual(dom_ast.children[0], expected_pm_li);
    assert.deepEqual(dom_ast.children[1], more_li);
});
