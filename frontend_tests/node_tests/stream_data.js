"use strict";

const _ = require("lodash");

set_global("page_params", {
    is_admin: false,
    realm_users: [],
    is_guest: false,
});

set_global("$", () => {});

set_global("document", null);
global.stub_out_jquery();

zrequire("color_data");
zrequire("hash_util");
zrequire("stream_topic_history");
const people = zrequire("people");
zrequire("stream_color");
zrequire("stream_data");
zrequire("FetchStatus", "js/fetch_status");
zrequire("Filter", "js/filter");
zrequire("MessageListData", "js/message_list_data");
zrequire("MessageListView", "js/message_list_view");
zrequire("message_list");
const settings_config = zrequire("settings_config");

const me = {
    email: "me@zulip.com",
    full_name: "Current User",
    user_id: 100,
};

// set up user data
people.add_active_user(me);
people.initialize_current_user(me.user_id);

function contains_sub(subs, sub) {
    return subs.some((s) => s.name === sub.name);
}

run_test("basics", () => {
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
        stream_post_policy: stream_data.stream_post_policy_values.admins.code,
    };
    const test = {
        subscribed: true,
        color: "yellow",
        name: "test",
        stream_id: 3,
        is_muted: true,
        invite_only: false,
    };
    stream_data.add_sub(denmark);
    stream_data.add_sub(social);
    assert(stream_data.all_subscribed_streams_are_in_home_view());
    stream_data.add_sub(test);
    assert(!stream_data.all_subscribed_streams_are_in_home_view());

    assert.equal(stream_data.get_sub("denmark"), denmark);
    assert.equal(stream_data.get_sub("Social"), social);

    assert.deepEqual(stream_data.home_view_stream_names(), ["social"]);
    assert.deepEqual(stream_data.subscribed_streams(), ["social", "test"]);
    assert.deepEqual(stream_data.get_colors(), ["red", "yellow"]);
    assert.deepEqual(stream_data.subscribed_stream_ids(), [social.stream_id, test.stream_id]);

    assert(stream_data.is_subscribed("social"));
    assert(stream_data.is_subscribed("Social"));
    assert(!stream_data.is_subscribed("Denmark"));
    assert(!stream_data.is_subscribed("Rome"));

    assert(stream_data.get_stream_privacy_policy(test.stream_id), "public");
    assert(stream_data.get_stream_privacy_policy(social.stream_id), "invite-only");
    assert(stream_data.get_stream_privacy_policy(denmark.stream_id), "invite-only-public-history");

    assert(stream_data.get_invite_only("social"));
    assert(!stream_data.get_invite_only("unknown"));

    assert.equal(stream_data.get_color("social"), "red");
    assert.equal(stream_data.get_color("unknown"), global.stream_color.default_color);

    assert.equal(stream_data.get_name("denMARK"), "Denmark");
    assert.equal(stream_data.get_name("unknown Stream"), "unknown Stream");

    assert(!stream_data.is_muted(social.stream_id));
    assert(stream_data.is_muted(denmark.stream_id));

    assert.equal(stream_data.maybe_get_stream_name(), undefined);
    assert.equal(stream_data.maybe_get_stream_name(social.stream_id), "social");
    assert.equal(stream_data.maybe_get_stream_name(42), undefined);

    stream_data.set_realm_default_streams([denmark]);
    assert(stream_data.is_default_stream_id(denmark.stream_id));
    assert(!stream_data.is_default_stream_id(social.stream_id));
    assert(!stream_data.is_default_stream_id(999999));

    assert.equal(stream_data.slug_to_name("2-social"), "social");
    assert.equal(stream_data.slug_to_name("2-whatever"), "social");
    assert.equal(stream_data.slug_to_name("2"), "social");

    assert.equal(stream_data.slug_to_name("25-or-6-to-4"), "25-or-6-to-4");
});

run_test("renames", () => {
    stream_data.clear_subscriptions();
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
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, "red");

    stream_data.rename_sub(sub, "Sweden");
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, "red");
    assert.equal(sub.name, "Sweden");

    sub = stream_data.get_sub("Denmark");
    assert.equal(sub, undefined);

    sub = stream_data.get_sub_by_name("Denmark");
    assert.equal(sub.name, "Sweden");

    const actual_id = stream_data.get_stream_id("Denmark");
    assert.equal(actual_id, 42);
});

