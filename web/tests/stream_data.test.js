"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {current_user, page_params, realm, user_settings} = require("./lib/zpage_params");

// TODO: Remove after we enable support for
// web_public_streams in production.
page_params.development_environment = true;

const color_data = zrequire("color_data");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const settings_config = zrequire("settings_config");
const sub_store = zrequire("sub_store");
const stream_data = zrequire("stream_data");
const stream_settings_data = zrequire("stream_settings_data");
const user_groups = zrequire("user_groups");

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

// set up user data
const admins_group = {
    name: "Admins",
    id: 1,
    members: new Set([1]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};

const moderators_group = {
    name: "Members",
    id: 2,
    members: new Set([2]),
    is_system_group: true,
    direct_subgroup_ids: new Set([1]),
};

function test(label, f) {
    run_test(label, (helpers) => {
        current_user.is_admin = false;
        page_params.realm_users = [];
        current_user.is_guest = false;
        people.init();
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);
        stream_data.clear_subscriptions();
        user_groups.initialize({realm_user_groups: [admins_group, moderators_group]});
        f(helpers);
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
    };
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
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
        subscribed: false,
        color: "yellow",
        name: "web_public_stream",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: true,
        is_web_public: true,
    };
    stream_data.add_sub(denmark);
    stream_data.add_sub(social);
    stream_data.add_sub(web_public_stream);
    assert.ok(stream_data.all_subscribed_streams_are_in_home_view());
    stream_data.add_sub(test);
    assert.ok(!stream_data.all_subscribed_streams_are_in_home_view());

    assert.equal(stream_data.get_sub("denmark"), denmark);
    assert.equal(stream_data.get_sub("Social"), social);
    assert.equal(stream_data.get_sub("web_public_stream"), web_public_stream);
    assert.ok(stream_data.is_web_public(web_public_stream.stream_id));

    assert.deepEqual(stream_data.home_view_stream_names(), ["social"]);
    assert.deepEqual(stream_data.subscribed_streams(), ["social", "test"]);
    assert.deepEqual(stream_data.get_colors(), ["red", "yellow"]);
    assert.deepEqual(stream_data.subscribed_stream_ids(), [social.stream_id, test.stream_id]);

    assert.ok(stream_data.is_subscribed_by_name("social"));
    assert.ok(stream_data.is_subscribed_by_name("Social"));
    assert.ok(!stream_data.is_subscribed_by_name("Denmark"));
    assert.ok(!stream_data.is_subscribed_by_name("Rome"));

    assert.equal(stream_data.get_stream_privacy_policy(test.stream_id), "public");
    assert.equal(stream_data.get_stream_privacy_policy(social.stream_id), "invite-only");
    assert.equal(
        stream_data.get_stream_privacy_policy(denmark.stream_id),
        "invite-only-public-history",
    );
    assert.equal(stream_data.get_stream_privacy_policy(web_public_stream.stream_id), "web-public");
    assert.ok(stream_data.is_web_public_by_stream_name(web_public_stream.name));
    assert.ok(!stream_data.is_web_public_by_stream_name(social.name));
    assert.ok(!stream_data.is_web_public_by_stream_name("unknown"));

    assert.ok(stream_data.is_invite_only_by_stream_id(social.stream_id));
    // Unknown stream id
    assert.ok(!stream_data.is_invite_only_by_stream_id(1000));

    assert.equal(stream_data.get_color(social.stream_id), "red");
    assert.equal(stream_data.get_color(undefined), "#c2c2c2");
    assert.equal(stream_data.get_color(1234567), "#c2c2c2");

    assert.equal(stream_data.get_name("denMARK"), "Denmark");
    assert.equal(stream_data.get_name("unknown Stream"), "unknown Stream");

    assert.ok(!stream_data.is_muted(social.stream_id));
    assert.ok(stream_data.is_muted(denmark.stream_id));

    assert.equal(sub_store.maybe_get_stream_name(), undefined);
    assert.equal(sub_store.maybe_get_stream_name(social.stream_id), "social");
    assert.equal(sub_store.maybe_get_stream_name(42), undefined);

    stream_data.set_realm_default_streams([denmark]);
    assert.ok(stream_data.is_default_stream_id(denmark.stream_id));
    assert.ok(!stream_data.is_default_stream_id(social.stream_id));
    assert.ok(!stream_data.is_default_stream_id(999999));

    assert.equal(stream_data.slug_to_name("2-social"), "social");
    assert.equal(stream_data.slug_to_name("2-whatever"), "social");
    assert.equal(stream_data.slug_to_name("2"), "social");

    // legacy
    assert.equal(stream_data.slug_to_name("25-or-6-to-4"), "25-or-6-to-4");
    assert.equal(stream_data.slug_to_name("2something"), "2something");

    assert.equal(stream_data.slug_to_name("99-whatever"), "99-whatever");
    assert.equal(stream_data.slug_to_name("99whatever"), "99whatever");

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
                stream_post_policy: 2,
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
    ]);
});

