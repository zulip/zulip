"use strict";

const noop = function () {};

const events = require("./lib/events.js");

const event_fixtures = events.fixtures;
const test_message = events.test_message;
const test_user = events.test_user;
const test_streams = events.test_streams;
const typing_person1 = events.typing_person1;

set_global("$", global.make_zjquery());

global.patch_builtin("setTimeout", (func) => func());

set_global("activity", {});
set_global("alert_words_ui", {});
set_global("attachments_ui", {});
set_global("bot_data", {});
set_global("compose", {});
set_global("composebox_typeahead", {});
set_global("current_msg_list", {});
set_global("emoji", {});
set_global("emoji_picker", {});
set_global("home_msg_list", {});
set_global("hotspots", {});
set_global("markdown", {});
set_global("message_edit", {});
set_global("message_list", {});
set_global("muting_ui", {});
set_global("night_mode", {});
set_global("notifications", {});
set_global("overlays", {});
set_global("reactions", {});
set_global("realm_icon", {});
set_global("realm_logo", {});
set_global("reload", {});
set_global("scroll_bar", {});
set_global("settings_account", {});
set_global("settings_bots", {});
set_global("settings_display", {});
set_global("settings_emoji", {});
set_global("settings_exports", {});
set_global("settings_invites", {});
set_global("settings_linkifiers", {});
set_global("settings_notifications", {});
set_global("settings_org", {});
set_global("settings_profile_fields", {});
set_global("settings_streams", {});
set_global("settings_user_groups", {});
set_global("settings_users", {});
set_global("stream_data", {});
set_global("stream_events", {});
set_global("submessage", {});
set_global("typing_events", {});
set_global("ui", {});
set_global("unread_ops", {});
set_global("user_events", {});
set_global("user_groups", {});

// page_params is highly coupled to dispatching now
set_global("page_params", {
    test_suite: false,
    is_admin: true,
    realm_description: "already set description",
});
const page_params = global.page_params;

// For data-oriented modules, just use them, don't stub them.
zrequire("alert_words");
zrequire("unread");
zrequire("stream_topic_history");
zrequire("stream_list");
zrequire("message_flags");
zrequire("message_store");
zrequire("people");
zrequire("starred_messages");
zrequire("user_status");
zrequire("subs");

const emoji = zrequire("emoji", "shared/js/emoji");

zrequire("server_events_dispatch");
zrequire("panels");

function dispatch(ev) {
    server_events_dispatch.dispatch_normal_event(ev);
}

people.init();
people.add_active_user(test_user);

message_store.add_message_metadata(test_message);

const realm_emoji = {};
const emoji_codes = zrequire("emoji_codes", "generated/emoji/emoji_codes.json");

emoji.initialize({realm_emoji, emoji_codes});

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert(expected !== undefined);
    assert.deepEqual(actual, expected);
}

run_test("alert_words", (override) => {
    assert(!alert_words.has_alert_word("fire"));
    assert(!alert_words.has_alert_word("lunch"));

    override("alert_words_ui.render_alert_words_ui", noop);
    const event = event_fixtures.alert_words;
    dispatch(event);

    assert.deepEqual(alert_words.get_word_list(), ["fire", "lunch"]);
    assert(alert_words.has_alert_word("fire"));
    assert(alert_words.has_alert_word("lunch"));
});

run_test("attachments", (override) => {
    const event = event_fixtures.attachment;
    global.with_stub((stub) => {
        override("attachments_ui.update_attachments", stub.f);
        dispatch(event);
        assert_same(stub.get_args("event").event, event);
    });
});

