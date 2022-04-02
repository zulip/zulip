"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const markdown = zrequire("markdown");

const my_id = 101;

const user_map = new Map();
user_map.set(my_id, "Me Myself");
user_map.set(105, "greg");

function get_actual_name_from_user_id(user_id) {
    return user_map.get(user_id);
}

function get_user_id_from_name(name) {
    for (const [user_id, _name] of user_map.entries()) {
        if (name === _name) {
            return user_id;
        }
    }

    return undefined;
}

function is_valid_full_name_and_user_id(name, user_id) {
    return user_map.has(user_id) && user_map.get(user_id) === name;
}

function my_user_id() {
    return my_id;
}

function is_valid_user_id(user_id) {
    return user_map.has(user_id);
}

const staff_group = {
    id: 201,
    name: "Staff",
};

const user_group_map = new Map();
user_group_map.set(staff_group.name, staff_group);

function get_user_group_from_name(name) {
    return user_group_map.get(name);
}

function is_member_of_user_group(user_group_id, user_id) {
    assert.equal(user_group_id, staff_group.id);
    assert.equal(user_id, my_id);
    return true;
}

const social = {
    stream_id: 301,
    name: "social",
};

const sub_map = new Map();
sub_map.set(social.name, social);

function get_stream_by_name(name) {
    return sub_map.get(name);
}

function stream_hash(stream_id) {
    return `stream-${stream_id}`;
}

function stream_topic_hash(stream_id, topic) {
    return `stream-${stream_id}-topic-${topic}`;
}

const helper_config = {
    // user stuff
    get_actual_name_from_user_id,
    get_user_id_from_name,
    is_valid_full_name_and_user_id,
    is_valid_user_id,
    my_user_id,

    // user groups
    get_user_group_from_name,
    is_member_of_user_group,

    // stream hashes
    get_stream_by_name,
    stream_hash,
    stream_topic_hash,

    // settings
    should_translate_emoticons: () => false,
};

function assert_parse(raw_content, expected_content) {
    const {content} = markdown.parse({raw_content, helper_config});
    assert.equal(content, expected_content);
}

function test(label, f) {
    markdown.setup();
    run_test(label, f);
}

test("basics", () => {
    assert_parse("boring", "<p>boring</p>");
    assert_parse("**bold**", "<p><strong>bold</strong></p>");
});

test("user mentions", () => {
    assert_parse("@**greg**", '<p><span class="user-mention" data-user-id="105">@greg</span></p>');

    assert_parse("@**|105**", '<p><span class="user-mention" data-user-id="105">@greg</span></p>');

    assert_parse(
        "@**greg|105**",
        '<p><span class="user-mention" data-user-id="105">@greg</span></p>',
    );

    assert_parse(
        "@**Me Myself|101**",
        '<p><span class="user-mention" data-user-id="101">@Me Myself</span></p>',
    );
});

test("user group mentions", () => {
    assert_parse(
        "@*Staff*",
        '<p><span class="user-group-mention" data-user-group-id="201">@Staff</span></p>',
    );
});

test("stream links", () => {
    assert_parse(
        "#**social**",
        '<p><a class="stream" data-stream-id="301" href="/stream-301">#social</a></p>',
    );

    assert_parse(
        "#**social>lunch**",
        '<p><a class="stream-topic" data-stream-id="301" href="/stream-301-topic-lunch">#social &gt; lunch</a></p>',
    );
});
