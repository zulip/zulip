"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const navigator = {};
set_global("navigator", navigator);

const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

run_test("catch_up_view AI Summary mode renders page-level summary block", ({mock_template}) => {
    mock_template("catch_up_view/catch_up_view.hbs", true, (_data, html) => html);

    const html = require("../templates/catch_up_view/catch_up_view.hbs")({
        loading: false,
        has_no_data: false,
        catch_up_period_display: "1 day away",
        total_messages: 2,
        total_topics: 1,
        topics: [],
        streams: [{id: 1, name: "design"}],
        has_streams: true,
        has_ai_summary_entries: true,
        ai_summary_entries: [
            {
                sender_full_name: "aaron",
                rendered_content: "<p>Please review <strong>this</strong>.</p>",
            },
        ],
        is_all_filter: false,
        is_mentions_filter: false,
        is_important_filter: false,
        is_ai_summary_filter: true,
    });

    assert.match(html, /catch-up-ai-summary-block/);
    assert.match(html, /aaron:/);
    assert.match(html, /<strong>this<\/strong>/);
    assert.doesNotMatch(html, /catch-up-topics-container/);
    assert.doesNotMatch(html, /catch-up-stream-filter/);
});

run_test("catch_up_view standard mode renders topics container and stream filter", ({mock_template}) => {
    mock_template("catch_up_view/catch_up_view.hbs", true, (_data, html) => html);

    const html = require("../templates/catch_up_view/catch_up_view.hbs")({
        loading: false,
        has_no_data: false,
        catch_up_period_display: "1 day away",
        total_messages: 1,
        total_topics: 1,
        topics: [
            {
                stream_id: 1,
                stream_name: "design",
                topic_name: "export issue",
                score: 8,
                message_count: 1,
                sender_count: 1,
                senders: ["aaron"],
                has_mention: true,
                has_wildcard_mention: false,
                has_group_mention: false,
                reaction_count: 0,
                latest_message_id: 10,
                first_message_id: 10,
                sample_messages: [],
                data_has_mention: "true",
                data_has_wildcard: "false",
                data_is_dm: "false",
                stream_color: "#f08",
                topic_url: "#narrow/channel/1-design/topic/export%20issue",
                sender_list: "aaron",
                is_dm: false,
                has_reactions: false,
                has_key_messages: false,
                has_sample_messages: false,
                has_keywords: false,
            },
        ],
        streams: [{id: 1, name: "design"}],
        has_streams: true,
        has_ai_summary_entries: false,
        ai_summary_entries: [],
        is_all_filter: true,
        is_mentions_filter: false,
        is_important_filter: false,
        is_ai_summary_filter: false,
    });

    assert.match(html, /catch-up-topics-container/);
    assert.match(html, /catch-up-stream-filter/);
    assert.match(html, /catch-up-topic-card/);
    assert.match(html, /AI Summary/);
});

run_test("catch_up_topic_card omits AI Summary button and keyword chips", ({mock_template}) => {
    mock_template("catch_up_view/catch_up_topic_card.hbs", true, (_data, html) => html);

    const html = require("../templates/catch_up_view/catch_up_topic_card.hbs")({
        stream_id: 1,
        stream_name: "design",
        topic_name: "export issue",
        score: 8,
        message_count: 1,
        reaction_count: 0,
        data_has_mention: "true",
        data_has_wildcard: "false",
        data_is_dm: "false",
        stream_color: "#f08",
        topic_url: "#narrow/channel/1-design/topic/export%20issue",
        sender_list: "aaron",
        is_dm: false,
        has_mention: true,
        has_wildcard_mention: false,
        has_reactions: false,
        has_sample_messages: true,
        sample_messages: [
            {
                sender_full_name: "aaron",
                rendered_content: "<p>Please review <strong>this</strong>.</p>",
            },
        ],
        has_keywords: true,
        keywords: ["review", "export"],
    });

    assert.match(html, /Open topic/);
    assert.doesNotMatch(html, />AI Summary</);
    assert.doesNotMatch(html, /catch-up-keyword/);
    assert.doesNotMatch(html, /catch-up-summarize-btn/);
});

run_test("catch_up_topic_card renders preview with rendered markdown HTML", ({mock_template}) => {
    mock_template("catch_up_view/catch_up_topic_card.hbs", true, (_data, html) => html);

    const html = require("../templates/catch_up_view/catch_up_topic_card.hbs")({
        stream_id: 1,
        stream_name: "design",
        topic_name: "export issue",
        score: 8,
        message_count: 1,
        reaction_count: 0,
        data_has_mention: "false",
        data_has_wildcard: "false",
        data_is_dm: "false",
        stream_color: "#f08",
        topic_url: "#narrow/channel/1-design/topic/export%20issue",
        sender_list: "aaron",
        is_dm: false,
        has_mention: false,
        has_wildcard_mention: false,
        has_reactions: false,
        has_sample_messages: true,
        sample_messages: [
            {
                sender_full_name: "aaron",
                rendered_content: "<p>Please review <strong>this</strong>.</p>",
            },
        ],
        has_keywords: false,
    });

    assert.match(html, /catch-up-preview-message rendered_markdown/);
    assert.match(html, /<strong>this<\/strong>/);
    assert.doesNotMatch(html, /\*\*this\*\*/);
});