run_test("user groups", (override) => {
    let event = event_fixtures.user_group__add;
    override("settings_user_groups.reload", noop);
    global.with_stub((stub) => {
        override("user_groups.add", stub.f);
        dispatch(event);
        const args = stub.get_args("group");
        assert_same(args.group, event.group);
    });

    event = event_fixtures.user_group__add_members;
    global.with_stub((stub) => {
        override("user_groups.add_members", stub.f);
        dispatch(event);
        const args = stub.get_args("group_id", "user_ids");
        assert_same(args.group_id, event.group_id);
        assert_same(args.user_ids, event.user_ids);
    });

    event = event_fixtures.user_group__remove_members;
    global.with_stub((stub) => {
        override("user_groups.remove_members", stub.f);
        dispatch(event);
        const args = stub.get_args("group_id", "user_ids");
        assert_same(args.group_id, event.group_id);
        assert_same(args.user_ids, event.user_ids);
    });

    event = event_fixtures.user_group__update;
    global.with_stub((stub) => {
        override("user_groups.update", stub.f);
        dispatch(event);
        const args = stub.get_args("event");
        assert_same(args.event.group_id, event.group_id);
        assert_same(args.event.data.name, event.data.name);
        assert_same(args.event.data.description, event.data.description);
    });
});

run_test("custom profile fields", (override) => {
    const event = event_fixtures.custom_profile_fields;
    override("settings_profile_fields.populate_profile_fields", noop);
    override("settings_account.add_custom_profile_fields_to_settings", noop);
    dispatch(event);
    assert_same(global.page_params.custom_profile_fields, event.fields);
});

run_test("default_streams", (override) => {
    const event = event_fixtures.default_streams;
    override("settings_streams.update_default_streams_table", noop);
    global.with_stub((stub) => {
        override("stream_data.set_realm_default_streams", stub.f);
        dispatch(event);
        const args = stub.get_args("realm_default_streams");
        assert_same(args.realm_default_streams, event.default_streams);
    });
});

run_test("hotspots", (override) => {
    const event = event_fixtures.hotspots;
    override("hotspots.load_new", noop);
    dispatch(event);
    assert_same(page_params.hotspots, event.hotspots);
});

run_test("invites_changed", (override) => {
    const event = event_fixtures.invites_changed;
    $("#admin-invites-list").length = 1;
    global.with_stub((stub) => {
        override("settings_invites.set_up", stub.f);
        dispatch(event); // stub automatically checks if stub.f is called once
    });
});

run_test("muted_topics", (override) => {
    const event = event_fixtures.muted_topics;

    global.with_stub((stub) => {
        override("muting_ui.handle_updates", stub.f);
        dispatch(event);
        const args = stub.get_args("muted_topics");
        assert_same(args.muted_topics, event.muted_topics);
    });
});

run_test("presence", (override) => {
    const event = event_fixtures.presence;

    global.with_stub((stub) => {
        override("activity.update_presence_info", stub.f);
        dispatch(event);
        const args = stub.get_args("user_id", "presence", "server_time");
        assert_same(args.user_id, event.user_id);
        assert_same(args.presence, event.presence);
        assert_same(args.server_time, event.server_timestamp);
    });
});

run_test("reaction", (override) => {
    let event = event_fixtures.reaction__add;
    global.with_stub((stub) => {
        override("reactions.add_reaction", stub.f);
        dispatch(event);
        const args = stub.get_args("event");
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
    });

    event = event_fixtures.reaction__remove;
    global.with_stub((stub) => {
        override("reactions.remove_reaction", stub.f);
        dispatch(event);
        const args = stub.get_args("event");
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
    });
});

