"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

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

set_global("document", {hasFocus: () => true});

const channel = mock_esm("../src/channel");
const desktop_notifications = mock_esm("../src/desktop_notifications");
const message_lists = mock_esm("../src/message_lists");
const message_viewport = mock_esm("../src/message_viewport");
const unread_ui = mock_esm("../src/unread_ui");

message_lists.current = {view: {}};
message_lists.all_rendered_message_lists = () => [message_lists.current];

const message_store = zrequire("message_store");
const stream_data = zrequire("stream_data");
const unread = zrequire("unread");
const unread_ops = zrequire("unread_ops");

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

run_test("unread_ops", ({override}) => {
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

    // Make our test message appear to be unread, so that
    // we then need to subsequently process them as read.
    message_store.update_message_cache(test_messages[0]);
    unread.process_loaded_messages(test_messages);

    // Make our message_viewport appear visible.
    $("#message_feed_container").show();

    // Make our "test" message appear visible.
    override(message_viewport, "bottom_rendered_message_visible", () => true);

    // Set message_lists.current containing messages that can be marked read
    override(message_lists.current, "all_messages", () => test_messages);

    // Ignore these interactions for now:
    override(message_lists.current.view, "show_message_as_read", noop);
    override(desktop_notifications, "close_notification", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "notify_messages_remain_unread", noop);

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
    override(message_lists.current.view, "is_fetched_end_rendered", () => true);

    // First, test for a message list that cannot read messages.
    can_mark_messages_read = false;
    unread_ops.process_visible();

    assert.deepEqual(channel_post_opts, undefined);

    // Now flip the boolean, and get to the main thing we are testing.
    can_mark_messages_read = true;
    // Don't mark messages as read until all messages in the narrow are fetched and rendered.
    override(message_lists.current.view, "is_fetched_end_rendered", () => false);
    unread_ops.process_visible();
    assert.deepEqual(channel_post_opts, undefined);

    override(message_lists.current.view, "is_fetched_end_rendered", () => true);
    unread_ops.process_visible();

    // The most important side effect of the above call is that
    // we post info to the server.  We can verify that the correct
    // url and parameters are specified:
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {messages: "[50]", op: "add", flag: "read"},
        success: channel_post_opts.success,
    });

    // Simulate a successful post (which also clears the queue
    // in our message_flag code).
    channel_post_opts.success({messages: [message_id]});
});
