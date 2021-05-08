"use strict";

const {strict: assert} = require("assert");

const {stub_templates} = require("../zjsunit/handlebars");
const {mock_cjs, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const compose = mock_esm("../../static/js/compose");

const ls_container = new Map();
const noop = () => {};

const localStorage = set_global("localStorage", {
    getItem(key) {
        return ls_container.get(key);
    },
    setItem(key, val) {
        ls_container.set(key, val);
    },
    removeItem(key) {
        ls_container.delete(key);
    },
    clear() {
        ls_container.clear();
    },
});
mock_cjs("jquery", $);

const compose_actions = zrequire("compose_actions");
const compose_state = zrequire("compose_state");
const {localstorage} = zrequire("localstorage");
const unsent_messages = zrequire("unsent_messages");

const KEY = "unsent_messages";

const unsent_message_1 = {
    type: "stream",
    content: "An important meeting at 5 P.M.",
    stream: "Denmark",
    topic: "New topic",
    createdAt: 1,
};

const unsent_message_2 = {
    type: "private",
    content: "foo **bar**",
    reply_to: "aaron@zulip.com",
    private_message_recipient: "aaron@zulip.com",
    createdAt: 2,
};

const unsent_message_3 = {
    type: "stream",
    content: "Let's take a lunch break",
    stream: "Rome",
    topic: "bar",
    createdAt: 3,
};

const unsent_message_4 = {
    type: "private",
    content: "We need to discuss about the project",
    reply_to: "aaron@zulip.com",
    private_message_recipient: "aaron@zulip.com",
    createdAt: 4,
};

function setup_parents_and_mock_remove(container_sel, target_sel, parent) {
    const container = $.create("fake " + container_sel);
    let container_removed = false;

    container.remove = () => {
        container_removed = true;
    };

    const target = $.create("fake click target (" + target_sel + ")");

    target.set_parents_result(parent, container);

    const event = {
        preventDefault: noop,
        target,
    };

    const helper = {
        event,
        container,
        target,
        container_was_removed: () => container_removed,
    };

    return helper;
}

run_test("store_and_get_unsent_messages", (override) => {
    const ls = localstorage();
    assert.equal(ls.get(KEY), undefined);

    let curr_unsent_msg;
    function map(field, f) {
        override(compose_state, field, f);
    }

    map("get_message_type", () => curr_unsent_msg.type);
    map("stream_name", () => curr_unsent_msg.stream);
    map("topic", () => curr_unsent_msg.topic);
    map("private_message_recipient", () => curr_unsent_msg.private_message_recipient);

    const expected = [];
    function assert_unsent_messages() {
        expected.push(curr_unsent_msg);
        override(Date, "now", () => curr_unsent_msg.createdAt);
        unsent_messages.store_unsent_message(curr_unsent_msg.content);
        assert.deepEqual(unsent_messages.get_unsent_messages(), expected);
    }

    curr_unsent_msg = unsent_message_1;
    assert_unsent_messages();

    curr_unsent_msg = unsent_message_3;
    assert_unsent_messages();

    curr_unsent_msg = unsent_message_2;
    assert_unsent_messages();
});

run_test("initialize_and_send_unsent_messages", (override) => {
    // Unsent messages stored in the previous test will be used here.
    const ls = localstorage();
    const unsent_msg = unsent_messages.unsent_messages;

    stub_templates((template_name) => {
        assert.equal(template_name, "compose_unsent_message");
        return "compose_unsent_message_stub";
    });

    $("#compose-unsent-message").append = (data) => {
        assert.equal(data, "compose_unsent_message_stub");
    };

    let actual_msg_type;
    let actual_opts;
    override(compose_actions, "start", (msg_type, opts) => {
        actual_msg_type = msg_type;
        actual_opts = opts;
    });

    let compose_finish_called = false;
    compose.finish = () => {
        compose_finish_called = true;
    };

    let clear_compose_box_called = false;
    compose.clear_compose_box = () => {
        clear_compose_box_called = true;
    };

    unsent_messages.initialize();

    const confirm_handler = $("#compose-unsent-message").get_on_handler(
        "click",
        ".compose-unsent-message-confirm",
    );

    const cancel_handler = $("#compose-unsent-message").get_on_handler(
        "click",
        ".compose-unsent-message-cancel",
    );

    const helper = setup_parents_and_mock_remove(
        "compose-unsent-message",
        "compose-unsent-message",
        ".compose-unsent-message",
    );

    // At this point we must remove all the unsent messages from the
    // localStorage and stage them to be acknowledged by the user.
    assert.deepEqual(ls.get(KEY), []);

    // We should send these unsent messages in the order they were created at.
    assert.equal(actual_msg_type, unsent_message_1.type);
    assert.deepEqual(actual_opts, {
        stream: "Denmark",
        topic: "New topic",
        private_message_recipient: "",
        content: "An important meeting at 5 P.M.",
    });
    assert($("#compose-unsent-message").is(":visible"));
    assert($("#compose-send-button").prop("disabled"));

    confirm_handler(helper.event);
    assert(compose_finish_called);
    compose_finish_called = false; // Reset
    assert(!unsent_msg.is_empty());
    assert(!helper.container_was_removed());

    assert.equal(actual_msg_type, unsent_message_2.type);
    assert.deepEqual(actual_opts, {
        stream: "",
        topic: "",
        content: "foo **bar**",
        private_message_recipient: "aaron@zulip.com",
    });

    cancel_handler(helper.event);
    assert(!compose_finish_called);
    assert(clear_compose_box_called);

    assert.equal(actual_msg_type, unsent_message_3.type);
    assert.deepEqual(actual_opts, {
        stream: "Rome",
        topic: "bar",
        content: "Let's take a lunch break",
        private_message_recipient: "",
    });

    confirm_handler(helper.event);
    assert(compose_finish_called);
    assert(unsent_msg.is_empty());
    assert(helper.container_was_removed());
    assert(!$("#compose-unsent-message").is(":visible"));
    assert(!$("#compose-send-status").is(":visible"));
    assert(!$("#compose-send-button").prop("disabled"));
});

run_test("initialize_and_send_no_unsent_message", (override) => {
    // This specific test is added to cover a necessary area (Node coverage).
    override(compose_state, "construct_message_data", () => unsent_message_4);
    unsent_messages.store_unsent_message();

    const ls = localstorage();
    const unsent_msg = unsent_messages.unsent_messages;

    stub_templates((template_name) => {
        assert.equal(template_name, "compose_unsent_message");
        return "compose_unsent_message_stub";
    });

    $("#compose-unsent-message").append = (data) => {
        assert.equal(data, "compose_unsent_message_stub");
    };

    let actual_msg_type;
    let actual_opts;
    override(compose_actions, "start", (msg_type, opts) => {
        actual_msg_type = msg_type;
        actual_opts = opts;
    });

    unsent_messages.initialize();
    assert.deepEqual(ls.get(KEY), []);

    const cancel_handler = $("#compose-unsent-message").get_on_handler(
        "click",
        ".compose-unsent-message-cancel",
    );

    const helper = setup_parents_and_mock_remove(
        "compose-unsent-message",
        "compose-unsent-message",
        ".compose-unsent-message",
    );

    assert.equal(actual_msg_type, unsent_message_4.type);
    assert.deepEqual(actual_opts, {
        stream: "",
        topic: "",
        content: "We need to discuss about the project",
        private_message_recipient: "aaron@zulip.com",
    });

    cancel_handler(helper.event);
    assert(unsent_msg.is_empty());
    assert(helper.container_was_removed());
    assert(!$("#compose-unsent-message").is(":visible"));
    assert(!$("#compose-send-status").is(":visible"));
    assert(!$("#compose-send-button").prop("disabled"));
});

run_test("initialize_no_unsent_message_available", () => {
    const ls = localstorage();
    localStorage.clear();
    assert.equal(ls.get(KEY), undefined);

    unsent_messages.initialize();
    assert.deepEqual(ls.get(KEY), []);

    const unsent_msg = unsent_messages.unsent_messages;
    assert(unsent_msg.is_empty());
    assert(!$("#compose-unsent-message").is(":visible"));
    assert(!$("#compose-send-button").prop("disabled"));
});