run_test("realm settings", (override) => {
    override("settings_org.sync_realm_settings", noop);
    override("settings_bots.update_bot_permissions_ui", noop);
    override("notifications.redraw_title", noop);

    // realm
    function test_realm_boolean(event, parameter_name) {
        page_params[parameter_name] = true;
        event = {...event};
        event.value = false;
        dispatch(event);
        assert.equal(page_params[parameter_name], false);
        event = {...event};
        event.value = true;
        dispatch(event);
        assert.equal(page_params[parameter_name], true);
    }

    function test_realm_integer(event, parameter_name) {
        page_params[parameter_name] = 1;
        event = {...event};
        event.value = 2;
        dispatch(event);
        assert.equal(page_params[parameter_name], 2);

        event = {...event};
        event.value = 3;
        dispatch(event);
        assert.equal(page_params[parameter_name], 3);

        event = {...event};
        event.value = 1;
        dispatch(event);
        assert.equal(page_params[parameter_name], 1);
    }

    let event = event_fixtures.realm__update__create_stream_policy;
    test_realm_integer(event, "realm_create_stream_policy");

    event = event_fixtures.realm__update__invite_to_stream_policy;
    test_realm_integer(event, "realm_invite_to_stream_policy");

    event = event_fixtures.realm__update__bot_creation_policy;
    test_realm_integer(event, "realm_bot_creation_policy");

    event = event_fixtures.realm__update__invite_required;
    test_realm_boolean(event, "realm_invite_required");

    event = event_fixtures.realm__update__name;
    dispatch(event);
    assert_same(page_params.realm_name, "new_realm_name");

    let called = false;
    set_global("electron_bridge", {
        send_event: (key, val) => {
            assert_same(key, "realm_name");
            assert_same(val, "new_realm_name");
            called = true;
        },
    });

    dispatch(event);
    assert_same(called, true);

    event = event_fixtures.realm__update__emails_restricted_to_domains;
    test_realm_boolean(event, "realm_emails_restricted_to_domains");

    event = event_fixtures.realm__update__disallow_disposable_email_addresses;
    test_realm_boolean(event, "realm_disallow_disposable_email_addresses");

    event = event_fixtures.realm__update__default_twenty_four_hour_time;
    test_realm_boolean(event, "realm_default_twenty_four_hour_time");

    event = event_fixtures.realm__update__email_addresses_visibility;
    dispatch(event);
    assert_same(page_params.realm_email_address_visibility, 3);

    event = event_fixtures.realm__update__notifications_stream_id;
    dispatch(event);
    assert_same(page_params.realm_notifications_stream_id, 42);
    page_params.realm_notifications_stream_id = -1; // make sure to reset for future tests

    event = event_fixtures.realm__update__signup_notifications_stream_id;
    dispatch(event);
    assert_same(page_params.realm_signup_notifications_stream_id, 41);
    page_params.realm_signup_notifications_stream_id = -1; // make sure to reset for future tests

    event = event_fixtures.realm__update__default_code_block_language;
    dispatch(event);
    assert_same(page_params.realm_default_code_block_language, "javascript");

    event = event_fixtures.realm__update_dict__default;
    page_params.realm_allow_message_editing = false;
    page_params.realm_message_content_edit_limit_seconds = 0;
    override("settings_org.populate_auth_methods", noop);
    override("message_edit.update_message_topic_editing_pencil", noop);
    dispatch(event);
    assert_same(page_params.realm_allow_message_editing, true);
    assert_same(page_params.realm_message_content_edit_limit_seconds, 5);
    assert_same(page_params.realm_authentication_methods, {Google: true});

    event = event_fixtures.realm__update_dict__icon;
    override("realm_icon.rerender", noop);

    called = false;
    set_global("electron_bridge", {
        send_event: (key, val) => {
            assert_same(key, "realm_icon_url");
            assert_same(val, "icon.png");
            called = true;
        },
    });

    dispatch(event);

    assert_same(called, true);
    assert_same(page_params.realm_icon_url, "icon.png");
    assert_same(page_params.realm_icon_source, "U");

    event = event_fixtures.realm__update_dict__logo;
    override("realm_logo.rerender", noop);
    dispatch(event);
    assert_same(page_params.realm_logo_url, "logo.png");
    assert_same(page_params.realm_logo_source, "U");

    event = event_fixtures.realm__update_dict__night_logo;
    override("realm_logo.rerender", noop);
    dispatch(event);
    assert_same(page_params.realm_night_logo_url, "night_logo.png");
    assert_same(page_params.realm_night_logo_source, "U");

    event = event_fixtures.realm__deactivated;
    set_global("location", {});
    dispatch(event);
    assert_same(window.location.href, "/accounts/deactivated/");
});

