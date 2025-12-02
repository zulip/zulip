"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

// Test that inbox row templates render with correct CSS classes
// for proper label overflow handling.

run_test("inbox_row_dm_has_overflow_classes", () => {
    const render_inbox_row = require("../templates/inbox_view/inbox_row.hbs");

    const dm_context = {
        is_stream: false,
        is_direct: true,
        is_topic: false,
        conversation_key: "test-dm-key",
        rendered_dm_with_html: "Very Long User Name That Should Be Truncated",
        is_group: false,
        user_circle_class: "user_circle_green",
        is_bot: false,
        dm_url: "#narrow/dm/1-user",
        user_ids_string: "1",
        unread_count: 5,
        is_hidden: false,
        is_collapsed: false,
        has_unread_mention: false,
        column_indexes: {
            FULL_ROW: 0,
            UNREAD_COUNT: 1,
            TOPIC_VISIBILITY: 2,
            ACTION_MENU: 3,
        },
    };

    const html = render_inbox_row(dm_context);

    // Verify the rendered HTML contains the necessary structural elements
    // that will receive the overflow-handling CSS styles
    assert.ok(html.includes('class="inbox-row'), "Should have inbox-row class");
    assert.ok(
        html.includes('class="inbox-left-part-wrapper"'),
        "Should have inbox-left-part-wrapper",
    );
    assert.ok(html.includes('class="inbox-left-part"'), "Should have inbox-left-part");
    assert.ok(html.includes('class="recipients_info'), "Should have recipients_info class");
    assert.ok(html.includes('class="user_block"'), "Should have user_block class");
    assert.ok(
        html.includes('class="recipients_name"'),
        "Should have recipients_name class for text truncation",
    );
});

run_test("inbox_stream_header_has_overflow_classes", () => {
    const render_inbox_row = require("../templates/inbox_view/inbox_row.hbs");

    const stream_context = {
        is_stream: true,
        stream_id: 1,
        stream_name: "Very Long Stream Name That Should Be Truncated With Ellipsis",
        stream_color: "#c2c2c2",
        stream_header_color: "#f0f0f0",
        invite_only: false,
        is_web_public: false,
        is_hidden: false,
        is_collapsed: false,
        is_muted: false,
        is_archived: false,
        mention_in_unread: false,
        unread_count: 10,
        column_indexes: {
            FULL_ROW: 0,
            UNREAD_COUNT: 1,
            TOPIC_VISIBILITY: 2,
            ACTION_MENU: 3,
        },
    };

    const html = render_inbox_row(stream_context);

    // Verify the rendered HTML contains the necessary structural elements
    // for stream header label overflow handling
    assert.ok(html.includes('class="inbox-header'), "Should have inbox-header class");
    assert.ok(html.includes('class="inbox-header-name"'), "Should have inbox-header-name class");
    assert.ok(
        html.includes('class="inbox-header-name-text"'),
        "Should have inbox-header-name-text class for ellipsis",
    );
});

run_test("inbox_topic_row_has_overflow_classes", () => {
    const render_inbox_row = require("../templates/inbox_view/inbox_row.hbs");

    const topic_context = {
        is_stream: false,
        is_direct: false,
        is_topic: true,
        stream_id: 1,
        stream_archived: false,
        topic_name: "Very Long Topic Name That Should Be Truncated With Ellipsis When Narrow",
        topic_display_name:
            "Very Long Topic Name That Should Be Truncated With Ellipsis When Narrow",
        is_empty_string_topic: false,
        conversation_key: "1:topic",
        topic_url: "#narrow/channel/1-stream/topic/topic",
        is_hidden: false,
        is_collapsed: false,
        mention_in_unread: false,
        unread_count: 3,
        all_visibility_policies: {
            INHERIT: 0,
            MUTED: 1,
            UNMUTED: 2,
            FOLLOWED: 3,
        },
        visibility_policy: 0,
        column_indexes: {
            FULL_ROW: 0,
            UNREAD_COUNT: 1,
            TOPIC_VISIBILITY: 2,
            ACTION_MENU: 3,
        },
    };

    const html = render_inbox_row(topic_context);

    // Verify the rendered HTML contains the necessary structural elements
    // for topic label overflow handling
    assert.ok(html.includes('class="inbox-row'), "Should have inbox-row class");
    assert.ok(
        html.includes('class="inbox-topic-name"'),
        "Should have inbox-topic-name class for ellipsis",
    );
});
