"use strict";

const assert = require("node:assert/strict");

const example_settings = require("./lib/example_settings.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_pill = zrequire("stream_pill");
const user_groups = zrequire("user_groups");

const current_user = {};
const realm = {};
set_current_user(current_user);
set_realm(realm);

const me = {
    email: "me@example.com",
    user_id: 5,
    full_name: "Me Myself",
};

const me_group = {
    name: "me_group",
    id: 1,
    members: new Set([me.user_id]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
};
const nobody_group = {
    name: "nobody_group",
    id: 2,
    members: new Set([]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
};

const denmark = {
    stream_id: 101,
    name: "Denmark",
    subscribed: true,
    can_administer_channel_group: nobody_group.id,
    can_add_subscribers_group: nobody_group.id,
    can_subscribe_group: nobody_group.id,
};
const sweden = {
    stream_id: 102,
    name: "Sweden",
    subscribed: false,
    can_administer_channel_group: nobody_group.id,
    can_add_subscribers_group: nobody_group.id,
    can_subscribe_group: nobody_group.id,
};
const germany = {
    stream_id: 103,
    name: "Germany",
    subscribed: false,
    invite_only: true,
    can_administer_channel_group: nobody_group.id,
    can_add_subscribers_group: nobody_group.id,
    can_subscribe_group: nobody_group.id,
};

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

peer_data.set_subscribers(denmark.stream_id, [1, 2, 77]);
peer_data.set_subscribers(sweden.stream_id, [1, 2, 3, 4, 5]);

people.add_active_user(me);
people.initialize_current_user(me.user_id);

user_groups.initialize({realm_user_groups: [me_group, nobody_group]});

run_test("create_item", ({override}) => {
    override(current_user, "user_id", me.user_id);
    override(current_user, "is_admin", true);
    override(
        realm,
        "server_supported_permission_settings",
        example_settings.server_supported_permission_settings,
    );
    override(realm, "realm_can_add_subscribers_group", me_group.id);
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

run_test("get_user_ids", async () => {
    const items = [denmark_pill, sweden_pill];
    const widget = {items: () => items};

    const user_ids = await stream_pill.get_user_ids(widget);
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
            '<i class="zulip-icon zulip-icon-hashtag channel-privacy-type-icon" aria-hidden="true"></i>            Denmark\n' +
            "        </span></span>\n" +
            '    <div class="exit">\n' +
            '        <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>\n' +
            "    </div>\n" +
            "</div>\n",
    );
});