test("get_streams_for_user", () => {
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
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
    };
    const test = {
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: true,
    };
    const world = {
        color: "blue",
        name: "world",
        stream_id: 4,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
    };
    const errors = {
        color: "green",
        name: "errors",
        stream_id: 5,
        is_muted: false,
        invite_only: false,
        history_public_to_subscribers: false,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
    };
    const subs = [denmark, social, test, world, errors];
    for (const sub of subs) {
        stream_data.add_sub(sub);
    }

    peer_data.set_subscribers(denmark.stream_id, [me.user_id, test_user.user_id]);
    peer_data.set_subscribers(social.stream_id, [test_user.user_id]);
    peer_data.set_subscribers(test.stream_id, [test_user.user_id]);
    peer_data.set_subscribers(world.stream_id, [me.user_id]);

    realm.realm_invite_to_stream_policy = settings_config.common_policy_values.by_admins_only.code;
    assert.deepEqual(stream_data.get_streams_for_user(me.user_id).can_subscribe, [social, errors]);

    // test_user is subscribed to all three streams, but current user (me)
    // gets only two because of subscriber visibility policy of stream:
    // #denmark: current user is subscribed to it so he can see its subscribers.
    // #social: current user is can get this as neither this is invite only nor current
    //          user is a guest.
    // #test: current user is no longer subscribed to a private stream, so
    //        he cannot see whether test_user is subscribed to it.
    assert.deepEqual(stream_data.get_streams_for_user(test_user.user_id).subscribed, [
        denmark,
        social,
    ]);
    assert.deepEqual(stream_data.get_streams_for_user(test_user.user_id).can_subscribe, []);
    // Verify can subscribe if we're an administrator.
    current_user.is_admin = true;
    assert.deepEqual(stream_data.get_streams_for_user(test_user.user_id).can_subscribe, [
        world,
        errors,
    ]);
    current_user.is_admin = false;

    realm.realm_invite_to_stream_policy = settings_config.common_policy_values.by_members.code;
    assert.deepEqual(stream_data.get_streams_for_user(test_user.user_id).can_subscribe, [
        world,
        errors,
    ]);
});

test("renames", () => {
    const id = 42;
    let sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: id,
    };
    stream_data.add_sub(sub);
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

test("admin_options", () => {
    function make_sub() {
        const sub = {
            subscribed: false,
            color: "blue",
            name: "stream_to_admin",
            stream_id: 1,
            is_muted: true,
            invite_only: false,
            can_remove_subscribers_group: admins_group.id,
            date_created: 1691057093,
            creator_id: null,
        };
        stream_data.add_sub(sub);
        return sub;
    }

    function is_realm_admin(sub) {
        return stream_settings_data.get_sub_for_settings(sub).is_realm_admin;
    }

    function can_change_stream_permissions(sub) {
        return stream_settings_data.get_sub_for_settings(sub).can_change_stream_permissions;
    }

    // non-admins can't do anything
    current_user.is_admin = false;
    let sub = make_sub();
    assert.ok(!is_realm_admin(sub));
    assert.ok(!can_change_stream_permissions(sub));

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, "blue");

    // the remaining cases are for admin users
    current_user.is_admin = true;

    // admins can make public streams become private
    sub = make_sub();
    assert.ok(is_realm_admin(sub));
    assert.ok(can_change_stream_permissions(sub));

    // admins can only make private streams become public
    // if they are subscribed
    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = false;
    assert.ok(is_realm_admin(sub));
    assert.ok(!can_change_stream_permissions(sub));

    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = true;
    assert.ok(is_realm_admin(sub));
    assert.ok(can_change_stream_permissions(sub));
});

