"use strict";

const {strict: assert} = require("assert");

const MockDate = require("mockdate");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const {page_params} = require("../zjsunit/zpage_params");

const markdown = mock_esm("../../static/js/markdown");
const message_lists = mock_esm("../../static/js/message_lists");
const notifications = mock_esm("../../static/js/notifications");

let disparities = [];

mock_esm("../../static/js/ui", {
    show_failed_message_success: () => {},
});

mock_esm("../../static/js/sent_messages", {
    mark_disparity: (local_id) => {
        disparities.push(local_id);
    },
});

const message_store = mock_esm("../../static/js/message_store", {
    get: () => ({failed_request: true}),

    update_booleans: () => {},

    set_message_booleans: () => {},
});

mock_esm("../../static/js/message_list");
message_lists.current = "";
message_lists.home = {view: {}};

const drafts = zrequire("drafts");
const echo = zrequire("echo");
const people = zrequire("people");

run_test("process_from_server for un-echoed messages", () => {
    const waiting_for_ack = new Map();
    const server_messages = [
        {
            local_id: "100.1",
        },
    ];
    echo._patch_waiting_for_ack(waiting_for_ack);
    const non_echo_messages = echo.process_from_server(server_messages);
    assert.deepEqual(non_echo_messages, server_messages);
});