run_test("realm_bot", (override) => {
    let event = event_fixtures.realm_bot__add;
    global.with_stub((bot_stub) => {
        global.with_stub((admin_stub) => {
            override("bot_data.add", bot_stub.f);
            override("settings_users.update_bot_data", admin_stub.f);
            dispatch(event);
            const args = bot_stub.get_args("bot");
            assert_same(args.bot, event.bot);

            admin_stub.get_args("update_user_id", "update_bot_data");
        });
    });

    event = event_fixtures.realm_bot__remove;
    global.with_stub((bot_stub) => {
        global.with_stub((admin_stub) => {
            override("bot_data.deactivate", bot_stub.f);
            override("settings_users.update_bot_data", admin_stub.f);
            dispatch(event);
            const args = bot_stub.get_args("user_id");
            assert_same(args.user_id, event.bot.user_id);

            admin_stub.get_args("update_user_id", "update_bot_data");
        });
    });

    event = event_fixtures.realm_bot__delete;
    // We don't handle live updates for delete events, this is a noop.
    dispatch(event);

    event = event_fixtures.realm_bot__update;
    global.with_stub((bot_stub) => {
        global.with_stub((admin_stub) => {
            override("bot_data.update", bot_stub.f);
            override("settings_users.update_bot_data", admin_stub.f);

            dispatch(event);

            let args = bot_stub.get_args("user_id", "bot");
            assert_same(args.user_id, event.bot.user_id);
            assert_same(args.bot, event.bot);

            args = admin_stub.get_args("update_user_id", "update_bot_data");
            assert_same(args.update_user_id, event.bot.user_id);
        });
    });
});

run_test("realm_emoji", (override) => {
    const event = event_fixtures.realm_emoji__update;

    const ui_func_names = [
        "settings_emoji.populate_emoji",
        "emoji_picker.rebuild_catalog",
        "composebox_typeahead.update_emoji_data",
    ];

    const ui_stubs = [];

    for (const func_name of ui_func_names) {
        const ui_stub = global.make_stub();
        override(func_name, ui_stub.f);
        ui_stubs.push(ui_stub);
    }

    // Make sure we start with nothing...
    assert.equal(emoji.get_realm_emoji_url("spain"), undefined);

    dispatch(event);

    // Now emoji.js knows about the spain emoji.
    assert_same(emoji.get_realm_emoji_url("spain"), "/some/path/to/spain.png");

    // Make sure our UI modules all got dispatched the same simple way.
    for (const stub of ui_stubs) {
        assert(stub.num_calls, 1);
        assert.equal(stub.last_call_args.length, 0);
    }
});

run_test("realm_filters", (override) => {
    const event = event_fixtures.realm_filters;
    page_params.realm_filters = [];
    override("settings_linkifiers.populate_filters", noop);
    override("markdown.update_realm_filter_rules", noop);
    dispatch(event);
    assert_same(page_params.realm_filters, event.realm_filters);
});

run_test("realm_domains", (override) => {
    let event = event_fixtures.realm_domains__add;
    page_params.realm_domains = [];
    override("settings_org.populate_realm_domains", noop);
    dispatch(event);
    assert_same(page_params.realm_domains, [event.realm_domain]);

    event = event_fixtures.realm_domains__change;
    dispatch(event);
    assert_same(page_params.realm_domains, [event.realm_domain]);

    event = event_fixtures.realm_domains__remove;
    dispatch(event);
    assert_same(page_params.realm_domains, []);
});

run_test("realm_user", (override) => {
    let event = event_fixtures.realm_user__add;
    dispatch(event);
    const added_person = people.get_by_user_id(event.person.user_id);
    assert.equal(added_person.full_name, "Test User");
    assert(people.is_active_user_for_popover(event.person.user_id));

    event = event_fixtures.realm_user__remove;
    override("stream_events.remove_deactivated_user_from_all_streams", noop);
    dispatch(event);

    // We don't actually remove the person, we just deactivate them.
    const removed_person = people.get_by_user_id(event.person.user_id);
    assert.equal(removed_person.full_name, "Test User");
    assert(!people.is_active_user_for_popover(event.person.user_id));

    event = event_fixtures.realm_user__update;
    global.with_stub((stub) => {
        override("user_events.update_person", stub.f);
        dispatch(event);
        const args = stub.get_args("person");
        assert_same(args.person, event.person);
    });
});

