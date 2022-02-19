"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

/*

   Let's continue to explore how we can test complex
   interactions in the real code.

   When a new message comes in, we update the three major
   panes of the app:

        * left sidebar - stream list
        * middle pane - message view
        * right sidebar - buddy list (aka "activity" list)

    These are reflected by the following calls:

        stream_list.update_streams_sidebar
        message_util.add_new_messages
        activity.process_loaded_messages

    For now, though, let's focus on another side effect
    of processing incoming messages:

        unread_ops.process_visible

    When new messages come in, they are often immediately
    visible to users, so the app will communicate this
    back to the server by calling unread_ops.process_visible.

    In order to unit test this, we don't want to require
    an actual server to be running.  Instead, this example
    will stub many of the "boundaries" to focus on the
    core behavior.

    The two key pieces here are as follows:

        * Use mock_esm to avoid compiling the "real"
          modules that are immaterial to our current
          testing concerns.

        * Use override(...) to simulate how we want
          methods to behave. (Often we want them to
          do nothing at all or return a simple
          value.)
*/

const channel = mock_esm("../../static/js/channel");
const message_list = mock_esm("../../static/js/message_list");
const message_lists = mock_esm("../../static/js/message_lists");
const message_viewport = mock_esm("../../static/js/message_viewport");
const notifications = mock_esm("../../static/js/notifications");
const unread_ui = mock_esm("../../static/js/unread_ui");

message_lists.current = {};
message_lists.home = {};

const message_store = zrequire("message_store");
const recent_topics_util = zrequire("recent_topics_util");
const stream_data = zrequire("stream_data");
const unread = zrequire("unread");
const unread_ops = zrequire("unread_ops");

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

run_test("unread_ops", ({override, override_rewire}) => {
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const message_id = 50;
    const test_messages = [
        {
            id: message_id,
            type: "stream",
            stream_id: denmark_stream.stream_id,
            topic: "copenhagen",
            unread: true,
        },
    ];

    // We don't want recent topics to process message for this test.
    override_rewire(recent_topics_util, "is_visible", () => false);
    // Show message_viewport as not visible so that messages will be stored as unread.
    override(message_viewport, "is_visible_and_focused", () => false);

    // Make our test message appear to be unread, so that
    // we then need to subsequently process them as read.
    unread.process_loaded_messages(test_messages);

    // Make our message_viewport appear visible.
    override(message_viewport, "is_visible_and_focused", () => true);

    // Make our "test" message appear visible.
    override(message_viewport, "bottom_message_visible", () => true);

    // Make us not be in a narrow (somewhat hackily).
    message_list.narrowed = undefined;

    // Set message_lists.current containing messages that can be marked read
    override(message_lists.current, "all_messages", () => test_messages);

    // Ignore these interactions for now:
    override(message_lists.home, "show_message_as_read", () => {});
    override(notifications, "close_notification", () => {});
    override(unread_ui, "update_unread_counts", () => {});
    override(unread_ui, "notify_messages_remain_unread", () => {});

    // Set up a way to capture the options passed in to channel.post.
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    let can_mark_messages_read;

    // Set up an override to point to the above var, so we can
    // toggle it easily from within the test (and avoid complicated
    // data setup).
    override(message_lists.current, "can_mark_messages_read", () => can_mark_messages_read);
    override(message_lists.current, "has_unread_messages", () => true);

    // First, test for a message list that cannot read messages.
    can_mark_messages_read = false;
    unread_ops.process_visible();

    assert.deepEqual(channel_post_opts, undefined);

    // Now flip the boolean, and get to the main thing we are testing.
    can_mark_messages_read = true;
    unread_ops.process_visible();

    // The most important side effect of the above call is that
    // we post info to the server.  We can verify that the correct
    // url and parameters are specified:
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        idempotent: true,
        data: {messages: "[50]", op: "add", flag: "read"},
        success: channel_post_opts.success,
    });

    // Simulate a successful post (which also clears the queue
    // in our message_flag code).
    channel_post_opts.success({messages: [message_id]});
});
