"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

// TODO: Remove after we enable support for
// web_public_streams in production.
page_params.development_environment = true;

const color_data = zrequire("color_data");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const sub_store = zrequire("sub_store");
const stream_data = zrequire("stream_data");
const hash_util = zrequire("hash_util");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_settings_data = zrequire("stream_settings_data");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");

const bot_data = mock_esm("../src/bot_data");
const channel = mock_esm("../src/channel");

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
set_realm(realm);
const user_settings = {};
initialize_user_settings({user_settings});

mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config(setting_name) {
        if (setting_name === "can_send_message_group") {
            return {
                allow_everyone_group: true,
            };
        }

        return {
            allow_everyone_group: false,
        };
    },
});

const me = {
    email: "me@zulip.com",
    full_name: "Current User",
    user_id: 100,
};

const test_user = {
    email: "test@zulip.com",
    full_name: "Test User",
    user_id: 101,
};

const guest_user = {
    email: "guest@example.com",
    user_id: 102,
    full_name: "Guest",
    is_guest: true,
};

const admin_user_id = 1;
const moderator_user_id = 2;

// set up user data
const admins_group = make_user_group({
    name: "Admins",
    id: 1,
    members: new Set([admin_user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});

const moderators_group = make_user_group({
    name: "Moderators",
    id: 2,
    members: new Set([moderator_user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set([admins_group.id]),
});

const everyone_group = make_user_group({
    name: "Everyone",
    id: 3,
    members: new Set([me.user_id, test_user.user_id, guest_user.user_id]),
    is_system_group: true,
    direct_subgroup_ids: new Set([moderators_group.id]),
});

const nobody_group = make_user_group({
    name: "Nobody",
    id: 4,
    members: new Set(),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});

const students = make_user_group({
    name: "Students",
    id: 5,
    members: new Set([test_user.user_id]),
    is_system_group: false,
    direct_subgroup_ids: new Set(),
});

const me_group = make_user_group({
    name: "Me Group",
    id: 6,
    members: new Set([me.user_id]),
    is_system_group: false,
    direct_subgroup_ids: new Set(),
});

function initialize_and_override_current_user(user_id, override) {
    people.initialize_current_user(user_id);
    override(current_user, "user_id", user_id);
}

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(current_user, "is_admin", false);
        page_params.realm_users = [];
        helpers.override(current_user, "is_guest", false);
        people.init();
        people.add_active_user(me);
        initialize_and_override_current_user(me.user_id, helpers.override);
        stream_data.clear_subscriptions();
        user_groups.initialize({
            realm_user_groups: [
                admins_group,
                moderators_group,
                everyone_group,
                nobody_group,
                students,
                me_group,
            ],
        });
        return f(helpers);
    });
}

test("basics", () => {
    const denmark = {
        subscribed: false,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
        is_muted: true,
        invite_only: true,
        history_public_to_subscribers: true,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const test = {
        subscribed: true,
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: false,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const web_public_stream = {
        subscribed: false,
        color: "yellow",
        name: "web_public_stream",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        is_web_public: true,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(denmark);
    stream_data.add_sub_for_tests(social);
    stream_data.add_sub_for_tests(web_public_stream);
    assert.ok(stream_data.all_subscribed_streams_are_in_home_view());
    stream_data.add_sub_for_tests(test);
    assert.ok(!stream_data.all_subscribed_streams_are_in_home_view());

    assert.equal(stream_data.get_sub("denmark"), denmark);
    assert.equal(stream_data.get_sub("Social"), social);
    assert.equal(stream_data.get_sub("web_public_stream"), web_public_stream);
    assert.ok(stream_data.is_web_public(web_public_stream.stream_id));

    assert.deepEqual(stream_data.subscribed_streams(), ["social", "test"]);
    assert.deepEqual(stream_data.get_colors(), ["red", "yellow"]);
    assert.deepEqual(stream_data.subscribed_stream_ids(), [social.stream_id, test.stream_id]);

    assert.ok(stream_data.is_subscribed(social.stream_id));
    assert.ok(!stream_data.is_subscribed(denmark.stream_id));

    assert.equal(stream_data.get_stream_privacy_policy(test.stream_id), "public");
    assert.equal(stream_data.get_stream_privacy_policy(social.stream_id), "invite-only");
    assert.equal(stream_data.get_stream_privacy_policy(denmark.stream_id), "invite-only");
    assert.equal(stream_data.get_stream_privacy_policy(web_public_stream.stream_id), "web-public");
    assert.ok(stream_data.is_web_public_by_stream_id(web_public_stream.stream_id));
    assert.ok(!stream_data.is_web_public_by_stream_id(social.stream_id));
    const unknown_stream_id = 9999;
    assert.ok(!stream_data.is_web_public_by_stream_id(unknown_stream_id));

    assert.ok(stream_data.is_invite_only_by_stream_id(social.stream_id));
    // Unknown stream id
    assert.ok(!stream_data.is_invite_only_by_stream_id(1000));

    assert.equal(stream_data.get_color(social.stream_id), "red");
    assert.equal(stream_data.get_color(undefined), "#c2c2c2");
    assert.equal(stream_data.get_color(1234567), "#c2c2c2");

    assert.ok(!stream_data.is_muted(social.stream_id));
    assert.ok(stream_data.is_muted(denmark.stream_id));

    assert.equal(sub_store.maybe_get_stream_name(), undefined);
    assert.equal(sub_store.maybe_get_stream_name(social.stream_id), "social");
    assert.equal(sub_store.maybe_get_stream_name(42), undefined);

    stream_data.set_realm_default_streams([denmark.stream_id]);
    assert.ok(stream_data.is_default_stream_id(denmark.stream_id));
    assert.ok(!stream_data.is_default_stream_id(social.stream_id));
    assert.ok(!stream_data.is_default_stream_id(999999));

    // "new" correct url formats
    assert.equal(stream_data.slug_to_stream_id("2-social"), 2);
    assert.equal(hash_util.decode_operand("channel", "2-social"), "2");

    assert.equal(stream_data.slug_to_stream_id("2"), 2);
    assert.equal(hash_util.decode_operand("channel", "2"), "2");

    // we still get 2 because it's a valid stream id
    assert.equal(stream_data.slug_to_stream_id("2-whatever"), 2);
    assert.equal(stream_data.slug_to_stream_id("2-"), 2);

    // legacy, we recognize "social" as a valid channel name
    assert.equal(stream_data.slug_to_stream_id("social"), 2);
    assert.equal(hash_util.decode_operand("channel", "social"), "2");

    // These aren't prepended with valid ids nor valid channel names. Return
    // the channel ID, since almost all URLs are the modern format and the
    // most likely explanation is an inaccessible channel.
    assert.equal(stream_data.slug_to_stream_id("999-social"), 999);
    assert.equal(hash_util.decode_operand("channel", "999-social"), "999");

    assert.equal(stream_data.slug_to_stream_id("99-whatever"), 99);
    assert.equal(hash_util.decode_operand("channel", "99-whatever"), "99");

    assert.equal(stream_data.slug_to_stream_id("25-or-6-to-4"), 25);
    assert.equal(hash_util.decode_operand("channel", "25-or-6-to-4"), "25");

    // If this is the name of a stream, its id is returned.
    const stream_starting_with_25 = {
        name: "25-or-6-to-4",
        stream_id: 400,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        subscribed: false,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        is_web_public: false,
    };
    stream_data.add_sub_for_tests(stream_starting_with_25);
    assert.equal(stream_data.slug_to_stream_id("25-or-6-to-4"), 400);
    assert.equal(hash_util.decode_operand("channel", "25-or-6-to-4"), "400");

    assert.equal(stream_data.slug_to_stream_id("2something"), undefined);
    assert.equal(hash_util.decode_operand("channel", "2something"), "");

    assert.equal(stream_data.slug_to_stream_id("99"), 99);
    assert.equal(hash_util.decode_operand("channel", "99"), "99");
    // If this is the name of a stream, its id is returned.
    const stream_99 = {
        name: "99",
        stream_id: 401,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(stream_99);
    assert.equal(stream_data.slug_to_stream_id("99"), 401);
    assert.equal(hash_util.decode_operand("channel", "99"), "401");
    // But if there's a stream with id 99, it gets priority over
    // a stream with name "99".
    const stream_id_99 = {
        name: "Some Stream",
        stream_id: 99,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(stream_id_99);
    assert.equal(stream_data.slug_to_stream_id("99"), 99);
    assert.equal(hash_util.decode_operand("channel", "99"), "99");

    // sub_store
    assert.equal(sub_store.get(-3), undefined);
    assert.equal(sub_store.get(undefined), undefined);
    assert.equal(sub_store.get(1), denmark);

    assert.deepEqual(stream_data.get_options_for_dropdown_widget(), [
        {
            name: "social",
            stream: {
                color: "red",
                history_public_to_subscribers: false,
                invite_only: true,
                is_muted: false,
                name: "social",
                stream_id: 2,
                subscribed: true,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 2,
        },
        {
            name: "test",
            stream: {
                color: "yellow",
                invite_only: false,
                is_muted: true,
                name: "test",
                stream_id: 3,
                subscribed: true,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 3,
        },
    ]);

    assert.deepEqual(stream_data.get_streams_for_move_messages_widget(), [
        {
            name: "social",
            stream: {
                color: "red",
                history_public_to_subscribers: false,
                invite_only: true,
                is_muted: false,
                name: "social",
                stream_id: 2,
                subscribed: true,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 2,
        },
        {
            name: "test",
            stream: {
                color: "yellow",
                invite_only: false,
                is_muted: true,
                name: "test",
                stream_id: 3,
                subscribed: true,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 3,
        },
        {
            name: "25-or-6-to-4",
            stream: {
                history_public_to_subscribers: true,
                invite_only: false,
                is_muted: false,
                is_web_public: false,
                name: "25-or-6-to-4",
                stream_id: 400,
                subscribed: false,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 400,
        },
        {
            name: "web_public_stream",
            stream: {
                name: "web_public_stream",
                stream_id: 4,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
                color: "yellow",
                history_public_to_subscribers: true,
                invite_only: false,
                is_muted: false,
                is_web_public: true,
                subscribed: false,
            },
            unique_id: 4,
        },
        {
            name: "99",
            stream: {
                name: "99",
                stream_id: 401,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 401,
        },
        {
            name: "Some Stream",
            stream: {
                name: "Some Stream",
                stream_id: 99,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 99,
        },
    ]);

    test.is_archived = true;
    assert.deepEqual(stream_data.get_options_for_dropdown_widget(), [
        {
            name: "social",
            stream: {
                color: "red",
                history_public_to_subscribers: false,
                invite_only: true,
                is_muted: false,
                name: "social",
                stream_id: 2,
                subscribed: true,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 2,
        },
    ]);

    social.invite_only = true;
    social.can_subscribe_group = me_group.id;
    social.subscribed = false;

    stream_starting_with_25.invite_only = true;

    assert.deepEqual(stream_data.get_streams_for_move_messages_widget(), [
        {
            name: "social",
            stream: {
                color: "red",
                history_public_to_subscribers: false,
                invite_only: true,
                is_muted: false,
                name: "social",
                stream_id: 2,
                subscribed: false,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: me_group.id,
            },
            unique_id: 2,
        },
        {
            name: "web_public_stream",
            stream: {
                color: "yellow",
                history_public_to_subscribers: true,
                invite_only: false,
                is_muted: false,
                is_web_public: true,
                name: "web_public_stream",
                stream_id: 4,
                subscribed: false,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 4,
        },
        {
            name: "99",
            stream: {
                name: "99",
                stream_id: 401,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 401,
        },
        {
            name: "Some Stream",
            stream: {
                name: "Some Stream",
                stream_id: 99,
                can_add_subscribers_group: admins_group.id,
                can_administer_channel_group: admins_group.id,
                can_subscribe_group: admins_group.id,
            },
            unique_id: 99,
        },
    ]);
});

test("get_streams_for_user", async ({override}) => {
    channel.get = (payload) =>
        payload.success({
            subscribed_channel_ids: [],
        });
    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
        is_muted: true,
        invite_only: true,
        history_public_to_subscribers: true,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const social = {
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const test = {
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: true,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const world = {
        color: "blue",
        name: "world",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const errors = {
        color: "green",
        name: "errors",
        stream_id: 5,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    const subs = [denmark, social, test, world, errors];
    for (const sub of subs) {
        stream_data.add_sub_for_tests(sub);
    }
    override(current_user, "user_id", me.user_id);

    peer_data.set_subscribers(denmark.stream_id, [me.user_id, test_user.user_id]);
    peer_data.set_subscribers(social.stream_id, [test_user.user_id]);
    peer_data.set_subscribers(test.stream_id, [test_user.user_id]);
    peer_data.set_subscribers(world.stream_id, [me.user_id]);

    override(realm, "realm_can_add_subscribers_group", students.id);
    assert.deepEqual((await stream_data.get_streams_for_user(me.user_id)).can_subscribe, [
        social,
        errors,
    ]);

    // test_user is subscribed to all three streams, but current user (me)
    // gets only two because of subscriber visibility policy of stream:
    // #denmark: current user is subscribed to it so he can see its subscribers.
    // #social: current user is can get this as neither this is invite only nor current
    //          user is a guest.
    // #test: current user is no longer subscribed to a private stream, so
    //        he cannot see whether test_user is subscribed to it.
    assert.deepEqual((await stream_data.get_streams_for_user(test_user.user_id)).subscribed, [
        denmark,
        social,
    ]);
    assert.deepEqual((await stream_data.get_streams_for_user(test_user.user_id)).can_subscribe, []);
    // Administrator is not part of the realm_can_add_subscribers_group
    // or the stream level can_add_subscribers_group. But users with
    // the permission to administer a channel can also subscribe other
    // users. Admins can administer all channels they have access to.
    override(current_user, "is_admin", true);
    assert.equal(user_groups.is_user_in_group(students.id, current_user.user_id), false);
    assert.deepEqual((await stream_data.get_streams_for_user(test_user.user_id)).can_subscribe, [
        world,
        errors,
    ]);

    override(realm, "realm_can_add_subscribers_group", everyone_group.id);
    assert.deepEqual((await stream_data.get_streams_for_user(test_user.user_id)).can_subscribe, [
        world,
        errors,
    ]);
});

test("renames", ({override_rewire}) => {
    override_rewire(stream_data, "set_max_channel_width_css_variable", noop);
    const id = 42;
    let sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: id,
    };
    stream_data.add_sub_for_tests(sub);
    sub = stream_data.get_sub("Denmark");
    assert.equal(sub.color, "red");
    sub = sub_store.get(id);
    assert.equal(sub.color, "red");

    stream_data.rename_sub(sub, "Sweden");
    sub = sub_store.get(id);
    assert.equal(sub.color, "red");
    assert.equal(sub.name, "Sweden");

    sub = stream_data.get_sub("Denmark");
    assert.equal(sub, undefined);

    sub = stream_data.get_sub_by_name("Denmark");
    assert.equal(sub.name, "Sweden");

    const actual_id = stream_data.get_stream_id("Denmark");
    assert.equal(actual_id, 42);
});

test("admin_options", ({override}) => {
    override(realm, "realm_can_add_subscribers_group", admins_group.id);

    function make_sub(can_administer_channel_group) {
        const sub = {
            subscribed: false,
            color: "blue",
            name: "stream_to_admin",
            stream_id: 1,
            is_muted: true,
            invite_only: false,
            can_remove_subscribers_group: admins_group.id,
            can_administer_channel_group,
            can_add_subscribers_group: admins_group.id,
            can_subscribe_group: admins_group.id,
            date_created: 1691057093,
            creator_id: null,
        };
        stream_data.add_sub_for_tests(sub);
        return sub;
    }

    function is_realm_admin(sub) {
        return stream_settings_data.get_sub_for_settings(sub).is_realm_admin;
    }

    function can_change_stream_permissions_requiring_content_access(sub) {
        return stream_settings_data.get_sub_for_settings(sub)
            .can_change_stream_permissions_requiring_content_access;
    }

    function can_change_stream_permissions_requiring_metadata_access(sub) {
        return stream_settings_data.get_sub_for_settings(sub)
            .can_change_stream_permissions_requiring_metadata_access;
    }

    // Test with can_administer_channel_group set to nobody.
    // non-admins can't do anything
    override(current_user, "is_admin", false);
    let sub = make_sub(nobody_group.id);
    assert.ok(!is_realm_admin(sub));
    assert.ok(!can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(!can_change_stream_permissions_requiring_content_access(sub));

    // Non admin user not subscribed to a private channel should not
    // have either of the permissions.
    sub = make_sub(nobody_group.id);
    sub.invite_only = true;
    sub.subscribed = false;
    assert.ok(!is_realm_admin(sub));
    assert.ok(!can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(!can_change_stream_permissions_requiring_content_access(sub));

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, "blue");

    // the remaining cases are for admin users
    override(current_user, "is_admin", true);

    // admins have both access to public streams.
    sub = make_sub(nobody_group.id);
    assert.ok(is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(can_change_stream_permissions_requiring_content_access(sub));

    // admins have content access to private streams only if they are
    // subscribed. They do have metadata access without subscribing.
    sub = make_sub(nobody_group.id);
    sub.invite_only = true;
    sub.subscribed = false;
    assert.ok(is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(!can_change_stream_permissions_requiring_content_access(sub));

    sub = make_sub(nobody_group.id);
    sub.invite_only = true;
    sub.subscribed = true;
    assert.ok(is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(can_change_stream_permissions_requiring_content_access(sub));

    // Test with can_administer_channel_group set to moderators.
    override(current_user, "is_admin", false);
    initialize_and_override_current_user(moderator_user_id, override);
    sub = make_sub(moderators_group.id);
    assert.ok(!is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(can_change_stream_permissions_requiring_content_access(sub));

    // Users in moderators group have content access to private streams
    // only if they are subscribed. They do have metadata access
    // without subscribing.
    sub = make_sub(moderators_group.id);
    sub.invite_only = true;
    sub.subscribed = false;
    assert.ok(!is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(!can_change_stream_permissions_requiring_content_access(sub));

    sub = make_sub(moderators_group.id);
    sub.invite_only = true;
    sub.subscribed = true;
    assert.ok(!is_realm_admin(sub));
    assert.ok(can_change_stream_permissions_requiring_metadata_access(sub));
    assert.ok(can_change_stream_permissions_requiring_content_access(sub));
});

test("stream_settings", ({override}) => {
    override(realm, "realm_can_add_subscribers_group", admins_group.id);
    const cinnamon = {
        stream_id: 1,
        name: "c",
        color: "cinnamon",
        subscribed: true,
        invite_only: false,
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };

    const blue = {
        stream_id: 2,
        name: "b",
        color: "blue",
        subscribed: false,
        invite_only: false,
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };

    const amber = {
        stream_id: 3,
        name: "a",
        color: "amber",
        subscribed: true,
        invite_only: true,
        history_public_to_subscribers: true,
        message_retention_days: 10,
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
        is_archived: true,
    };

    const red = {
        stream_id: 4,
        name: "r",
        color: "red",
        subscribed: true,
        invite_only: false,
        history_public_to_subscribers: true,
        message_retention_days: 10,
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
        is_archived: false,
    };
    stream_data.add_sub_for_tests(cinnamon);
    stream_data.add_sub_for_tests(amber);
    stream_data.add_sub_for_tests(blue);
    stream_data.add_sub_for_tests(red);

    let sub_rows = stream_settings_data.get_streams_for_settings_page();
    assert.equal(sub_rows[0].color, "blue");
    /* Archived channel "ambed" is skipped, since it is archived. */
    assert.equal(sub_rows[1].color, "cinnamon");
    assert.equal(sub_rows[2].color, "red");

    sub_rows = stream_data.get_streams_for_admin();
    assert.equal(sub_rows[0].name, "a");
    assert.equal(sub_rows[1].name, "b");
    assert.equal(sub_rows[2].name, "c");
    assert.equal(sub_rows[3].name, "r");
    assert.equal(sub_rows[0].invite_only, true);
    assert.equal(sub_rows[1].invite_only, false);
    assert.equal(sub_rows[2].invite_only, false);
    assert.equal(sub_rows[3].invite_only, false);

    assert.equal(sub_rows[0].history_public_to_subscribers, true);
    assert.equal(sub_rows[0].message_retention_days, 10);

    let sub = stream_data.get_sub("a");
    stream_data.update_stream_privacy(sub, {
        invite_only: false,
        history_public_to_subscribers: false,
    });
    stream_data.update_message_retention_setting(sub, -1);
    stream_data.update_topics_policy_setting(sub, "allow_topics_policy");
    stream_data.update_stream_permission_group_setting(
        "can_remove_subscribers_group",
        sub,
        moderators_group.id,
    );
    stream_data.update_stream_permission_group_setting(
        "can_administer_channel_group",
        sub,
        moderators_group.id,
    );
    stream_data.update_channel_folder(sub, 3);
    assert.equal(sub.invite_only, false);
    assert.equal(sub.history_public_to_subscribers, false);
    assert.equal(sub.message_retention_days, -1);
    assert.equal(sub.topics_policy, "allow_topics_policy");
    assert.equal(sub.can_remove_subscribers_group, moderators_group.id);
    assert.equal(sub.can_administer_channel_group, moderators_group.id);
    assert.equal(sub.folder_id, 3);

    // For guest user only retrieve subscribed streams
    sub_rows = stream_settings_data.get_updated_unsorted_subs();
    assert.equal(sub_rows.length, 4);
    override(current_user, "is_guest", true);
    sub_rows = stream_settings_data.get_updated_unsorted_subs();
    assert.equal(sub_rows[0].name, "c");
    assert.equal(sub_rows[1].name, "a");
    assert.equal(sub_rows[2].name, "r");
    assert.equal(sub_rows.length, 3);

    sub = stream_data.get_sub("b");
    stream_data.update_stream_privacy(sub, {
        is_web_public: true,
    });
    assert.equal(sub.is_web_public, true);
});

test("default_stream_names", () => {
    const announce = {
        stream_id: 101,
        name: "announce",
        subscribed: true,
    };

    const public_stream = {
        stream_id: 102,
        name: "public",
        subscribed: true,
    };

    const private_stream = {
        stream_id: 103,
        name: "private",
        subscribed: true,
        invite_only: true,
    };

    const general = {
        stream_id: 104,
        name: "general",
        subscribed: true,
        invite_only: false,
    };

    stream_data.set_realm_default_streams([announce.stream_id, general.stream_id]);
    stream_data.add_sub_for_tests(announce);
    stream_data.add_sub_for_tests(public_stream);
    stream_data.add_sub_for_tests(private_stream);
    stream_data.add_sub_for_tests(general);

    const names = stream_data.get_non_default_stream_names();
    assert.deepEqual(names, [{name: "public", unique_id: 102}]);

    const default_stream_ids = stream_data.get_default_stream_ids();
    assert.deepEqual(default_stream_ids.toSorted(), [announce.stream_id, general.stream_id]);
});

test("delete_sub", () => {
    const canada = {
        stream_id: 101,
        name: "Canada",
        subscribed: true,
    };

    stream_data.add_sub_for_tests(canada);

    assert.ok(stream_data.is_subscribed(canada.stream_id));
    assert.equal(stream_data.get_sub("Canada").stream_id, canada.stream_id);
    assert.equal(sub_store.get(canada.stream_id).name, "Canada");

    stream_data.delete_sub(canada.stream_id);
    assert.ok(!stream_data.is_subscribed(canada.stream_id));
    assert.ok(!stream_data.get_sub("Canada"));
    assert.ok(!sub_store.get(canada.stream_id));

    blueslip.expect("warn", "Failed to archive stream 99999");
    stream_data.delete_sub(99999);
});

test("mark_archived", () => {
    const canada = {
        is_archived: false,
        stream_id: 101,
        name: "Canada",
        subscribed: true,
    };

    stream_data.add_sub_for_tests(canada);
    const num_subscribed_subs = stream_data.num_subscribed_subs();
    const archived_subs = stream_data.get_archived_subs();

    assert.ok(stream_data.is_subscribed(canada.stream_id));
    assert.equal(stream_data.get_sub("Canada").stream_id, canada.stream_id);
    assert.equal(sub_store.get(canada.stream_id).name, "Canada");
    assert.equal(stream_data.is_stream_archived_by_id(canada.stream_id), false);

    stream_data.mark_archived(canada.stream_id);
    assert.ok(stream_data.is_stream_archived_by_id(canada.stream_id));
    assert.ok(stream_data.is_subscribed(canada.stream_id));
    assert.ok(stream_data.get_sub("Canada"));
    assert.ok(sub_store.get(canada.stream_id));
    assert.equal(stream_data.num_subscribed_subs(), num_subscribed_subs);
    assert.equal(stream_data.get_archived_subs().length, archived_subs.length + 1);

    blueslip.expect("warn", "Failed to archive stream 99999");
    stream_data.mark_archived(99999);
});

test("mark_unarchived", () => {
    const canada = {
        stream_id: 101,
        name: "Canada",
        is_archived: true,
        subscribed: true,
    };

    stream_data.add_sub_for_tests(canada);
    assert.ok(stream_data.is_stream_archived_by_id(canada.stream_id));
    assert.ok(stream_data.is_subscribed(canada.stream_id));

    stream_data.mark_unarchived(canada.stream_id);
    assert.ok(!stream_data.is_stream_archived_by_id(canada.stream_id));
    assert.ok(stream_data.is_subscribed(canada.stream_id));
    const sub = stream_data.get_sub("Canada");
    assert.equal(sub.stream_id, canada.stream_id);
    assert.equal(sub.is_archived, false);

    blueslip.expect("warn", "Failed to unarchive stream 99999");
    stream_data.mark_unarchived(99999);
});

test("notifications", ({override}) => {
    const india = {
        stream_id: 102,
        name: "India",
        color: "#000080",
        subscribed: true,
        invite_only: false,
        is_web_public: false,
        desktop_notifications: null,
        audible_notifications: null,
        email_notifications: null,
        push_notifications: null,
        wildcard_mentions_notify: null,
    };
    stream_data.add_sub_for_tests(india);

    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    override(user_settings, "enable_stream_desktop_notifications", true);
    override(user_settings, "enable_stream_audible_notifications", true);
    assert.ok(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    override(user_settings, "enable_stream_desktop_notifications", false);
    override(user_settings, "enable_stream_audible_notifications", false);
    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = true;
    india.audible_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = false;
    india.audible_notifications = false;
    override(user_settings, "enable_stream_desktop_notifications", true);
    override(user_settings, "enable_stream_audible_notifications", true);
    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    override(user_settings, "wildcard_mentions_notify", true);
    assert.ok(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    override(user_settings, "wildcard_mentions_notify", false);
    assert.ok(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    india.wildcard_mentions_notify = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    override(user_settings, "wildcard_mentions_notify", true);
    india.wildcard_mentions_notify = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));

    override(user_settings, "enable_stream_push_notifications", true);
    assert.ok(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    override(user_settings, "enable_stream_push_notifications", false);
    assert.ok(!stream_data.receives_notifications(india.stream_id, "push_notifications"));
    india.push_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    override(user_settings, "enable_stream_push_notifications", true);
    india.push_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "push_notifications"));

    override(user_settings, "enable_stream_email_notifications", true);
    assert.ok(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    override(user_settings, "enable_stream_email_notifications", false);
    assert.ok(!stream_data.receives_notifications(india.stream_id, "email_notifications"));
    india.email_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    override(user_settings, "enable_stream_email_notifications", true);
    india.email_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "email_notifications"));

    const canada = {
        stream_id: 103,
        name: "Canada",
        color: "#d80621",
        subscribed: true,
        invite_only: true,
        is_web_public: false,
        desktop_notifications: null,
        audible_notifications: null,
        email_notifications: null,
        push_notifications: null,
        wildcard_mentions_notify: null,
    };
    stream_data.add_sub_for_tests(canada);

    const antarctica = {
        stream_id: 104,
        name: "Antarctica",
        subscribed: true,
        desktop_notifications: null,
        audible_notifications: null,
        email_notifications: null,
        push_notifications: null,
        wildcard_mentions_notify: null,
    };
    stream_data.add_sub_for_tests(antarctica);

    override(user_settings, "enable_stream_desktop_notifications", true);
    override(user_settings, "enable_stream_audible_notifications", true);
    override(user_settings, "enable_stream_email_notifications", false);
    override(user_settings, "enable_stream_push_notifications", false);
    override(user_settings, "wildcard_mentions_notify", true);

    india.desktop_notifications = null;
    india.audible_notifications = true;
    india.email_notifications = true;
    india.push_notifications = true;
    india.wildcard_mentions_notify = false;

    canada.desktop_notifications = true;
    canada.audible_notifications = false;
    canada.email_notifications = true;
    canada.push_notifications = null;
    canada.wildcard_mentions_notify = false;

    antarctica.desktop_notifications = true;
    antarctica.audible_notifications = null;
    antarctica.email_notifications = false;
    antarctica.push_notifications = null;
    antarctica.wildcard_mentions_notify = null;

    const unmatched_streams =
        stream_settings_data.get_unmatched_streams_for_notification_settings();
    const expected_streams = [
        {
            desktop_notifications: true,
            audible_notifications: false,
            email_notifications: true,
            push_notifications: false,
            wildcard_mentions_notify: false,
            invite_only: true,
            is_web_public: false,
            stream_name: "Canada",
            stream_id: 103,
            color: "#d80621",
        },
        {
            desktop_notifications: true,
            audible_notifications: true,
            email_notifications: true,
            push_notifications: true,
            wildcard_mentions_notify: false,
            invite_only: false,
            is_web_public: false,
            stream_name: "India",
            stream_id: 102,
            color: "#000080",
        },
    ];

    assert.deepEqual(unmatched_streams, expected_streams);

    // Get line coverage on defensive code with bogus stream_id.
    assert.ok(!stream_data.receives_notifications(999999));
});

const tony = {
    stream_id: 999,
    name: "tony",
    subscribed: true,
    is_muted: false,
};

const jazy = {
    stream_id: 500,
    name: "jazy",
    subscribed: false,
    is_muted: true,
};

test("is_new_stream_announcements_stream_muted", ({override}) => {
    stream_data.add_sub_for_tests(tony);
    stream_data.add_sub_for_tests(jazy);

    override(realm, "realm_new_stream_announcements_stream_id", tony.stream_id);
    assert.ok(!stream_data.is_new_stream_announcements_stream_muted());

    override(realm, "realm_new_stream_announcements_stream_id", jazy.stream_id);
    assert.ok(stream_data.is_new_stream_announcements_stream_muted());
});

test("muted_stream_ids", () => {
    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
        is_muted: true,
        invite_only: true,
        history_public_to_subscribers: true,
    };
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
    };
    const test = {
        subscribed: true,
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: false,
    };
    const web_public_stream = {
        subscribed: true,
        color: "yellow",
        name: "web_public_stream",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        is_web_public: true,
    };
    stream_data.add_sub_for_tests(denmark);
    stream_data.add_sub_for_tests(social);
    stream_data.add_sub_for_tests(test);
    stream_data.add_sub_for_tests(web_public_stream);

    assert.deepEqual(stream_data.muted_stream_ids(), [1, 3]);
});

test("realm_has_new_stream_announcements_stream", ({override}) => {
    override(realm, "realm_new_stream_announcements_stream_id", 10);
    assert.ok(stream_data.realm_has_new_stream_announcements_stream());
    override(realm, "realm_new_stream_announcements_stream_id", -1);
    assert.ok(!stream_data.realm_has_new_stream_announcements_stream());
});

test("remove_default_stream", () => {
    const remove_me = {
        stream_id: 674,
        name: "remove_me",
        subscribed: false,
        is_muted: true,
    };

    stream_data.add_sub_for_tests(remove_me);
    stream_data.set_realm_default_streams([remove_me.stream_id]);
    stream_data.remove_default_stream(remove_me.stream_id);
    assert.ok(!stream_data.is_default_stream_id(remove_me.stream_id));
});

test("canonicalized_name", () => {
    assert.deepStrictEqual(stream_data.canonicalized_name("Stream_Bar"), "stream_bar");
});

test("create_sub", () => {
    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
        is_web_public: true,
        subscriber_count: 3,
    };

    const canada = {
        name: "Canada",
        subscribed: true,
        subscriber_count: 2,
    };

    const antarctica = {
        stream_id: 103,
        name: "Antarctica",
        subscribed: true,
        color: "#76ce90",
        partial_subscribers: [1, 2, 3],
        subscriber_count: 10,
    };

    const india_sub = stream_data.create_sub_from_server_data(india);
    assert.ok(india_sub);
    assert.equal(india_sub.color, color_data.colors[0]);
    const new_sub = stream_data.create_sub_from_server_data(india);
    // make sure sub doesn't get created twice
    assert.equal(india_sub, new_sub);

    assert.throws(
        () => {
            stream_data.create_sub_from_server_data("Canada", canada);
        },
        {message: "We cannot create a sub without a stream_id"},
    );

    const antarctica_sub = stream_data.create_sub_from_server_data(antarctica);
    assert.ok(antarctica_sub);
    assert.equal(antarctica_sub.color, "#76ce90");
});

test("creator_id", ({override}) => {
    people.add_active_user(test_user);
    override(realm, "realm_can_access_all_users_group", everyone_group.id);
    override(current_user, "user_id", me.user_id);
    // When creator id is not a valid user id
    assert.throws(() => stream_data.maybe_get_creator_details(-1), {
        name: "Error",
        message: "Unknown user_id in get_by_user_id: -1",
    });

    // When there is no creator
    assert.equal(stream_data.maybe_get_creator_details(null), undefined);

    let creator_details = {...people.get_by_user_id(test_user.user_id), is_active: true};
    assert.deepStrictEqual(
        stream_data.maybe_get_creator_details(test_user.user_id),
        creator_details,
    );

    // Check when creator is deactivated.
    people.deactivate(test_user);
    creator_details = {...people.get_by_user_id(test_user.user_id), is_active: false};
    assert.deepStrictEqual(
        stream_data.maybe_get_creator_details(test_user.user_id),
        creator_details,
    );
});

test("initialize", ({override, override_rewire}) => {
    function get_params() {
        return {
            subscriptions: [
                {
                    name: "subscriptions",
                    stream_id: 2001,
                    subscriber_count: 0,
                },
            ],

            unsubscribed: [
                {
                    name: "unsubscribed",
                    stream_id: 2002,
                    subscriber_count: 0,
                },
            ],

            never_subscribed: [
                {
                    name: "never_subscribed",
                    stream_id: 2003,
                    subscriber_count: 0,
                },
            ],

            realm_default_streams: [],
        };
    }

    function initialize() {
        stream_data.initialize(get_params());
    }

    override(realm, "realm_new_stream_announcements_stream_id", -1);
    override_rewire(stream_data, "set_max_channel_width_css_variable", noop);

    initialize();

    const stream_names = new Set(stream_data.get_streams_for_admin().map((elem) => elem.name));
    assert.ok(stream_names.has("subscriptions"));
    assert.ok(stream_names.has("unsubscribed"));
    assert.ok(stream_names.has("never_subscribed"));
    assert.equal(stream_data.get_new_stream_announcements_stream(), "");

    // Simulate a private stream the user isn't subscribed to
    override(realm, "realm_new_stream_announcements_stream_id", 89);
    initialize();
    assert.equal(stream_data.get_new_stream_announcements_stream(), "");

    // Now actually subscribe the user to the stream
    initialize();
    const foo = {
        name: "foo",
        stream_id: 89,
    };

    stream_data.add_sub_for_tests(foo);
    initialize();
    assert.equal(stream_data.get_new_stream_announcements_stream(), "foo");
});

test("edge_cases", () => {
    const bad_stream_ids = [555555, 99999];

    // just make sure we don't explode
    stream_settings_data.sort_for_stream_settings(bad_stream_ids);
});

test("get_invite_stream_data", ({override}) => {
    // add default stream
    const orie = {
        name: "Orie",
        stream_id: 320,
        invite_only: false,
        subscribed: true,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };

    people.init();
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    override(current_user, "user_id", me.user_id);
    override(current_user, "is_admin", true);

    stream_data.add_sub_for_tests(orie);
    stream_data.set_realm_default_streams([orie.stream_id]);

    override(realm, "realm_can_add_subscribers_group", everyone_group.id);

    const expected_list = [
        {
            name: "Orie",
            stream_id: 320,
            invite_only: false,
            subscribed: true,
            is_web_public: false,
            can_administer_channel_group: nobody_group.id,
            can_add_subscribers_group: nobody_group.id,
            can_subscribe_group: nobody_group.id,
        },
    ];
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    const inviter = {
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        subscribed: true,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };
    stream_data.add_sub_for_tests(inviter);

    expected_list.push({
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        subscribed: true,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    });
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    // add unsubscribed private stream
    const tokyo = {
        name: "Tokyo",
        stream_id: 12,
        invite_only: true,
        subscribed: false,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };

    stream_data.add_sub_for_tests(tokyo);
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    const random = {
        name: "Random",
        stream_id: 34,
        invite_only: false,
        subscribed: false,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };

    stream_data.add_sub_for_tests(random);

    expected_list.push({
        name: "Random",
        stream_id: 34,
        invite_only: false,
        subscribed: false,
        is_web_public: false,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    });
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);
});

test("can_post_messages_in_stream", ({override}) => {
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
        can_send_message_group: admins_group.id,
    };
    override(current_user, "user_id", test_user.user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    social.can_send_message_group = everyone_group.id;
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    override(current_user, "user_id", test_user.user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    override(current_user, "user_id", me.user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    const anonymous_setting_group = {
        direct_members: [test_user.user_id],
        direct_subgroups: [admins_group.id],
    };
    social.can_send_message_group = anonymous_setting_group;
    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    override(current_user, "user_id", me.user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    override(current_user, "user_id", test_user.user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    page_params.is_spectator = false;
    social.is_archived = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);
});

test("can_create_topics_in_stream", ({override}) => {
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_create_topic_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), false);

    sub.can_create_topic_group = moderators_group.id;
    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", test_user.user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), false);

    sub.can_create_topic_group = everyone_group.id;
    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", test_user.user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);
    override(current_user, "user_id", guest_user.user_id);
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), false);

    page_params.is_spectator = false;
    sub.is_archived = true;
    assert.equal(stream_data.can_create_new_topics_in_stream(sub.stream_id), false);
});

test("can_move_messages_out_of_channel", ({override}) => {
    const social = {
        subscribed: true,
        name: "social",
        stream_id: 10,
        can_administer_channel_group: nobody_group.id,
        can_move_messages_out_of_channel_group: nobody_group.id,
    };
    const scotland = {
        subscribed: true,
        name: "scotland",
        stream_id: 11,
        can_administer_channel_group: nobody_group.id,
        can_move_messages_out_of_channel_group: everyone_group.id,
    };

    override(realm, "realm_can_move_messages_between_channels_group", nobody_group.id);
    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.user_can_move_messages_out_of_channel(social), false);
    social.can_administer_channel_group = admins_group.id;
    assert.equal(stream_data.user_can_move_messages_out_of_channel(social), true);

    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.user_can_move_messages_out_of_channel(social), false);

    assert.equal(stream_data.user_can_move_messages_out_of_channel(scotland), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.user_can_move_messages_out_of_channel(scotland), false);

    page_params.is_spectator = false;
    scotland.is_archived = true;
    assert.equal(stream_data.user_can_move_messages_out_of_channel(scotland), false);
});

test("can_move_messages_within_channel", ({override}) => {
    const social = {
        subscribed: true,
        name: "social",
        stream_id: 10,
        can_administer_channel_group: nobody_group.id,
        can_move_messages_within_channel_group: nobody_group.id,
    };
    const scotland = {
        subscribed: true,
        name: "scotland",
        stream_id: 11,
        can_administer_channel_group: nobody_group.id,
        can_move_messages_within_channel_group: everyone_group.id,
    };

    override(realm, "realm_can_move_messages_between_topics_group", nobody_group.id);
    override(current_user, "user_id", admin_user_id);
    assert.equal(stream_data.user_can_move_messages_within_channel(social), false);
    social.can_administer_channel_group = admins_group.id;
    assert.equal(stream_data.user_can_move_messages_within_channel(social), true);

    override(current_user, "user_id", moderator_user_id);
    assert.equal(stream_data.user_can_move_messages_within_channel(social), false);

    assert.equal(stream_data.user_can_move_messages_within_channel(scotland), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.user_can_move_messages_within_channel(scotland), false);

    page_params.is_spectator = false;
    scotland.is_archived = true;
    assert.equal(stream_data.user_can_move_messages_within_channel(scotland), false);
});

test("can_resolve_topics", ({override}) => {
    override(realm, "realm_can_resolve_topics_group", admins_group.id);
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_resolve_topics_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    assert.equal(stream_data.can_resolve_topics(undefined), false);
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_resolve_topics(undefined), true);
    assert.equal(stream_data.can_resolve_topics(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), false);

    sub.can_resolve_topics_group = moderators_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), false);

    sub.can_resolve_topics_group = everyone_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_resolve_topics(sub), true);
});

test("can_unsubscribe_others", ({override}) => {
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);

    sub.can_remove_subscribers_group = moderators_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);

    sub.can_remove_subscribers_group = everyone_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);

    // With the setting set to user defined group not including admin,
    // admin can still unsubscribe others.
    sub.can_remove_subscribers_group = students.id;
    override(current_user, "is_admin", true);
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    override(current_user, "is_admin", false);
    sub.can_administer_channel_group = admins_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    sub.can_administer_channel_group = nobody_group.id;
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    override(current_user, "is_guest", true);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);
    override(current_user, "is_guest", false);

    // This isn't a real state, but we want coverage on !can_view_subscribers.
    sub.can_remove_subscribers_group = everyone_group.id;
    sub.subscribed = false;
    sub.invite_only = true;
    override(current_user, "is_admin", true);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    override(current_user, "is_admin", false);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);
});

test("can_subscribe_others", ({override}) => {
    override(realm, "realm_can_add_subscribers_group", admins_group.id);
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), false);

    sub.can_add_subscribers_group = moderators_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), false);

    sub.can_add_subscribers_group = everyone_group.id;
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);

    // With the setting set to user defined group not including admin,
    // admin can still subscribe others.
    sub.can_add_subscribers_group = students.id;
    override(current_user, "is_admin", true);
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    override(current_user, "is_admin", false);
    initialize_and_override_current_user(moderator_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), false);
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    override(current_user, "is_guest", true);
    assert.equal(stream_data.can_subscribe_others(sub), false);
    override(current_user, "is_guest", false);

    // A user belonging to `can_add_subscribers_group` can subscribe
    // others without being subscribed to a private channel.
    sub.subscribed = false;
    sub.invite_only = true;
    override(current_user, "is_guest", false);
    assert.equal(stream_data.can_subscribe_others(sub), true);
    override(current_user, "is_guest", true);
    assert.equal(stream_data.can_subscribe_others(sub), false);
    sub.can_add_subscribers_group = nobody_group.id;

    // User with administrator privileges cannot subscribe others to a
    // private channel they are not subscribed to.
    override(current_user, "is_admin", true);
    initialize_and_override_current_user(admin_user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), false);
    override(current_user, "is_admin", false);
    sub.can_administer_channel_group = students.id;
    initialize_and_override_current_user(test_user.user_id, override);
    assert.equal(stream_data.can_subscribe_others(sub), false);
});

test("user_can_set_topics_policy", ({override}) => {
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    override(realm, "realm_can_set_topics_policy_group", nobody_group.id);
    // Admins can always change per-channel topics policy.
    initialize_and_override_current_user(admin_user_id, override);
    override(current_user, "is_admin", true);
    assert.equal(stream_data.user_can_set_topics_policy(sub), true);

    initialize_and_override_current_user(moderator_user_id, override);
    override(current_user, "is_admin", false);
    assert.equal(stream_data.user_can_set_topics_policy(sub), false);

    // Not allowed as user not in can_administer_channel_group.
    override(realm, "realm_can_set_topics_policy_group", everyone_group.id);
    assert.equal(stream_data.user_can_set_topics_policy(sub), false);

    sub.can_administer_channel_group = moderators_group.id;
    assert.equal(stream_data.user_can_set_topics_policy(sub), true);

    // Only realm_can_set_topics_policy_group is checked if sub is not provided.
    assert.equal(stream_data.user_can_set_topics_policy(), true);
    override(realm, "realm_can_set_topics_policy_group", nobody_group.id);
    assert.equal(stream_data.user_can_set_topics_policy(sub), false);
});

test("user_can_set_delete_message_policy", ({override}) => {
    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(sub);

    override(realm, "realm_can_set_delete_message_policy_group", nobody_group.id);
    // Admins can always change per-channel delete_message policy.
    initialize_and_override_current_user(admin_user_id, override);
    override(current_user, "is_admin", true);
    assert.equal(stream_data.user_can_set_delete_message_policy(sub), true);

    initialize_and_override_current_user(moderator_user_id, override);
    override(current_user, "is_admin", false);
    assert.equal(stream_data.user_can_set_delete_message_policy(sub), false);

    // Not allowed as user not in can_administer_channel_group.
    override(realm, "realm_can_set_delete_message_policy_group", everyone_group.id);
    assert.equal(stream_data.user_can_set_delete_message_policy(sub), false);

    sub.can_administer_channel_group = moderators_group.id;
    assert.equal(stream_data.user_can_set_delete_message_policy(sub), true);

    // Only realm_can_set_delete_message_policy_group is checked if sub is not provided.
    assert.equal(stream_data.user_can_set_delete_message_policy(), true);
    override(realm, "realm_can_set_delete_message_policy_group", nobody_group.id);
    assert.equal(stream_data.user_can_set_delete_message_policy(sub), false);
});

test("options for dropdown widget", () => {
    const denmark = {
        subscribed: true,
        color: "blue",
        name: "Denmark",
        stream_id: 1,
        is_muted: true,
        invite_only: true,
        history_public_to_subscribers: true,
    };
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
    };
    const test = {
        subscribed: true,
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: false,
    };
    const web_public_stream = {
        subscribed: true,
        color: "yellow",
        name: "web_public_stream",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        is_web_public: true,
    };
    stream_data.add_sub_for_tests(denmark);
    stream_data.add_sub_for_tests(social);
    stream_data.add_sub_for_tests(web_public_stream);
    stream_data.add_sub_for_tests(test);

    assert.deepEqual(stream_data.get_options_for_dropdown_widget(), [
        {
            name: "Denmark",
            stream: {
                subscribed: true,
                color: "blue",
                name: "Denmark",
                stream_id: 1,
                is_muted: true,
                invite_only: true,
                history_public_to_subscribers: true,
            },
            unique_id: 1,
        },
        {
            name: "social",
            stream: {
                color: "red",
                history_public_to_subscribers: false,
                invite_only: true,
                is_muted: false,
                name: "social",
                stream_id: 2,
                subscribed: true,
            },
            unique_id: 2,
        },
        {
            name: "test",
            stream: {
                color: "yellow",
                invite_only: false,
                is_muted: true,
                name: "test",
                stream_id: 3,
                subscribed: true,
            },
            unique_id: 3,
        },
        {
            name: "web_public_stream",
            stream: {
                subscribed: true,
                color: "yellow",
                name: "web_public_stream",
                stream_id: 4,
                is_muted: false,
                invite_only: false,
                history_public_to_subscribers: true,
                is_web_public: true,
            },
            unique_id: 4,
        },
    ]);
});