run_test("restart", (override) => {
    const event = event_fixtures.restart;
    global.with_stub((stub) => {
        override("reload.initiate", stub.f);
        dispatch(event);
        const args = stub.get_args("options");
        assert.equal(args.options.save_pointer, true);
        assert.equal(args.options.immediate, true);
    });
});

run_test("stream", (override) => {
    let event = event_fixtures.stream__update;

    global.with_stub((stub) => {
        override("stream_events.update_property", stub.f);
        override("settings_streams.update_default_streams_table", noop);
        dispatch(event);
        const args = stub.get_args("stream_id", "property", "value");
        assert_same(args.stream_id, event.stream_id);
        assert_same(args.property, event.property);
        assert_same(args.value, event.value);
    });

    // stream create
    event = event_fixtures.stream__create;
    global.with_stub((stub) => {
        override("stream_data.create_streams", stub.f);
        override("stream_data.get_sub_by_id", noop);
        override("stream_data.update_calculated_fields", noop);
        override("subs.add_sub_to_table", noop);
        override("overlays.streams_open", () => true);
        dispatch(event);
        const args = stub.get_args("streams");
        assert_same(
            args.streams.map((stream) => stream.stream_id),
            [101, 102],
        );
    });

    // stream delete
    event = event_fixtures.stream__delete;
    global.with_stub((stub) => {
        override("subs.remove_stream", noop);
        override("stream_data.delete_sub", noop);
        override("settings_streams.update_default_streams_table", noop);
        override("stream_data.remove_default_stream", noop);

        const devel_id = test_streams.devel.stream_id;

        override("stream_data.get_sub_by_id", (id) =>
            id === devel_id ? {subscribed: true} : {subscribed: false},
        );
        override("stream_list.remove_sidebar_row", stub.f);
        dispatch(event);
        const args = stub.get_args("stream_id");
        assert_same(args.stream_id, devel_id);

        override("settings_org.sync_realm_settings", noop);
        override("stream_list.remove_sidebar_row", noop);
        page_params.realm_notifications_stream_id = devel_id;
        dispatch(event);
        assert_same(page_params.realm_notifications_stream_id, -1);

        page_params.realm_signup_notifications_stream_id = devel_id;
        dispatch(event);
        assert_same(page_params.realm_signup_notifications_stream_id, -1);
    });
});

run_test("submessage", (override) => {
    const event = event_fixtures.submessage;
    global.with_stub((stub) => {
        override("submessage.handle_event", stub.f);
        dispatch(event);
        const submsg = stub.get_args("submsg").submsg;
        assert_same(submsg, {
            id: 99,
            sender_id: 42,
            msg_type: "stream",
            message_id: 56,
            content: "test",
        });
    });
});

// For subscriptions, see dispatch_subs.js

run_test("typing", (override) => {
    let event = event_fixtures.typing__start;
    global.with_stub((stub) => {
        override("typing_events.display_notification", stub.f);
        dispatch(event);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
    });

    event = event_fixtures.typing__stop;
    global.with_stub((stub) => {
        override("typing_events.hide_notification", stub.f);
        dispatch(event);
        const args = stub.get_args("event");
        assert_same(args.event.sender.user_id, typing_person1.user_id);
    });

    page_params.user_id = typing_person1.user_id;
    event = event_fixtures.typing__start;
    dispatch(event); // get line coverage
});