run_test("unsubscribe", () => {
    stream_data.clear_subscriptions();

    let sub = {name: "devel", subscribed: false, stream_id: 1};

    // set up our subscription
    stream_data.add_sub(sub);
    sub.subscribed = true;
    stream_data.set_subscribers(sub, [me.user_id]);

    // ensure our setup is accurate
    assert(stream_data.is_subscribed("devel"));

    // DO THE UNSUBSCRIBE HERE
    stream_data.unsubscribe_myself(sub);
    assert(!sub.subscribed);
    assert(!stream_data.is_subscribed("devel"));
    assert(!contains_sub(stream_data.subscribed_subs(), sub));
    assert(contains_sub(stream_data.unsubscribed_subs(), sub));

    // make sure subsequent calls work
    sub = stream_data.get_sub("devel");
    assert(!sub.subscribed);
});

run_test("subscribers", () => {
    stream_data.clear_subscriptions();
    let sub = {name: "Rome", subscribed: true, stream_id: 1};

    stream_data.add_sub(sub);

    const fred = {
        email: "fred@zulip.com",
        full_name: "Fred",
        user_id: 101,
    };
    const not_fred = {
        email: "not_fred@zulip.com",
        full_name: "Not Fred",
        user_id: 102,
    };
    const george = {
        email: "george@zulip.com",
        full_name: "George",
        user_id: 103,
    };
    people.add_active_user(fred);
    people.add_active_user(not_fred);
    people.add_active_user(george);

    function potential_subscriber_ids() {
        const users = stream_data.potential_subscribers(sub);
        return users.map((u) => u.user_id).sort();
    }

    assert.deepEqual(potential_subscriber_ids(), [
        me.user_id,
        fred.user_id,
        not_fred.user_id,
        george.user_id,
    ]);

    stream_data.set_subscribers(sub, [me.user_id, fred.user_id, george.user_id]);
    stream_data.update_calculated_fields(sub);
    assert(stream_data.is_user_subscribed(sub.stream_id, me.user_id));
    assert(stream_data.is_user_subscribed(sub.stream_id, fred.user_id));
    assert(stream_data.is_user_subscribed(sub.stream_id, george.user_id));
    assert(!stream_data.is_user_subscribed(sub.stream_id, not_fred.user_id));

    assert.deepEqual(potential_subscriber_ids(), [not_fred.user_id]);

    stream_data.set_subscribers(sub, []);

    const brutus = {
        email: "brutus@zulip.com",
        full_name: "Brutus",
        user_id: 104,
    };
    people.add_active_user(brutus);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));

    // add
    let ok = stream_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert(ok);
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    sub = stream_data.get_sub("Rome");
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);
    const sub_email = "Rome:214125235@zulipdev.com:9991";
    stream_data.update_stream_email_address(sub, sub_email);
    assert.equal(sub.email_address, sub_email);

    // verify that adding an already-added subscriber is a noop
    stream_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    sub = stream_data.get_sub("Rome");
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 1);

    // remove
    ok = stream_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert(ok);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    sub = stream_data.get_sub("Rome");
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // verify that checking subscription with undefined user id

    blueslip.expect("warn", "Undefined user_id passed to function is_user_subscribed");
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, undefined), undefined);

    // Verify noop for bad stream when removing subscriber
    const bad_stream_id = 999999;
    blueslip.expect(
        "warn",
        "We got a remove_subscriber call for a non-existent stream " + bad_stream_id,
    );
    ok = stream_data.remove_subscriber(bad_stream_id, brutus.user_id);
    assert(!ok);

    // verify that removing an already-removed subscriber is a noop
    blueslip.expect("warn", "We tried to remove invalid subscriber: 104");
    ok = stream_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert(!ok);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    sub = stream_data.get_sub("Rome");
    stream_data.update_subscribers_count(sub);
    assert.equal(sub.subscriber_count, 0);

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.set_subscribers(sub);
    stream_data.add_sub(sub);
    stream_data.add_subscriber(sub.stream_id, brutus.user_id);
    sub.subscribed = true;
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));

    // Verify that we noop and don't crash when unsubscribed.
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    ok = stream_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert(ok);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), true);
    stream_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), false);
    stream_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), true);

    blueslip.expect(
        "warn",
        "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        2,
    );
    sub.invite_only = true;
    stream_data.update_calculated_fields(sub);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), undefined);
    stream_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), undefined);

    // Verify that we don't crash and return false for a bad stream.
    blueslip.expect("warn", "We got an add_subscriber call for a non-existent stream.");
    ok = stream_data.add_subscriber(9999999, brutus.user_id);
    assert(!ok);

    // Verify that we don't crash and return false for a bad user id.
    blueslip.expect("error", "Unknown user_id in get_by_user_id: 9999999");
    blueslip.expect("error", "We tried to add invalid subscriber: 9999999");
    ok = stream_data.add_subscriber(sub.stream_id, 9999999);
    assert(!ok);
});