test("stream_settings", () => {
    const cinnamon = {
        stream_id: 1,
        name: "c",
        color: "cinnamon",
        subscribed: true,
        invite_only: false,
        can_remove_subscribers_group: admins_group.id,
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
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
        message_retention_days: 10,
        can_remove_subscribers_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    stream_data.add_sub(cinnamon);
    stream_data.add_sub(amber);
    stream_data.add_sub(blue);

    let sub_rows = stream_settings_data.get_streams_for_settings_page();
    assert.equal(sub_rows[0].color, "blue");
    assert.equal(sub_rows[1].color, "amber");
    assert.equal(sub_rows[2].color, "cinnamon");

    sub_rows = stream_data.get_streams_for_admin();
    assert.equal(sub_rows[0].name, "a");
    assert.equal(sub_rows[1].name, "b");
    assert.equal(sub_rows[2].name, "c");
    assert.equal(sub_rows[0].invite_only, true);
    assert.equal(sub_rows[1].invite_only, false);
    assert.equal(sub_rows[2].invite_only, false);

    assert.equal(sub_rows[0].history_public_to_subscribers, true);
    assert.equal(
        sub_rows[0].stream_post_policy === settings_config.stream_post_policy_values.admins.code,
        true,
    );
    assert.equal(sub_rows[0].message_retention_days, 10);

    const sub = stream_data.get_sub("a");
    stream_data.update_stream_privacy(sub, {
        invite_only: false,
        history_public_to_subscribers: false,
    });
    stream_data.update_stream_post_policy(sub, 1);
    stream_data.update_message_retention_setting(sub, -1);
    stream_data.update_can_remove_subscribers_group_id(sub, moderators_group.id);
    assert.equal(sub.invite_only, false);
    assert.equal(sub.history_public_to_subscribers, false);
    assert.equal(sub.stream_post_policy, settings_config.stream_post_policy_values.everyone.code);
    assert.equal(sub.message_retention_days, -1);
    assert.equal(sub.can_remove_subscribers_group, moderators_group.id);

    // For guest user only retrieve subscribed streams
    sub_rows = stream_settings_data.get_updated_unsorted_subs();
    assert.equal(sub_rows.length, 3);
    current_user.is_guest = true;
    sub_rows = stream_settings_data.get_updated_unsorted_subs();
    assert.equal(sub_rows[0].name, "c");
    assert.equal(sub_rows[1].name, "a");
    assert.equal(sub_rows.length, 2);
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

    stream_data.set_realm_default_streams([announce, general]);
    stream_data.add_sub(announce);
    stream_data.add_sub(public_stream);
    stream_data.add_sub(private_stream);
    stream_data.add_sub(general);

    const names = stream_data.get_non_default_stream_names();
    assert.deepEqual(names.sort(), [{name: "public", unique_id: "102"}]);

    const default_stream_ids = stream_data.get_default_stream_ids();
    assert.deepEqual(default_stream_ids.sort(), [announce.stream_id, general.stream_id]);
});

test("delete_sub", () => {
    const canada = {
        stream_id: 101,
        name: "Canada",
        subscribed: true,
    };

    stream_data.add_sub(canada);

    assert.ok(stream_data.is_subscribed_by_name("Canada"));
    assert.equal(stream_data.get_sub("Canada").stream_id, canada.stream_id);
    assert.equal(sub_store.get(canada.stream_id).name, "Canada");

    stream_data.delete_sub(canada.stream_id);
    assert.ok(!stream_data.is_subscribed_by_name("Canada"));
    assert.ok(!stream_data.get_sub("Canada"));
    assert.ok(!sub_store.get(canada.stream_id));

    blueslip.expect("warn", "Failed to archive stream 99999");
    stream_data.delete_sub(99999);
});

test("notifications", () => {
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
    stream_data.add_sub(india);

    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    user_settings.enable_stream_desktop_notifications = true;
    user_settings.enable_stream_audible_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    user_settings.enable_stream_desktop_notifications = false;
    user_settings.enable_stream_audible_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = true;
    india.audible_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = false;
    india.audible_notifications = false;
    user_settings.enable_stream_desktop_notifications = true;
    user_settings.enable_stream_audible_notifications = true;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert.ok(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    user_settings.wildcard_mentions_notify = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    user_settings.wildcard_mentions_notify = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    india.wildcard_mentions_notify = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    user_settings.wildcard_mentions_notify = true;
    india.wildcard_mentions_notify = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));

    user_settings.enable_stream_push_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    user_settings.enable_stream_push_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "push_notifications"));
    india.push_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    user_settings.enable_stream_push_notifications = true;
    india.push_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "push_notifications"));

    user_settings.enable_stream_email_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    user_settings.enable_stream_email_notifications = false;
    assert.ok(!stream_data.receives_notifications(india.stream_id, "email_notifications"));
    india.email_notifications = true;
    assert.ok(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    user_settings.enable_stream_email_notifications = true;
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
    stream_data.add_sub(canada);

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
    stream_data.add_sub(antarctica);

    user_settings.enable_stream_desktop_notifications = true;
    user_settings.enable_stream_audible_notifications = true;
    user_settings.enable_stream_email_notifications = false;
    user_settings.enable_stream_push_notifications = false;
    user_settings.wildcard_mentions_notify = true;

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

test("is_muted", () => {
    stream_data.add_sub(tony);
    stream_data.add_sub(jazy);
    assert.ok(!stream_data.is_stream_muted_by_name("tony"));
    assert.ok(stream_data.is_stream_muted_by_name("jazy"));
    assert.ok(stream_data.is_stream_muted_by_name("EEXISTS"));
});

test("is_new_stream_announcements_stream_muted", () => {
    stream_data.add_sub(tony);
    stream_data.add_sub(jazy);

    realm.realm_new_stream_announcements_stream_id = tony.stream_id;
    assert.ok(!stream_data.is_new_stream_announcements_stream_muted());

    realm.realm_new_stream_announcements_stream_id = jazy.stream_id;
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
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
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
    stream_data.add_sub(denmark);
    stream_data.add_sub(social);
    stream_data.add_sub(test);
    stream_data.add_sub(web_public_stream);

    assert.deepEqual(stream_data.muted_stream_ids(), [1, 3]);
});

test("realm_has_new_stream_announcements_stream", () => {
    realm.realm_new_stream_announcements_stream_id = 10;
    assert.ok(stream_data.realm_has_new_stream_announcements_stream());
    realm.realm_new_stream_announcements_stream_id = -1;
    assert.ok(!stream_data.realm_has_new_stream_announcements_stream());
});

test("remove_default_stream", () => {
    const remove_me = {
        stream_id: 674,
        name: "remove_me",
        subscribed: false,
        is_muted: true,
    };

    stream_data.add_sub(remove_me);
    stream_data.set_realm_default_streams([remove_me]);
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
    };

    const canada = {
        name: "Canada",
        subscribed: true,
    };

    const antarctica = {
        stream_id: 103,
        name: "Antarctica",
        subscribed: true,
        color: "#76ce90",
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

test("creator_id", () => {
    people.add_active_user(test_user);

    // When creator id is not a valid user id
    assert.throws(() => stream_data.maybe_get_creator_details(-1), {
        name: "Error",
        message: "Unknown user_id in get_by_user_id: -1",
    });

    // When there is no creator
    assert.equal(stream_data.maybe_get_creator_details(null), undefined);

    const creator_details = people.get_by_user_id(test_user.user_id);
    assert.deepStrictEqual(
        stream_data.maybe_get_creator_details(test_user.user_id),
        creator_details,
    );
});

test("initialize", () => {
    function get_params() {
        const params = {};

        params.subscriptions = [
            {
                name: "subscriptions",
                stream_id: 2001,
            },
        ];

        params.unsubscribed = [
            {
                name: "unsubscribed",
                stream_id: 2002,
            },
        ];

        params.never_subscribed = [
            {
                name: "never_subscribed",
                stream_id: 2003,
            },
        ];

        params.realm_default_streams = [];

        return params;
    }

    function initialize() {
        stream_data.initialize(get_params());
    }

    realm.realm_new_stream_announcements_stream_id = -1;

    initialize();

    const stream_names = new Set(stream_data.get_streams_for_admin().map((elem) => elem.name));
    assert.ok(stream_names.has("subscriptions"));
    assert.ok(stream_names.has("unsubscribed"));
    assert.ok(stream_names.has("never_subscribed"));
    assert.equal(stream_data.get_new_stream_announcements_stream(), "");

    // Simulate a private stream the user isn't subscribed to
    realm.realm_new_stream_announcements_stream_id = 89;
    initialize();
    assert.equal(stream_data.get_new_stream_announcements_stream(), "");

    // Now actually subscribe the user to the stream
    initialize();
    const foo = {
        name: "foo",
        stream_id: 89,
    };

    stream_data.add_sub(foo);
    initialize();
    assert.equal(stream_data.get_new_stream_announcements_stream(), "foo");
});

test("edge_cases", () => {
    const bad_stream_ids = [555555, 99999];

    // just make sure we don't explode
    stream_settings_data.sort_for_stream_settings(bad_stream_ids);
});

test("get_invite_stream_data", () => {
    // add default stream
    const orie = {
        name: "Orie",
        stream_id: 320,
        invite_only: false,
        subscribed: true,
        is_web_public: false,
    };

    people.init();

    stream_data.add_sub(orie);
    stream_data.set_realm_default_streams([orie]);

    const expected_list = [
        {
            name: "Orie",
            stream_id: 320,
            invite_only: false,
            default_stream: true,
            is_web_public: false,
        },
    ];
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    const inviter = {
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        subscribed: true,
        is_web_public: false,
    };
    stream_data.add_sub(inviter);

    expected_list.push({
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        default_stream: false,
        is_web_public: false,
    });
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);
});

test("can_post_messages_in_stream", () => {
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
    };
    current_user.is_admin = false;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    current_user.is_admin = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    social.stream_post_policy = settings_config.stream_post_policy_values.moderators.code;
    current_user.is_moderator = false;
    current_user.is_admin = false;

    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    current_user.is_moderator = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    social.stream_post_policy = settings_config.stream_post_policy_values.non_new_members.code;
    current_user.is_moderator = false;
    me.date_joined = new Date(Date.now());
    realm.realm_waiting_period_threshold = 10;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    me.date_joined = new Date(Date.now() - 20 * 86400000);
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    current_user.is_guest = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);

    social.stream_post_policy = settings_config.stream_post_policy_values.everyone.code;
    assert.equal(stream_data.can_post_messages_in_stream(social), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.can_post_messages_in_stream(social), false);
});