run_test("update_display_settings", (override) => {
    let event = event_fixtures.update_display_settings__default_language;
    page_params.default_language = "en";
    override("settings_display.update_page", noop);
    dispatch(event);
    assert_same(page_params.default_language, "fr");

    event = event_fixtures.update_display_settings__left_side_userlist;
    page_params.left_side_userlist = false;
    dispatch(event);
    assert_same(page_params.left_side_userlist, true);

    // We alias message_list.narrowed to current_msg_list
    // to make sure we get line coverage on re-rendering
    // the current message list.  The actual code tests
    // that these two objects are equal.  It is possible
    // we want a better strategy for that, or at least
    // a helper.
    message_list.narrowed = current_msg_list;

    let called = false;
    current_msg_list.rerender = () => {
        called = true;
    };

    override("home_msg_list.rerender", noop);
    event = event_fixtures.update_display_settings__twenty_four_hour_time;
    page_params.twenty_four_hour_time = false;
    dispatch(event);
    assert_same(page_params.twenty_four_hour_time, true);
    assert_same(called, true);

    event = event_fixtures.update_display_settings__translate_emoticons;
    page_params.translate_emoticons = false;
    dispatch(event);
    assert_same(page_params.translate_emoticons, true);

    event = event_fixtures.update_display_settings__high_contrast_mode;
    page_params.high_contrast_mode = false;
    let toggled = [];
    $("body").toggleClass = (cls) => {
        toggled.push(cls);
    };
    dispatch(event);
    assert_same(page_params.high_contrast_mode, true);
    assert_same(toggled, ["high-contrast"]);

    event = event_fixtures.update_display_settings__dense_mode;
    page_params.dense_mode = false;
    toggled = [];
    dispatch(event);
    assert_same(page_params.dense_mode, true);
    assert_same(toggled, ["less_dense_mode", "more_dense_mode"]);

    $("body").fadeOut = (secs) => {
        assert_same(secs, 300);
    };
    $("body").fadeIn = (secs) => {
        assert_same(secs, 300);
    };

    global.with_stub((stub) => {
        event = event_fixtures.update_display_settings__color_scheme_dark;
        page_params.color_scheme = 1;
        override("night_mode.enable", stub.f); // automatically checks if called
        override("realm_logo.rerender", noop);
        dispatch(event);
        assert(page_params.color_scheme, 2);
    });

    global.with_stub((stub) => {
        event = event_fixtures.update_display_settings__color_scheme_light;
        page_params.color_scheme = 1;
        override("night_mode.disable", stub.f); // automatically checks if called
        override("realm_logo.rerender", noop);
        dispatch(event);
        assert(page_params.color_scheme, 3);
    });

    global.with_stub((stub) => {
        event = event_fixtures.update_display_settings__color_scheme_automatic;
        page_params.color_scheme = 2;
        override("night_mode.default_preference_checker", stub.f); // automatically checks if called
        override("realm_logo.rerender", noop);
        dispatch(event);
        assert(page_params.color_scheme, 1);
    });

    global.with_stub((stub) => {
        event = event_fixtures.update_display_settings__emojiset;
        called = false;
        override("settings_display.report_emojiset_change", stub.f);
        page_params.emojiset = "text";
        dispatch(event);
        assert_same(called, true);
        assert_same(page_params.emojiset, "google");
    });

    override("starred_messages.rerender_ui", noop);
    event = event_fixtures.update_display_settings__starred_message_counts;
    page_params.starred_message_counts = false;
    dispatch(event);
    assert_same(page_params.starred_message_counts, true);

    override("scroll_bar.set_layout_width", noop);
    event = event_fixtures.update_display_settings__fluid_layout_width;
    page_params.fluid_layout_width = false;
    dispatch(event);
    assert_same(page_params.fluid_layout_width, true);

    global.with_stub((stub) => {
        event = event_fixtures.update_display_settings__demote_inactive_streams;
        override("stream_data.set_filter_out_inactives", noop);
        override("stream_list.update_streams_sidebar", stub.f);
        page_params.demote_inactive_streams = 1;
        dispatch(event);
        assert_same(page_params.demote_inactive_streams, 2);
    });
});

