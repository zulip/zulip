"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// forward_message.build_forward_content needs only i18n (auto-stubbed by the
// test harness) and the real fenced_code module. Stub everything else the
// module imports so it loads without DOM / app initialization. The i18n stub
// prefixes translated strings with "translated: ", so we assert on the parts
// we interpolate ourselves rather than the whole attribution line.
mock_esm("../src/channel");
mock_esm("../src/dialog_widget");
mock_esm("../src/feedback_widget");
mock_esm("../src/hash_util");
mock_esm("../src/message_lists");
mock_esm("../src/people");
mock_esm("../src/pm_conversations");
mock_esm("../src/sent_messages");
mock_esm("../src/server_events_state");
mock_esm("../src/state_data", {current_user: {user_id: 1}});
mock_esm("../src/stream_data");
mock_esm("../src/transmit");
mock_esm("../src/ui_report");

const forward_message = zrequire("forward_message");

const sender = {sender_full_name: "Iago", sender_id: 5};

run_test("build_forward_content quotes the message with a silent mention", () => {
    const content = forward_message.build_forward_content(
        sender,
        "#narrow/channel/1-general/near/10",
        "hello world",
        "",
    );
    // Silent mention of the original sender, plus a link back to the source.
    assert.ok(content.includes("@_**Iago|5**"));
    assert.ok(content.includes("#narrow/channel/1-general/near/10"));
    // The body is wrapped in a quote fence.
    assert.ok(content.includes("```quote\nhello world\n```"));
    // With no comment there is no leading blank line.
    assert.ok(!content.startsWith("\n"));
});

run_test("build_forward_content prepends a trimmed comment", () => {
    const content = forward_message.build_forward_content(sender, "#link", "body", "  hi there  ");
    assert.ok(content.startsWith("hi there\n\n"));
    assert.ok(content.includes("```quote\nbody\n```"));
});

run_test("build_forward_content escapes the fence when content has backticks", () => {
    const raw = "```\ncode\n```";
    const content = forward_message.build_forward_content(sender, "#link", raw, "");
    // Fence must be longer than any backtick run inside the content.
    assert.ok(content.includes("````quote\n" + raw + "\n````"));
});

run_test("build_send_request builds a stream request", () => {
    const dest = {kind: "stream", key: "stream:7", stream_id: 7, name: "general", topic: "ideas"};
    const request = forward_message.build_send_request(dest, "body", "loc1", 1, "queue1");
    assert.deepEqual(request, {
        type: "stream",
        local_id: "loc1",
        sender_id: 1,
        queue_id: "queue1",
        to: "[7]",
        content: "body",
        topic: "ideas",
    });
});

run_test("build_send_request builds a direct message request", () => {
    const dest = {kind: "private", key: "dm:3,9", user_ids: [3, 9], label: "Cordelia, Othello"};
    const request = forward_message.build_send_request(dest, "body", "loc2", 1, "queue1");
    assert.deepEqual(request, {
        type: "private",
        local_id: "loc2",
        sender_id: 1,
        queue_id: "queue1",
        to: "[3,9]",
        content: "body",
    });
});
