"use strict";

const {strict: assert} = require("assert");

const {with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const hash_util = zrequire("hash_util");
const compose_state = zrequire("compose_state");
const narrow_banner = zrequire("narrow_banner");
const narrow_state = zrequire("narrow_state");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const {Filter} = zrequire("../js/filter");
const narrow = zrequire("narrow");

function set_filter(operators) {
    operators = operators.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    narrow_state.set_current_filter(new Filter(operators));
}

const me = {
    email: "me@example.com",
    user_id: 5,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@example.com",
    user_id: 23,
    full_name: "Alice Smith",
};

const ray = {
    email: "ray@example.com",
    user_id: 22,
    full_name: "Raymond",
};

function hide_all_empty_narrow_messages() {
    const all_empty_narrow_messages = [
        ".empty_feed_notice",
        "#empty_narrow_message",
        "#nonsubbed_private_nonexistent_stream_narrow_message",
        "#nonsubbed_stream_narrow_message",
        "#empty_star_narrow_message",
        "#empty_narrow_all_mentioned",
        "#empty_narrow_all_private_message",
        "#no_unread_narrow_message",
        "#non_existing_user",
        "#non_existing_users",
        "#empty_narrow_private_message",
        "#empty_narrow_self_private_message",
        "#empty_narrow_multi_private_message",
        "#empty_narrow_group_private_message",
        "#silent_user",
        "#empty_search_narrow_message",
        "#empty_narrow_resolved_topics",
    ];
    for (const selector of all_empty_narrow_messages) {
        $(selector).hide();
    }
}

run_test("uris", () => {
    people.add_active_user(ray);
    people.add_active_user(alice);
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);

    let uri = hash_util.pm_with_uri(ray.email);
    assert.equal(uri, "#narrow/pm-with/22-ray");

    uri = hash_util.huddle_with_uri("22,23");
    assert.equal(uri, "#narrow/pm-with/22,23-group");

    uri = hash_util.by_sender_uri(ray.email);
    assert.equal(uri, "#narrow/sender/22-ray");

    let emails = hash_util.decode_operand("pm-with", "22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("pm-with", "5,22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("pm-with", "5-group");
    assert.equal(emails, "me@example.com");
});

run_test("show_empty_narrow_message", () => {
    page_params.stop_words = [];

    narrow_state.reset_current_filter();
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.equal($(".empty_feed_notice").visible(), false);
    assert.ok($("#empty_narrow_message").visible());

    // for non-existent or private stream
    set_filter([["stream", "Foo"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#nonsubbed_private_nonexistent_stream_narrow_message").visible());

    // for non sub public stream
    stream_data.add_sub({name: "ROME", stream_id: 99});
    set_filter([["stream", "Rome"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#nonsubbed_stream_narrow_message").visible());

    set_filter([["is", "starred"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_star_narrow_message").visible());

    set_filter([["is", "mentioned"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_all_mentioned").visible());

    set_filter([["is", "private"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_all_private_message").visible());

    set_filter([["is", "unread"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#no_unread_narrow_message").visible());

    set_filter([["is", "resolved"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_resolved_topics").visible());

    set_filter([["pm-with", ["Yo"]]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#non_existing_user").visible());

    people.add_active_user(alice);
    set_filter([["pm-with", ["alice@example.com", "Yo"]]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#non_existing_users").visible());

    set_filter([["pm-with", "alice@example.com"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_private_message").visible());

    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    set_filter([["pm-with", me.email]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_self_private_message").visible());

    set_filter([["pm-with", me.email + "," + alice.email]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_multi_private_message").visible());

    set_filter([["group-pm-with", "alice@example.com"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_group_private_message").visible());

    set_filter([["sender", "ray@example.com"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#silent_user").visible());

    set_filter([["sender", "sinwar@example.com"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#non_existing_user").visible());

    const display = $("#empty_search_stop_words_string");

    const items = [];
    display.append = (html) => {
        items.push(html);
    };

    set_filter([["search", "grail"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());

    assert.equal(items.length, 2);
    assert.equal(items[0], " ");
    assert.equal(items[1].text(), "grail");

    set_filter([
        ["sender", "alice@example.com"],
        ["stream", "Rome"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_message").visible());

    set_filter([["is", "invalid"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_message").visible());

    const my_stream = {
        name: "my stream",
        stream_id: 103,
    };
    stream_data.add_sub(my_stream);
    stream_data.subscribe_myself(my_stream);

    set_filter([["stream", "my stream"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_narrow_message").visible());

    set_filter([["stream", ""]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#nonsubbed_private_nonexistent_stream_narrow_message").visible());
});

run_test("hide_empty_narrow_message", () => {
    $(".empty_feed_notice").show();
    narrow_banner.hide_empty_narrow_message();
    assert.ok(!$(".empty_feed_notice").visible());
});

run_test("show_search_stopwords", () => {
    page_params.stop_words = ["what", "about"];

    narrow_state.reset_current_filter();
    let items = [];

    const display = $("#empty_search_stop_words_string");

    display.append = (html) => {
        if (html.text) {
            items.push(html.selector + html.text());
        }
    };

    set_filter([["search", "what about grail"]]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());

    assert.equal(items.length, 3);
    assert.equal(items[0], "<del>what");
    assert.equal(items[1], "<del>about");
    assert.equal(items[2], "<span>grail");

    items = [];
    set_filter([
        ["stream", "streamA"],
        ["search", "what about grail"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());

    assert.equal(items.length, 4);
    assert.equal(items[0], "<span>stream: streamA");
    assert.equal(items[1], "<del>what");
    assert.equal(items[2], "<del>about");
    assert.equal(items[3], "<span>grail");

    items = [];
    set_filter([
        ["stream", "streamA"],
        ["topic", "topicA"],
        ["search", "what about grail"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());

    assert.equal(items.length, 4);
    assert.equal(items[0], "<span>stream: streamA topic: topicA");
    assert.equal(items[1], "<del>what");
    assert.equal(items[2], "<del>about");
    assert.equal(items[3], "<span>grail");
});

run_test("show_invalid_narrow_message", () => {
    narrow_state.reset_current_filter();
    const display = $("#empty_search_stop_words_string");

    stream_data.add_sub({name: "streamA", stream_id: 88});
    stream_data.add_sub({name: "streamB", stream_id: 77});

    set_filter([
        ["stream", "streamA"],
        ["stream", "streamB"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());
    assert.equal(
        display.text(),
        "translated: You are searching for messages that belong to more than one stream, which is not possible.",
    );

    set_filter([
        ["topic", "topicA"],
        ["topic", "topicB"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());
    assert.equal(
        display.text(),
        "translated: You are searching for messages that belong to more than one topic, which is not possible.",
    );

    people.add_active_user(ray);
    people.add_active_user(alice);

    set_filter([
        ["sender", "alice@example.com"],
        ["sender", "ray@example.com"],
    ]);
    hide_all_empty_narrow_messages();
    narrow_banner.show_empty_narrow_message();
    assert.ok($("#empty_search_narrow_message").visible());
    assert.equal(
        display.text(),
        "translated: You are searching for messages that are sent by more than one person, which is not possible.",
    );
});

run_test("narrow_to_compose_target errors", () => {
    function test() {
        with_field(
            narrow,
            "activate",
            () => {
                throw new Error("should not activate!");
            },
            () => {
                narrow.to_compose_target();
            },
        );
    }

    // No-op when not composing.
    compose_state.set_message_type(false);
    test();

    // No-op when empty stream.
    compose_state.set_message_type("stream");
    compose_state.stream_name("");
    test();
});

run_test("narrow_to_compose_target streams", ({override}) => {
    const args = {called: false};
    override(narrow, "activate", (operators, opts) => {
        args.operators = operators;
        args.opts = opts;
        args.called = true;
    });

    compose_state.set_message_type("stream");
    stream_data.add_sub({name: "ROME", stream_id: 99});
    compose_state.stream_name("ROME");

    // Test with existing topic
    compose_state.topic("one");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.equal(args.opts.trigger, "narrow_to_compose_target");
    assert.deepEqual(args.operators, [
        {operator: "stream", operand: "ROME"},
        {operator: "topic", operand: "one"},
    ]);

    // Test with new topic
    compose_state.topic("four");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: "stream", operand: "ROME"},
        {operator: "topic", operand: "four"},
    ]);

    // Test with blank topic
    compose_state.topic("");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "stream", operand: "ROME"}]);

    // Test with no topic
    compose_state.topic(undefined);
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "stream", operand: "ROME"}]);
});

run_test("narrow_to_compose_target PMs", ({override}) => {
    const args = {called: false};
    override(narrow, "activate", (operators, opts) => {
        args.operators = operators;
        args.opts = opts;
        args.called = true;
    });

    let emails;
    override(compose_state, "private_message_recipient", () => emails);

    compose_state.set_message_type("private");
    people.add_active_user(ray);
    people.add_active_user(alice);
    people.add_active_user(me);

    // Test with valid person
    emails = "alice@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "pm-with", operand: "alice@example.com"}]);

    // Test with valid persons
    emails = "alice@example.com,ray@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: "pm-with", operand: "alice@example.com,ray@example.com"},
    ]);

    // Test with some invalid persons
    emails = "alice@example.com,random,ray@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "is", operand: "private"}]);

    // Test with all invalid persons
    emails = "alice,random,ray";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "is", operand: "private"}]);

    // Test with no persons
    emails = "";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [{operator: "is", operand: "private"}]);
});