run_test("update_global_notifications", (override) => {
    const event = event_fixtures.update_global_notifications;
    global.with_stub((stub) => {
        override("notifications.handle_global_notification_updates", stub.f);
        override("settings_notifications.update_page", noop);
        dispatch(event);
        const args = stub.get_args("name", "setting");
        assert_same(args.name, event.notification_name);
        assert_same(args.setting, event.setting);
    });
});

run_test("update_message (read)", (override) => {
    const event = event_fixtures.update_message_flags__read;

    global.with_stub((stub) => {
        override("unread_ops.process_read_messages_event", stub.f);
        dispatch(event);
        const args = stub.get_args("message_ids");
        assert_same(args.message_ids, [999]);
    });
});

run_test("update_message (stars)", (override) => {
    override("starred_messages.rerender_ui", noop);

    let event = event_fixtures.update_message_flags__starred_add;
    global.with_stub((stub) => {
        override("ui.update_starred_view", stub.f);
        dispatch(event);
        const args = stub.get_args("message_id", "new_value");
        assert_same(args.message_id, test_message.id);
        assert_same(args.new_value, true); // for 'add'
        const msg = message_store.get(test_message.id);
        assert.equal(msg.starred, true);
    });

    event = event_fixtures.update_message_flags__starred_remove;
    global.with_stub((stub) => {
        override("ui.update_starred_view", stub.f);
        dispatch(event);
        const args = stub.get_args("message_id", "new_value");
        assert_same(args.message_id, test_message.id);
        assert_same(args.new_value, false);
        const msg = message_store.get(test_message.id);
        assert.equal(msg.starred, false);
    });
});

run_test("delete_message", (override) => {
    const event = event_fixtures.delete_message;

    override("stream_list.update_streams_sidebar", noop);
    global.with_stub((stub) => {
        override("unread_ops.process_read_messages_event", noop);
        override("ui.remove_messages", stub.f);
        dispatch(event);
        const args = stub.get_args("message_ids");
        assert_same(args.message_ids, [1337]);
    });
    global.with_stub((stub) => {
        override("unread_ops.process_read_messages_event", stub.f);
        dispatch(event);
        const args = stub.get_args("message_ids");
        assert_same(args.message_ids, [1337]);
    });
    global.with_stub((stub) => {
        override("stream_topic_history.remove_messages", stub.f);
        dispatch(event);
        const args = stub.get_args("opts");
        assert_same(args.opts.stream_id, 99);
        assert_same(args.opts.topic_name, "topic1");
        assert_same(args.opts.num_messages, 1);
        assert_same(args.opts.max_removed_msg_id, 1337);
    });
});

run_test("user_status", (override) => {
    let event = event_fixtures.user_status__set_away;
    global.with_stub((stub) => {
        override("activity.on_set_away", stub.f);
        dispatch(event);
        const args = stub.get_args("user_id");
        assert_same(args.user_id, 55);
    });

    event = event_fixtures.user_status__revoke_away;
    global.with_stub((stub) => {
        override("activity.on_revoke_away", stub.f);
        dispatch(event);
        const args = stub.get_args("user_id");
        assert_same(args.user_id, 63);
    });

    event = event_fixtures.user_status__set_status_text;
    global.with_stub((stub) => {
        override("activity.redraw_user", stub.f);
        dispatch(event);
        const args = stub.get_args("user_id");
        assert_same(args.user_id, test_user.user_id);
        const status_text = user_status.get_status_text(test_user.user_id);
        assert.equal(status_text, "out to lunch");
    });
});

run_test("realm_export", (override) => {
    const event = event_fixtures.realm_export;
    override("settings_exports.populate_exports_table", noop);
    dispatch(event);
    global.with_stub((stub) => {
        override("settings_exports.populate_exports_table", stub.f);
        dispatch(event);

        const args = stub.get_args("exports");
        assert.equal(args.exports.acting_user_id, 55);
        assert.equal(args.exports.event_time, "noon");
        assert.equal(args.exports.path, "some_path");
    });
});