test("get_current_user_and_their_bots_with_post_messages_permission", ({override}) => {
    const social = {
        name: "social",
        stream_id: 2,
        is_archived: false,
        can_send_message_group: {
            direct_subgroups: [],
            direct_members: [me.user_id],
        },
    };
    const bot = {
        is_active: true,
        user_id: 999,
    };
    const bot_user = {
        email: "bot@zulip.com",
        full_name: "Bot User",
        user_id: 999,
        is_bot: true,
    };

    people.add_active_user(bot_user);
    override(current_user, "user_id", me.user_id);
    override(bot_data, "get_all_bots_for_current_user", () => [bot]);

    // Test that bot isn't included in the returned users list if bot cannot send message.
    assert.deepEqual(
        stream_data.get_current_user_and_their_bots_with_post_messages_permission(social),
        [current_user],
    );

    // Test that bot is included in the returned users list if bot can send message.
    social.can_send_message_group.direct_members = [me.user_id, bot.user_id];
    assert.deepEqual(
        stream_data.get_current_user_and_their_bots_with_post_messages_permission(social),
        [current_user, bot],
    );
});

test("can_access_stream_email", ({override}) => {
    const social = {
        name: "social",
        stream_id: 2,
        is_archived: false,
        is_web_public: false,
        subscribed: true,
        invite_only: false,
        history_public_to_subscribers: true,
        can_send_message_group: {
            direct_subgroups: [],
            direct_members: [me.user_id],
        },
        can_add_subscribers_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };
    const bot = {
        is_active: true,
        user_id: 999,
    };
    const bot_user = {
        email: "bot@zulip.com",
        full_name: "Bot User",
        user_id: 999,
        is_bot: true,
    };
    people.add_active_user(bot_user);
    override(current_user, "user_id", me.user_id);

    // No user can access email of archived streams.
    social.is_archived = true;
    assert.equal(stream_data.can_access_stream_email(social), false);
    social.is_archived = false;

    // Spectator cannot access email of any stream.
    page_params.is_spectator = true;
    assert.equal(stream_data.can_access_stream_email(social), false);
    page_params.is_spectator = false;

    assert.equal(stream_data.can_access_stream_email(social), true);

    // User should be in can_send_message_group to access stream email.
    social.can_send_message_group.direct_members = [123];
    assert.equal(stream_data.can_access_stream_email(social), false);

    // Even admins not in can_send_message_group cannot access email.
    override(current_user, "is_admin", true);
    assert.equal(stream_data.can_access_stream_email(social), false);
    override(current_user, "is_admin", false);

    social.can_send_message_group.direct_members = [bot.user_id];
    assert.equal(stream_data.can_access_stream_email(social), false);

    social.can_send_message_group.direct_members = [me.user_id];
    assert.equal(stream_data.can_access_stream_email(social), true);

    // Unsubscribe the user to test cases of unsubscribed users
    // having access to email of web-public and public streams.
    social.subscribed = false;

    // All users with post permissions, including guests, can
    // access email of web-public streams.
    override(current_user, "is_guest", true);
    social.is_web_public = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    // Non-guests have access to stream email of all public streams.
    social.is_web_public = false;
    assert.equal(stream_data.can_access_stream_email(social), false);

    override(current_user, "is_guest", false);
    assert.equal(stream_data.can_access_stream_email(social), true);

    // Subscribed users have access to stream email for private
    // streams with both public and protected history.
    social.invite_only = true;
    assert.equal(stream_data.can_access_stream_email(social), false);

    social.subscribed = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.subscribed = false;
    social.history_public_to_subscribers = false;

    assert.equal(stream_data.can_access_stream_email(social), false);

    social.subscribed = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.subscribed = false;
    const anonymous_setting_group = {
        direct_members: [me.user_id],
        direct_subgroups: [],
    };
    social.can_add_subscribers_group = anonymous_setting_group;
    social.can_subscribe_group = anonymous_setting_group;

    // Non subscribed users cannot access email for private streams
    // with protected history even if they have content access via
    // group permissions.
    assert.equal(social.history_public_to_subscribers, false);
    assert.equal(stream_data.can_access_stream_email(social), false);

    // Non subscribed non-guest users can access email for private streams
    // with public history  if they have content access to stream via
    // group permissions.
    social.history_public_to_subscribers = true;
    override(current_user, "is_guest", true);
    assert.equal(stream_data.can_access_stream_email(social), false);
    override(current_user, "is_guest", false);

    assert.equal(stream_data.can_access_stream_email(social), true);

    social.can_subscribe_group = nobody_group.id;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.can_add_subscribers_group = nobody_group.id;
    social.can_subscribe_group = anonymous_setting_group;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.can_subscribe_group = nobody_group.id;
    assert.equal(stream_data.can_access_stream_email(social), false);
});