run_test("process_from_server for differently rendered messages", ({override}) => {
    let messages_to_rerender = [];

    override(message_lists.home.view, "rerender_messages", (msgs) => {
        messages_to_rerender = msgs;
    });

    // Test that we update all the booleans and the content of the message
    // in local echo.
    const old_value = "old_value";
    const new_value = "new_value";
    const waiting_for_ack = new Map([
        [
            "100.1",
            {
                content: "<p>A client rendered message</p>",
                timestamp: old_value,
                is_me_message: old_value,
                submessages: old_value,
                topic_links: old_value,
            },
        ],
    ]);
    const server_messages = [
        {
            local_id: "100.1",
            content: "<p>A server rendered message</p>",
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ];
    echo._patch_waiting_for_ack(waiting_for_ack);
    disparities = [];
    const non_echo_messages = echo.process_from_server(server_messages);
    assert.deepEqual(non_echo_messages, []);
    assert.equal(disparities.length, 1);
    assert.deepEqual(messages_to_rerender, [
        {
            content: server_messages[0].content,
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ]);
});

run_test("build_display_recipient", () => {
    page_params.user_id = 123;

    const params = {};
    params.realm_users = [
        {
            user_id: 123,
            full_name: "Iago",
            email: "iago@zulip.com",
        },
        {
            email: "cordelia@zulip.com",
            full_name: "Cordelia",
            user_id: 21,
        },
    ];
    params.realm_non_active_users = [];
    params.cross_realm_bots = [];
    people.initialize(page_params.user_id, params);

    let message = {
        type: "stream",
        stream: "general",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    let display_recipient = echo.build_display_recipient(message);
    assert.equal(display_recipient, "general");

    message = {
        type: "private",
        private_message_recipient: "cordelia@zulip.com,hamlet@zulip.com",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    display_recipient = echo.build_display_recipient(message);
    assert.equal(display_recipient.length, 3);

    let iago = display_recipient.find((recipient) => recipient.email === "iago@zulip.com");
    assert.equal(iago.full_name, "Iago");
    assert.equal(iago.id, 123);

    const cordelia = display_recipient.find(
        (recipient) => recipient.email === "cordelia@zulip.com",
    );
    assert.equal(cordelia.full_name, "Cordelia");
    assert.equal(cordelia.id, 21);

    const hamlet = display_recipient.find((recipient) => recipient.email === "hamlet@zulip.com");
    assert.equal(hamlet.full_name, "hamlet@zulip.com");
    assert.equal(hamlet.id, undefined);
    assert.equal(hamlet.unknown_local_echo_user, true);

    message = {
        type: "private",
        private_message_recipient: "iago@zulip.com",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    display_recipient = echo.build_display_recipient(message);

    assert.equal(display_recipient.length, 1);
    iago = display_recipient.find((recipient) => recipient.email === "iago@zulip.com");
    assert.equal(iago.full_name, "Iago");
    assert.equal(iago.id, 123);
});

run_test("update_message_lists", () => {
    message_lists.home.view = {};

    const stub = make_stub();
    const view_stub = make_stub();

    message_lists.home.change_message_id = stub.f;
    message_lists.home.view.change_message_id = view_stub.f;

    echo.update_message_lists({old_id: 401, new_id: 402});

    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("old", "new");
    assert.equal(args.old, 401);
    assert.equal(args.new, 402);

    assert.equal(view_stub.num_calls, 1);
    const view_args = view_stub.get_args("old", "new");
    assert.equal(view_args.old, 401);
    assert.equal(view_args.new, 402);
});

run_test("insert_local_message streams", ({override, override_rewire}) => {
    const fake_now = 555;
    MockDate.set(new Date(fake_now * 1000));

    const local_id_float = 101.01;

    let apply_markdown_called = false;
    let add_topic_links_called = false;
    let insert_message_called = false;

    override(markdown, "apply_markdown", () => {
        apply_markdown_called = true;
    });

    override(markdown, "add_topic_links", () => {
        add_topic_links_called = true;
    });

    override_rewire(echo, "insert_message", (message) => {
        assert.equal(message.display_recipient, "general");
        assert.equal(message.timestamp, fake_now);
        assert.equal(message.sender_email, "iago@zulip.com");
        assert.equal(message.sender_full_name, "Iago");
        assert.equal(message.sender_id, 123);
        insert_message_called = true;
    });

    const message_request = {
        type: "stream",
        stream: "general",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float);

    assert.ok(apply_markdown_called);
    assert.ok(add_topic_links_called);
    assert.ok(insert_message_called);
});

run_test("insert_local_message PM", ({override, override_rewire}) => {
    const local_id_float = 102.01;

    page_params.user_id = 123;

    const params = {};
    params.realm_users = [
        {
            user_id: 123,
            full_name: "Iago",
            email: "iago@zulip.com",
        },
    ];
    params.realm_non_active_users = [];
    params.cross_realm_bots = [];
    people.initialize(page_params.user_id, params);

    let add_topic_links_called = false;
    let apply_markdown_called = false;
    let insert_message_called = false;

    override_rewire(echo, "insert_message", (message) => {
        assert.equal(message.display_recipient.length, 3);
        insert_message_called = true;
    });

    override(markdown, "apply_markdown", () => {
        apply_markdown_called = true;
    });

    override(markdown, "add_topic_links", () => {
        add_topic_links_called = true;
    });

    const message_request = {
        private_message_recipient: "cordelia@zulip.com,hamlet@zulip.com",
        type: "private",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float);
    assert.ok(add_topic_links_called);
    assert.ok(apply_markdown_called);
    assert.ok(insert_message_called);
});

run_test("test reify_message_id", ({override, override_rewire}) => {
    const local_id_float = 103.01;

    override(markdown, "apply_markdown", () => {});
    override(markdown, "add_topic_links", () => {});
    override_rewire(echo, "insert_message", () => {});

    const message_request = {
        type: "stream",
        stream: "general",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
        draft_id: 100,
    };
    echo.insert_local_message(message_request, local_id_float);

    let message_store_reify_called = false;
    let notifications_reify_called = false;
    let draft_deleted = false;

    override(message_store, "reify_message_id", () => {
        message_store_reify_called = true;
    });

    override(notifications, "reify_message_id", () => {
        notifications_reify_called = true;
    });

    const draft_model = drafts.draft_model;
    override(draft_model, "deleteDraft", (draft_id) => {
        assert.ok(draft_id, 100);
        draft_deleted = true;
    });

    echo.reify_message_id(local_id_float.toString(), 110);

    assert.ok(message_store_reify_called);
    assert.ok(notifications_reify_called);
    assert.ok(draft_deleted);
});

MockDate.reset();
