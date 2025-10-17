"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const message_delete = zrequire("message_delete");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const user_groups = zrequire("user_groups");

mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config() {
        return {
            allow_everyone_group: false,
        };
    },
});

const realm = make_realm();
set_realm(realm);
const current_user = {};
set_current_user(current_user);

const me = {
    email: "me@zulip.com",
    full_name: "Current User",
    user_id: 100,
};

const moderator = {
    email: "moderator@zulip.com",
    full_name: "Moderator",
    user_id: 2,
    is_moderator: true,
};

const admin = {
    email: "admin@zulip.com",
    full_name: "Admin",
    user_id: 3,
    is_admin: true,
};
// set up user data
const admins_group = {
    name: "Admins",
    id: 1,
    members: new Set([admin.user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};

const moderators_group = {
    name: "Moderators",
    id: 2,
    members: new Set([moderator.user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set([admins_group.id]),
};

const everyone_group = {
    name: "Everyone",
    id: 3,
    members: new Set([me.user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set([moderators_group.id]),
};

const nobody_group = {
    name: "Nobody",
    id: 4,
    members: new Set([]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
user_groups.initialize({
    realm_user_groups: [admins_group, moderators_group, everyone_group, nobody_group],
});

people.init();
people.add_active_user(me);

function initialize_and_override_current_user(user_id, override) {
    people.initialize_current_user(user_id);
    override(current_user, "user_id", user_id);
}

run_test("get_deletability", ({override}) => {
    let message = {
        sent_by_me: false,
        locally_echoed: true,
        sender_id: me.user_id,
    };
    people.add_active_user(moderator);
    override(realm, "realm_can_delete_any_message_group", everyone_group.id);
    override(realm, "realm_can_delete_own_message_group", nobody_group.id);
    override(realm, "realm_message_content_delete_limit_seconds", null);
    initialize_and_override_current_user(me.user_id, override);

    // Spectators cannot delete messages
    page_params.is_spectator = true;
    assert.equal(message_delete.get_deletability(message), false);

    page_params.is_spectator = false;

    // User can delete any message
    assert.equal(message_delete.get_deletability(message), true);

    override(realm, "realm_can_delete_any_message_group", nobody_group.id);
    // User can't delete message sent by others
    assert.equal(message_delete.get_deletability(message), false);

    // Locally echoed messages are not deletable
    message.sent_by_me = true;
    assert.equal(message_delete.get_deletability(message), false);

    message.locally_echoed = false;
    assert.equal(message_delete.get_deletability(message), false);

    override(realm, "realm_can_delete_own_message_group", everyone_group.id);
    assert.equal(message_delete.get_deletability(message), true);

    message.sent_by_me = false;
    assert.equal(message_delete.get_deletability(message), false);
    message.sent_by_me = true;

    const now = new Date();
    const current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 5;

    // Time limit not exceeded
    override(realm, "realm_message_content_delete_limit_seconds", 10);
    assert.equal(message_delete.get_deletability(message), true);

    // Time limit exceeded, so user cannot delete messaeges now
    message.timestamp = current_timestamp - 60;
    assert.equal(message_delete.get_deletability(message), false);

    initialize_and_override_current_user(admin.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);
    // Time limit doesn't apply to users who can delete any message
    override(realm, "realm_can_delete_any_message_group", admins_group.id);
    assert.equal(message_delete.get_deletability(message), true);

    message.sent_by_me = false;
    override(realm, "realm_message_content_delete_limit_seconds", null);

    assert.equal(message_delete.get_deletability(message), true);

    initialize_and_override_current_user(moderator.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);

    // Test per-channel delete permission for deleting any message in the channel.
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        can_delete_any_message_group: moderators_group.id,
        can_delete_own_message_group: moderators_group.id,
    };
    const denmark = {
        subscribed: true,
        color: "red",
        name: "denmark",
        stream_id: 3,
        can_delete_any_message_group: nobody_group.id,
        can_delete_own_message_group: moderators_group.id,
    };
    stream_data.add_sub_for_tests(social);
    stream_data.add_sub_for_tests(denmark);

    message = {
        locally_echoed: true,
        type: "stream",
        stream_id: social.stream_id,
    };
    people.add_active_user(moderator);
    override(realm, "realm_can_delete_any_message_group", nobody_group.id);
    override(realm, "realm_can_delete_own_message_group", nobody_group.id);

    message.sender_id = moderator.user_id;
    initialize_and_override_current_user(moderator.user_id, override);
    assert.equal(message_delete.get_deletability(message), true);

    message.sender_id = me.user_id;
    initialize_and_override_current_user(me.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);

    message.stream_id = denmark.stream_id;
    assert.equal(message_delete.get_deletability(message), false);

    message.sender_id = moderator.user_id;
    initialize_and_override_current_user(moderator.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);

    // Test per-channel delete permissions for deleting own messages.
    message.stream_id = social.stream_id;

    message.sender_id = moderator.user_id;
    initialize_and_override_current_user(moderator.user_id, override);
    assert.equal(message_delete.get_deletability(message), true);

    message.sender_id = me.user_id;
    initialize_and_override_current_user(me.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);

    message.stream_id = denmark.stream_id;
    assert.equal(message_delete.get_deletability(message), false);

    initialize_and_override_current_user(moderator.user_id, override);
    assert.equal(message_delete.get_deletability(message), false);

    message.sender_id = moderator.user_id;
    assert.equal(message_delete.get_deletability(message), false);
});