run_test("is_active", () => {
    stream_data.clear_subscriptions();

    let sub;

    page_params.demote_inactive_streams =
        settings_config.demote_inactive_streams_values.automatic.code;
    stream_data.set_filter_out_inactives();

    sub = {name: "pets", subscribed: false, stream_id: 111};
    stream_data.add_sub(sub);

    assert(stream_data.is_active(sub));

    stream_data.subscribe_myself(sub);
    assert(stream_data.is_active(sub));

    assert(contains_sub(stream_data.subscribed_subs(), sub));
    assert(!contains_sub(stream_data.unsubscribed_subs(), sub));

    stream_data.unsubscribe_myself(sub);
    assert(stream_data.is_active(sub));

    sub.pin_to_top = true;
    assert(stream_data.is_active(sub));
    sub.pin_to_top = false;

    const opts = {
        stream_id: 222,
        message_id: 108,
        topic_name: "topic2",
    };
    stream_topic_history.add_message(opts);

    assert(stream_data.is_active(sub));

    page_params.demote_inactive_streams =
        settings_config.demote_inactive_streams_values.always.code;
    stream_data.set_filter_out_inactives();

    sub = {name: "pets", subscribed: false, stream_id: 111};
    stream_data.add_sub(sub);

    assert(!stream_data.is_active(sub));

    sub.pin_to_top = true;
    assert(stream_data.is_active(sub));
    sub.pin_to_top = false;

    stream_data.subscribe_myself(sub);
    assert(stream_data.is_active(sub));

    stream_data.unsubscribe_myself(sub);
    assert(!stream_data.is_active(sub));

    sub = {name: "lunch", subscribed: false, stream_id: 222};
    stream_data.add_sub(sub);

    assert(stream_data.is_active(sub));

    stream_topic_history.add_message(opts);

    assert(stream_data.is_active(sub));

    page_params.demote_inactive_streams = settings_config.demote_inactive_streams_values.never.code;
    stream_data.set_filter_out_inactives();

    sub = {name: "pets", subscribed: false, stream_id: 111};
    stream_data.add_sub(sub);

    assert(stream_data.is_active(sub));

    stream_data.subscribe_myself(sub);
    assert(stream_data.is_active(sub));

    stream_data.unsubscribe_myself(sub);
    assert(stream_data.is_active(sub));

    sub.pin_to_top = true;
    assert(stream_data.is_active(sub));

    stream_topic_history.add_message(opts);

    assert(stream_data.is_active(sub));
});

run_test("admin_options", () => {
    function make_sub() {
        const sub = {
            subscribed: false,
            color: "blue",
            name: "stream_to_admin",
            stream_id: 1,
            is_muted: true,
            invite_only: false,
        };
        stream_data.add_sub(sub);
        return sub;
    }

    // non-admins can't do anything
    global.page_params.is_admin = false;
    let sub = make_sub();
    stream_data.update_calculated_fields(sub);
    assert(!sub.is_admin);
    assert(!sub.can_change_stream_permissions);

    // just a sanity check that we leave "normal" fields alone
    assert.equal(sub.color, "blue");

    // the remaining cases are for admin users
    global.page_params.is_admin = true;

    // admins can make public streams become private
    sub = make_sub();
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(sub.can_change_stream_permissions);

    // admins can only make private streams become public
    // if they are subscribed
    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(!sub.can_change_stream_permissions);

    sub = make_sub();
    sub.invite_only = true;
    sub.subscribed = true;
    stream_data.update_calculated_fields(sub);
    assert(sub.is_admin);
    assert(sub.can_change_stream_permissions);
});