const access_cases = [
    {
        desc: "subscribed user has full access to private channel but cannot preview if history is not public",
        stream: {
            subscribed: true,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: false,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: false},
    },
    {
        desc: "unsubscribed user has full access to web-public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: true,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "spectator has full access to web-public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: true,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: false},
        spectator: true,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "spectator is denied access to non-web-public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: false},
        spectator: true,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "unsubscribed user is denied access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: false,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "realm admin has metadata access but not content access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: true, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: false, can_preview: false},
    },
    {
        desc: "subscribed user can preview private channel with history_public_to_subscribers",
        stream: {
            subscribed: true,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    // Guest user cases
    {
        desc: "subscribed guest has full access to public channel",
        stream: {
            subscribed: true,
            invite_only: false,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "unsubscribed guest is denied access to public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "unsubscribed guest has full access to web-public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: true,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    // Public channel cases
    {
        desc: "unsubscribed normal user has full access to public channel",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: false,
            history_public_to_subscribers: true,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "unsubscribed user cannot preview public channel without history_public_to_subscribers",
        stream: {
            subscribed: false,
            invite_only: false,
            is_web_public: false,
            history_public_to_subscribers: false,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: false},
    },
    // Group permission cases
    {
        desc: "user in can_add_subscribers_group has full access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_add_subscribers_group: me_group.id,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "user in can_subscribe_group has full access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_subscribe_group: me_group.id,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
    {
        desc: "user in can_administer_channel_group has metadata access only to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_administer_channel_group: me_group.id,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: false, can_preview: false},
    },
    {
        desc: "guest in can_administer_channel_group is denied metadata access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_administer_channel_group: me_group.id,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "guest in can_add_subscribers_group is denied access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_add_subscribers_group: me_group.id,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "guest in can_subscribe_group is denied access to private channel",
        stream: {
            subscribed: false,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_subscribe_group: me_group.id,
        },
        user: {is_admin: false, is_guest: true},
        spectator: false,
        expect: {has_metadata_access: false, has_content_access: false, can_preview: false},
    },
    {
        desc: "subscribed channel admin has content access to private channel",
        stream: {
            subscribed: true,
            invite_only: true,
            is_web_public: false,
            history_public_to_subscribers: true,
            can_administer_channel_group: me_group.id,
        },
        user: {is_admin: false, is_guest: false},
        spectator: false,
        expect: {has_metadata_access: true, has_content_access: true, can_preview: true},
    },
];

run_test("stream access table-driven test", ({override}) => {
    for (const test_case of access_cases) {
        const stream = {
            stream_id: 777,
            name: "test_stream",
            color: "red",
            is_muted: false,
            can_add_subscribers_group: nobody_group.id,
            can_administer_channel_group: nobody_group.id,
            can_subscribe_group: nobody_group.id,
            ...test_case.stream,
        };

        override(current_user, "user_id", me.user_id);
        override(current_user, "is_admin", test_case.user.is_admin);
        override(current_user, "is_guest", test_case.user.is_guest);
        page_params.is_spectator = test_case.spectator;

        assert.equal(
            stream_data.has_metadata_access(stream),
            test_case.expect.has_metadata_access,
            `${test_case.desc}: has_metadata_access`,
        );

        assert.equal(
            stream_data.has_content_access(stream),
            test_case.expect.has_content_access,
            `${test_case.desc}: has_content_access`,
        );

        assert.equal(
            stream_data.can_preview(stream),
            test_case.expect.can_preview,
            `${test_case.desc}: can_preview`,
        );
    }

    // Reset so future tests are unaffected
    page_params.is_spectator = false;
});

run_test("can_preview with content access override", ({override_rewire}) => {
    const social = {
        history_public_to_subscribers: true,
    };

    override_rewire(stream_data, "has_content_access", () => true);
    assert.equal(stream_data.can_preview(social), true);
    social.history_public_to_subscribers = false;
    assert.equal(stream_data.can_preview(social), false);
    social.history_public_to_subscribers = true;
    assert.equal(stream_data.can_preview(social), true);
    override_rewire(stream_data, "has_content_access", () => false);
    assert.equal(stream_data.can_preview(social), false);
});

run_test("can_toggle_subscription", ({override}) => {
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        can_add_subscribers_group: nobody_group.id,
        can_administer_channel_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };

    override(current_user, "user_id", me.user_id);

    override(page_params, "is_spectator", true);
    assert.equal(stream_data.can_toggle_subscription(social), false);

    override(page_params, "is_spectator", false);
    assert.equal(stream_data.can_toggle_subscription(social), true);

    override(current_user, "is_guest", true);
    assert.equal(stream_data.can_toggle_subscription(social), true);

    social.subscribed = false;
    assert.equal(stream_data.can_toggle_subscription(social), false);

    override(current_user, "is_guest", false);
    assert.equal(stream_data.can_toggle_subscription(social), true);

    social.invite_only = true;
    assert.equal(stream_data.can_toggle_subscription(social), false);

    override(current_user, "is_admin", true);
    assert.equal(stream_data.can_toggle_subscription(social), false);

    override(current_user, "is_admin", false);

    social.can_add_subscribers_group = me_group.id;
    assert.equal(stream_data.can_toggle_subscription(social), true);

    social.can_add_subscribers_group = nobody_group.id;
    assert.equal(stream_data.can_toggle_subscription(social), false);
    social.can_subscribe_group = me_group.id;
    assert.equal(stream_data.can_toggle_subscription(social), true);
});

run_test("can_archive_stream", ({override}) => {
    const social = {
        subscribed: false,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        can_add_subscribers_group: me_group.id,
        can_administer_channel_group: nobody_group.id,
        can_subscribe_group: me_group.id,
    };
    override(current_user, "user_id", me.user_id);

    override(current_user, "is_admin", true);
    social.is_archived = true;
    assert.equal(stream_data.can_archive_stream(social), false);

    social.is_archived = false;
    assert.equal(stream_data.can_archive_stream(social), true);

    override(current_user, "is_admin", false);
    assert.equal(stream_data.can_archive_stream(social), false);

    social.can_administer_channel_group = me_group.id;
    assert.equal(stream_data.can_archive_stream(social), true);
});

run_test("is_empty_topic_only_channel", ({override}) => {
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        topics_policy: "empty_topic_only",
    };
    stream_data.add_sub_for_tests(social);
    const scotland = {
        subscribed: true,
        color: "red",
        name: "scotland",
        stream_id: 3,
        topics_policy: "inherit",
    };
    override(realm, "realm_topics_policy", "allow_empty_topic");
    assert.equal(stream_data.is_empty_topic_only_channel(undefined), false);

    stream_data.add_sub_for_tests(scotland);
    override(current_user, "user_id", me.user_id);

    override(current_user, "is_admin", true);
    assert.equal(stream_data.is_empty_topic_only_channel(social.stream_id), true);
    assert.equal(stream_data.is_empty_topic_only_channel(scotland.stream_id), false);
});

test("set_max_channel_width_css_variable", async () => {
    const stream = {
        subscribed: true,
        color: "blue",
        name: "abc",
        stream_id: 500,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        can_add_subscribers_group: admins_group.id,
        can_administer_channel_group: admins_group.id,
        can_subscribe_group: admins_group.id,
    };
    stream_data.add_sub_for_tests(stream);

    const $measure_div = $("<div>");
    const $root = $(":root");

    $measure_div.css = () => $measure_div;
    $measure_div.get = () => ({
        getBoundingClientRect: () => ({width: $measure_div.text().length}),
    });
    $measure_div.remove = () => {};

    const set_property_calls = [];
    $root.css = (name, value) => {
        set_property_calls.push({name, value});
    };

    await stream_data.set_max_channel_width_css_variable();

    assert.equal(set_property_calls.length, 1);
    assert.equal(set_property_calls[0].name, "--longest-subscribed-channel-name-width");
    assert.equal(set_property_calls[0].value, "3px");
});
