"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_pill = zrequire("stream_pill");

const current_user = {};
set_current_user(current_user);
set_realm({});

const denmark = {
    stream_id: 101,
    name: "Denmark",
    subscribed: true,
};
const sweden = {
    stream_id: 102,
    name: "Sweden",
    subscribed: false,
};
const germany = {
    stream_id: 103,
    name: "Germany",
    subscribed: false,
    invite_only: true,
};

peer_data.set_subscribers(denmark.stream_id, [1, 2, 77]);
peer_data.set_subscribers(sweden.stream_id, [1, 2, 3, 4, 5]);

const denmark_pill = {
    type: "stream",
    stream_id: denmark.stream_id,
    show_subscriber_count: true,
};
const sweden_pill = {
    type: "stream",
    stream_id: sweden.stream_id,
    show_subscriber_count: true,
};

const subs = [denmark, sweden, germany];
for (const sub of subs) {
    stream_data.add_sub(sub);
}

const me = {
    email: "me@example.com",
    user_id: 5,
    full_name: "Me Myself",
};

people.add_active_user(me);
people.initialize_current_user(me.user_id);

run_test("create_item", ({override}) => {
    override(current_user, "user_id", me.user_id);
    override(current_user, "is_admin", true);
    function test_create_item(
        stream_name,
        current_items,
        expected_item,
        stream_prefix_required = true,
        get_allowed_streams = stream_data.get_unsorted_subs,
    ) {
        const item = stream_pill.create_item_from_stream_name(
            stream_name,
            current_items,
            stream_prefix_required,
            get_allowed_streams,
        );
        assert.deepEqual(item, expected_item);
    }

    test_create_item("sweden", [], undefined);
    test_create_item("#sweden", [sweden_pill], undefined);
    test_create_item("  #sweden", [], sweden_pill);
    test_create_item("#test", [], undefined);
    test_create_item("#germany", [], undefined, true, stream_data.get_invite_stream_data);
});

run_test("display_value", () => {
    assert.deepEqual(stream_pill.get_display_value_from_item(denmark_pill), "Denmark");
    assert.deepEqual(stream_pill.get_display_value_from_item(sweden_pill), "Sweden");
    sweden_pill.show_subscriber_count = false;
    assert.deepEqual(stream_pill.get_display_value_from_item(sweden_pill), "Sweden");
});

run_test("get_stream_id", () => {
    assert.equal(stream_pill.get_stream_name_from_item(denmark_pill), denmark.name);
});

run_test("get_user_ids", () => {
    const items = [denmark_pill, sweden_pill];
    const widget = {items: () => items};

    const user_ids = stream_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [1, 2, 3, 4, 5, 77]);
});

run_test("get_stream_ids", () => {
    const items = [denmark_pill, sweden_pill];
    const widget = {items: () => items};

    const stream_ids = stream_pill.get_stream_ids(widget);
    assert.deepEqual(stream_ids, [101, 102]);
});

run_test("generate_pill_html", () => {
    assert.deepEqual(
        stream_pill.generate_pill_html(denmark_pill),
        "<div class='pill 'data-stream-id=\"101\" tabindex=0>\n" +
            '    <span class="pill-label">\n' +
            '        <span class="pill-value">\n' +
            '<i class="zulip-icon zulip-icon-hashtag stream-privacy-type-icon" aria-hidden="true"></i>            Denmark\n' +
            "        </span></span>\n" +
            '    <div class="exit">\n' +
            '        <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>\n' +
            "    </div>\n" +
            "</div>\n",
    );
});
