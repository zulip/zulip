"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const message_edit = mock_esm("../src/message_edit");
const message_lists = mock_esm("../src/message_lists");
const message_notifications = mock_esm("../src/message_notifications");
const pm_list = mock_esm("../src/pm_list");
const stream_list = mock_esm("../src/stream_list");
const unread_ui = mock_esm("../src/unread_ui");
mock_esm("../src/message_parser", {
    message_has_attachment: noop,
    message_has_image: noop,
    message_has_link: noop,
});
message_lists.current = {};
message_lists.all_rendered_message_lists = () => [message_lists.current];

const people = zrequire("people");
const message_events = zrequire("message_events");
const message_helper = zrequire("message_helper");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const settings_config = zrequire("settings_config");
const stream_topic_history = zrequire("stream_topic_history");
const unread = zrequire("unread");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);

initialize_user_settings({user_settings: {}});

const alice = {
    email: "alice@example.com",
    user_id: 32,
    full_name: "Alice Patel",
};

people.add_active_user(alice);

const denmark = {
    subscribed: false,
    name: "Denmark",
    stream_id: 101,
};
stream_data.add_sub(denmark);

function test_helper(side_effects) {
    const events = [];

    for (const [module, field] of side_effects) {
        module[field] = () => {
            events.push([module, field]);
        };
    }

    const self = {};

    self.verify = () => {
        assert.deepEqual(side_effects, events);
    };

    return self;
}

run_test("update_messages", ({override, override_rewire}) => {
    override_rewire(message_events, "update_views_filtered_on_message_property", () => {});

    const raw_message = {
        id: 111,
        display_recipient: denmark.name,
        flags: ["mentioned"],
        sender_id: alice.user_id,
        stream_id: denmark.stream_id,
        topic: "lunch",
        type: "stream",
    };

    const original_message = message_helper.process_new_message(raw_message);

    assert.equal(original_message.mentioned, true);
    assert.equal(original_message.unread, true);

    assert.deepEqual(stream_topic_history.get_recent_topic_names(denmark.stream_id), ["lunch"]);

    unread.update_message_for_mention(original_message);
    assert.ok(unread.unread_mentions_counter.has(original_message.id));

    const events = [
        {
            message_id: original_message.id,
            flags: [],
            orig_content: "old stuff",
            content: "**new content**",
            rendered_content: "<b>new content</b>",
        },
    ];

    message_lists.current.view = {};

    let rendered_mgs;

    message_lists.current.view.rerender_messages = (msgs_to_rerender, message_content_edited) => {
        rendered_mgs = msgs_to_rerender;
        assert.equal(message_content_edited, true);
    };

    const side_effects = [
        [message_edit, "end_message_edit"],
        [message_notifications, "received_messages"],
        [unread_ui, "update_unread_counts"],
        [stream_list, "update_streams_sidebar"],
        [pm_list, "update_private_messages"],
    ];

    const helper = test_helper(side_effects);

    override(
        realm,
        "realm_message_edit_history_visibility_policy",
        settings_config.message_edit_history_visibility_policy_values.never.code,
    );

    const $message_edit_history_modal = $.create("#message-edit-history");
    const $modal = $.create("micromodal").addClass("modal--open");
    $message_edit_history_modal.set_parents_result(".micromodal", $modal);

    // TEST THIS:
    message_events.update_messages(events);

    assert.ok(!unread.unread_mentions_counter.has(original_message.id));

    helper.verify();

    assert.deepEqual(rendered_mgs, [
        {
            display_reply_to: undefined,
            alerted: false,
            clean_reactions: new Map(),
            collapsed: false,
            content: "<b>new content</b>",
            display_recipient: denmark.name,
            historical: false,
            id: 111,
            is_stream: true,
            is_private: false,
            last_edit_timestamp: undefined,
            mentioned: false,
            stream_wildcard_mentioned: false,
            topic_wildcard_mentioned: false,
            mentioned_me_directly: false,
            raw_content: "**new content**",
            reply_to: alice.email,
            sender_email: alice.email,
            sender_full_name: alice.full_name,
            sender_id: 32,
            sent_by_me: false,
            starred: false,
            status_emoji_info: undefined,
            stream_id: denmark.stream_id,
            stream: "Denmark",
            topic: "lunch",
            type: "stream",
            unread: true,
        },
    ]);
});