run_test("stream_settings", () => {
    const cinnamon = {
        stream_id: 1,
        name: "c",
        color: "cinnamon",
        subscribed: true,
        invite_only: false,
    };

    const blue = {
        stream_id: 2,
        name: "b",
        color: "blue",
        subscribed: false,
        invite_only: false,
    };

    const amber = {
        stream_id: 3,
        name: "a",
        color: "amber",
        subscribed: true,
        invite_only: true,
        history_public_to_subscribers: true,
        stream_post_policy: stream_data.stream_post_policy_values.admins.code,
        message_retention_days: 10,
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub(cinnamon);
    stream_data.add_sub(amber);
    stream_data.add_sub(blue);

    let sub_rows = stream_data.get_streams_for_settings_page();
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
        sub_rows[0].stream_post_policy === stream_data.stream_post_policy_values.admins.code,
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
    stream_data.update_calculated_fields(sub);
    assert.equal(sub.invite_only, false);
    assert.equal(sub.history_public_to_subscribers, false);
    assert.equal(sub.stream_post_policy, stream_data.stream_post_policy_values.everyone.code);
    assert.equal(sub.message_retention_days, -1);

    // For guest user only retrieve subscribed streams
    sub_rows = stream_data.get_updated_unsorted_subs();
    assert.equal(sub_rows.length, 3);
    global.page_params.is_guest = true;
    sub_rows = stream_data.get_updated_unsorted_subs();
    assert.equal(sub_rows[0].name, "c");
    assert.equal(sub_rows[1].name, "a");
    assert.equal(sub_rows.length, 2);
});

run_test("default_stream_names", () => {
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

    stream_data.clear_subscriptions();
    stream_data.set_realm_default_streams([announce, general]);
    stream_data.add_sub(announce);
    stream_data.add_sub(public_stream);
    stream_data.add_sub(private_stream);
    stream_data.add_sub(general);

    const names = stream_data.get_non_default_stream_names();
    assert.deepEqual(names.sort(), ["private", "public"]);

    const default_stream_ids = stream_data.get_default_stream_ids();
    assert.deepEqual(default_stream_ids.sort(), [announce.stream_id, general.stream_id]);
});

run_test("delete_sub", () => {
    const canada = {
        stream_id: 101,
        name: "Canada",
        subscribed: true,
    };

    stream_data.clear_subscriptions();
    stream_data.add_sub(canada);

    assert(stream_data.is_subscribed("Canada"));
    assert(stream_data.get_sub("Canada").stream_id, canada.stream_id);
    assert(stream_data.get_sub_by_id(canada.stream_id).name, "Canada");

    stream_data.delete_sub(canada.stream_id);
    assert(!stream_data.is_subscribed("Canada"));
    assert(!stream_data.get_sub("Canada"));
    assert(!stream_data.get_sub_by_id(canada.stream_id));

    blueslip.expect("warn", "Failed to delete stream 99999");
    stream_data.delete_sub(99999);
});

run_test("get_subscriber_count", () => {
    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
    };
    stream_data.clear_subscriptions();

    blueslip.expect("warn", "We got a get_subscriber_count count call for a non-existent stream.");
    assert.equal(stream_data.get_subscriber_count(india.stream_id), undefined);

    stream_data.add_sub(india);
    assert.equal(stream_data.get_subscriber_count(india.stream_id), 0);

    const fred = {
        email: "fred@zulip.com",
        full_name: "Fred",
        user_id: 101,
    };
    people.add_active_user(fred);
    stream_data.add_subscriber(india.stream_id, 102);
    assert.equal(stream_data.get_subscriber_count(india.stream_id), 1);
    const george = {
        email: "george@zulip.com",
        full_name: "George",
        user_id: 103,
    };
    people.add_active_user(george);
    stream_data.add_subscriber(india.stream_id, 103);
    assert.equal(stream_data.get_subscriber_count(india.stream_id), 2);

    const sub = stream_data.get_sub_by_name("India");
    delete sub.subscribers;
    assert.deepStrictEqual(stream_data.get_subscriber_count(india.stream_id), 0);
});