test("can_unsubscribe_others", () => {
    const admin_user_id = 1;
    const moderator_user_id = 2;
    const member_user_id = 3;

    const admins = {
        name: "Admins",
        id: 1,
        members: new Set([admin_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    const moderators = {
        name: "Moderators",
        id: 2,
        members: new Set([moderator_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
    };
    const all = {
        name: "Everyone",
        id: 3,
        members: new Set([member_user_id]),
        is_system_group: true,
        direct_subgroup_ids: new Set([2]),
    };
    const nobody = {
        name: "Nobody",
        id: 4,
        members: new Set([]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({realm_user_groups: [admins, moderators, all, nobody]});

    const sub = {
        name: "Denmark",
        subscribed: true,
        color: "red",
        stream_id: 1,
        can_remove_subscribers_group: admins.id,
    };
    stream_data.add_sub(sub);

    people.initialize_current_user(admin_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    people.initialize_current_user(moderator_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);

    sub.can_remove_subscribers_group = moderators.id;
    people.initialize_current_user(admin_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    people.initialize_current_user(moderator_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    people.initialize_current_user(member_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), false);

    sub.can_remove_subscribers_group = all.id;
    people.initialize_current_user(admin_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    people.initialize_current_user(moderator_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    people.initialize_current_user(member_user_id);
    assert.equal(stream_data.can_unsubscribe_others(sub), true);

    // Even with the nobody system group, admins can still unsubscribe others.
    sub.can_remove_subscribers_group = nobody.id;
    current_user.is_admin = true;
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    current_user.is_admin = false;
    assert.equal(stream_data.can_unsubscribe_others(sub), false);

    // This isn't a real state, but we want coverage on !can_view_subscribers.
    sub.subscribed = false;
    sub.invite_only = true;
    current_user.is_admin = true;
    assert.equal(stream_data.can_unsubscribe_others(sub), true);
    current_user.is_admin = false;
    assert.equal(stream_data.can_unsubscribe_others(sub), false);
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
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
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
    stream_data.add_sub(denmark);
    stream_data.add_sub(social);
    stream_data.add_sub(web_public_stream);
    stream_data.add_sub(test);

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
                stream_post_policy: 2,
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

test("can_access_stream_email", () => {
    const social = {
        subscribed: true,
        color: "red",
        name: "social",
        stream_id: 2,
        is_muted: false,
        invite_only: true,
        history_public_to_subscribers: false,
    };
    current_user.is_admin = false;
    assert.equal(stream_data.can_access_stream_email(social), true);

    current_user.is_admin = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.subscribed = false;
    assert.equal(stream_data.can_access_stream_email(social), false);

    social.invite_only = false;
    assert.equal(stream_data.can_access_stream_email(social), true);

    current_user.is_admin = false;
    assert.equal(stream_data.can_access_stream_email(social), true);

    current_user.is_guest = true;
    assert.equal(stream_data.can_access_stream_email(social), false);

    social.subscribed = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.is_web_public = true;
    assert.equal(stream_data.can_access_stream_email(social), true);

    social.subscribed = false;
    assert.equal(stream_data.can_access_stream_email(social), true);

    page_params.is_spectator = true;
    assert.equal(stream_data.can_access_stream_email(social), false);
});
