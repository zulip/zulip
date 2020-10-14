"use strict";

set_global("$", global.make_zjquery());
set_global("markdown", {});
set_global("local_message", {
    now: () => "timestamp",
});
set_global("page_params", {});

zrequire("echo");
const people = zrequire("people");

let disparities = [];
let messages_to_rerender = [];

set_global("ui", {
    show_failed_message_success: () => {},
});

set_global("sent_messages", {
    mark_disparity: (local_id) => {
        disparities.push(local_id);
    },
});

set_global("message_store", {
    get: () => ({failed_request: true}),
    update_booleans: () => {},
});

set_global("alert_words", {
    process_message: () => {},
});

set_global("home_msg_list", {
    view: {
        rerender_messages: (msgs) => {
            messages_to_rerender = msgs;
        },
    },
});

set_global("message_list", {});

set_global("current_msg_list", "");

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

run_test("process_from_server for differently rendered messages", () => {
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
    messages_to_rerender = [];
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

run_test("insert_local_message", () => {
    const local_id_float = 1;

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

    let apply_markdown_called = false;
    let add_topic_links_called = false;
    let insert_message_called = false;

    markdown.apply_markdown = () => {
        apply_markdown_called = true;
    };

    markdown.add_topic_links = () => {
        add_topic_links_called = true;
    };

    local_message.insert_message = (message) => {
        assert.equal(message.display_recipient, "general");
        assert.equal(message.timestamp, "timestamp");
        assert.equal(message.sender_email, "iago@zulip.com");
        assert.equal(message.sender_full_name, "Iago");
        assert.equal(message.sender_id, 123);
        insert_message_called = true;
    };

    let message_request = {
        type: "stream",
        stream: "general",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float);

    assert(apply_markdown_called);
    assert(add_topic_links_called);
    assert(insert_message_called);

    add_topic_links_called = false;
    apply_markdown_called = false;
    insert_message_called = false;

    local_message.insert_message = (message) => {
        assert.equal(message.display_recipient.length, 3);
        insert_message_called = true;
    };

    message_request = {
        private_message_recipient: "cordelia@zulip.com,hamlet@zulip.com",
        type: "private",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float);
    assert(add_topic_links_called);
    assert(apply_markdown_called);
    assert(insert_message_called);
});