run_test("notifications", () => {
    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
        invite_only: false,
        is_web_public: false,
        desktop_notifications: null,
        audible_notifications: null,
        email_notifications: null,
        push_notifications: null,
        wildcard_mentions_notify: null,
    };
    stream_data.clear_subscriptions();
    stream_data.add_sub(india);

    assert(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    page_params.enable_stream_desktop_notifications = true;
    page_params.enable_stream_audible_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    page_params.enable_stream_desktop_notifications = false;
    page_params.enable_stream_audible_notifications = false;
    assert(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = true;
    india.audible_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert(stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    india.desktop_notifications = false;
    india.audible_notifications = false;
    page_params.enable_stream_desktop_notifications = true;
    page_params.enable_stream_audible_notifications = true;
    assert(!stream_data.receives_notifications(india.stream_id, "desktop_notifications"));
    assert(!stream_data.receives_notifications(india.stream_id, "audible_notifications"));

    page_params.wildcard_mentions_notify = true;
    assert(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    page_params.wildcard_mentions_notify = false;
    assert(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    india.wildcard_mentions_notify = true;
    assert(stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));
    page_params.wildcard_mentions_notify = true;
    india.wildcard_mentions_notify = false;
    assert(!stream_data.receives_notifications(india.stream_id, "wildcard_mentions_notify"));

    page_params.enable_stream_push_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    page_params.enable_stream_push_notifications = false;
    assert(!stream_data.receives_notifications(india.stream_id, "push_notifications"));
    india.push_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "push_notifications"));
    page_params.enable_stream_push_notifications = true;
    india.push_notifications = false;
    assert(!stream_data.receives_notifications(india.stream_id, "push_notifications"));

    page_params.enable_stream_email_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    page_params.enable_stream_email_notifications = false;
    assert(!stream_data.receives_notifications(india.stream_id, "email_notifications"));
    india.email_notifications = true;
    assert(stream_data.receives_notifications(india.stream_id, "email_notifications"));
    page_params.enable_stream_email_notifications = true;
    india.email_notifications = false;
    assert(!stream_data.receives_notifications(india.stream_id, "email_notifications"));

    const canada = {
        stream_id: 103,
        name: "Canada",
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

    page_params.enable_stream_desktop_notifications = true;
    page_params.enable_stream_audible_notifications = true;
    page_params.enable_stream_email_notifications = false;
    page_params.enable_stream_push_notifications = false;
    page_params.wildcard_mentions_notify = true;

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

    const unmatched_streams = stream_data.get_unmatched_streams_for_notification_settings();
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
        },
    ];

    assert.deepEqual(unmatched_streams, expected_streams);
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

run_test("is_muted", () => {
    stream_data.add_sub(tony);
    stream_data.add_sub(jazy);
    assert(!stream_data.is_stream_muted_by_name("tony"));
    assert(stream_data.is_stream_muted_by_name("jazy"));
    assert(stream_data.is_stream_muted_by_name("EEXISTS"));
});

run_test("is_notifications_stream_muted", () => {
    stream_data.add_sub(tony);
    stream_data.add_sub(jazy);

    page_params.realm_notifications_stream_id = tony.stream_id;
    assert(!stream_data.is_notifications_stream_muted());

    page_params.realm_notifications_stream_id = jazy.stream_id;
    assert(stream_data.is_notifications_stream_muted());
});

run_test("realm_has_notifications_stream", () => {
    page_params.realm_notifications_stream_id = 10;
    assert(stream_data.realm_has_notifications_stream());
    page_params.realm_notifications_stream_id = -1;
    assert(!stream_data.realm_has_notifications_stream());
});

run_test("remove_default_stream", () => {
    const remove_me = {
        stream_id: 674,
        name: "remove_me",
        subscribed: false,
        is_muted: true,
    };

    stream_data.add_sub(remove_me);
    stream_data.set_realm_default_streams([remove_me]);
    stream_data.remove_default_stream(remove_me.stream_id);
    assert(!stream_data.is_default_stream_id(remove_me.stream_id));
});

run_test("canonicalized_name", () => {
    assert.deepStrictEqual(stream_data.canonicalized_name("Stream_Bar"), "stream_bar");
});

run_test("create_sub", () => {
    stream_data.clear_subscriptions();
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

    color_data.pick_color = function () {
        return "#bd86e5";
    };

    const india_sub = stream_data.create_sub_from_server_data(india);
    assert(india_sub);
    assert.equal(india_sub.color, "#bd86e5");
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
    assert(antarctica_sub);
    assert.equal(antarctica_sub.color, "#76ce90");
});

run_test("initialize", () => {
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

    page_params.demote_inactive_streams = 1;
    page_params.realm_notifications_stream_id = -1;

    initialize();
    assert(!stream_data.is_filtering_inactives());

    const stream_names = stream_data.get_streams_for_admin().map((elem) => elem.name);
    assert(stream_names.includes("subscriptions"));
    assert(stream_names.includes("unsubscribed"));
    assert(stream_names.includes("never_subscribed"));
    assert.equal(stream_data.get_notifications_stream(), "");

    // Simulate a private stream the user isn't subscribed to
    page_params.realm_notifications_stream_id = 89;
    initialize();
    assert.equal(stream_data.get_notifications_stream(), "");

    // Now actually subscribe the user to the stream
    initialize();
    const foo = {
        name: "foo",
        stream_id: 89,
    };

    stream_data.add_sub(foo);
    initialize();
    assert.equal(stream_data.get_notifications_stream(), "foo");
});

run_test("filter inactives", () => {
    const params = {};
    params.unsubscribed = [];
    params.never_subscribed = [];
    params.subscriptions = [];
    params.realm_default_streams = [];

    stream_data.initialize(params);
    assert(!stream_data.is_filtering_inactives());

    _.times(30, (i) => {
        const name = "random" + i.toString();
        const stream_id = 100 + i;

        const sub = {
            name,
            subscribed: true,
            newly_subscribed: false,
            stream_id,
        };
        stream_data.add_sub(sub);
    });
    stream_data.initialize(params);
    assert(stream_data.is_filtering_inactives());
});

run_test("is_subscriber_subset", () => {
    function make_sub(user_ids) {
        const sub = {};
        stream_data.set_subscribers(sub, user_ids);
        return sub;
    }

    const sub_a = make_sub([1, 2]);
    const sub_b = make_sub([2, 3]);
    const sub_c = make_sub([1, 2, 3]);

    // The bogus case should not come up in normal
    // use.
    // We simply punt on any calculation if
    // a stream has no subscriber info (like
    // maybe Zephyr?).
    const bogus = {}; // no subscribers

    const matrix = [
        [sub_a, sub_a, true],
        [sub_a, sub_b, false],
        [sub_a, sub_c, true],
        [sub_b, sub_a, false],
        [sub_b, sub_b, true],
        [sub_b, sub_c, true],
        [sub_c, sub_a, false],
        [sub_c, sub_b, false],
        [sub_c, sub_c, true],
        [bogus, bogus, false],
    ];

    for (const row of matrix) {
        assert.equal(stream_data.is_subscriber_subset(row[0], row[1]), row[2]);
    }
});

run_test("edge_cases", () => {
    const bad_stream_ids = [555555, 99999];

    // just make sure we don't explode
    stream_data.sort_for_stream_settings(bad_stream_ids);
});

run_test("get_invite_stream_data", () => {
    // add default stream
    const orie = {
        name: "Orie",
        stream_id: 320,
        invite_only: false,
        subscribed: true,
    };

    // clear all the data form stream_data, and people
    stream_data.clear_subscriptions();
    people.init();

    stream_data.add_sub(orie);
    stream_data.set_realm_default_streams([orie]);

    const expected_list = [
        {
            name: "Orie",
            stream_id: 320,
            invite_only: false,
            default_stream: true,
        },
    ];
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);

    const inviter = {
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        subscribed: true,
    };
    stream_data.add_sub(inviter);

    expected_list.push({
        name: "Inviter",
        stream_id: 25,
        invite_only: true,
        default_stream: false,
    });
    assert.deepEqual(stream_data.get_invite_stream_data(), expected_list);
});

run_test("all_topics_in_cache", () => {
    // Add a new stream with first_message_id set.
    const general = {
        name: "general",
        stream_id: 21,
        first_message_id: null,
    };
    const messages = [
        {id: 1, stream_id: 21},
        {id: 2, stream_id: 21},
        {id: 3, stream_id: 21},
    ];
    const sub = stream_data.create_sub_from_server_data(general);

    assert.equal(stream_data.all_topics_in_cache(sub), false);

    message_list.all.data.add_messages(messages);
    assert.equal(stream_data.all_topics_in_cache(sub), false);
    message_list.all.data.fetch_status.has_found_newest = () => true;
    assert.equal(stream_data.all_topics_in_cache(sub), true);

    sub.first_message_id = 0;
    assert.equal(stream_data.all_topics_in_cache(sub), false);

    sub.first_message_id = 2;
    assert.equal(stream_data.all_topics_in_cache(sub), true);
});
