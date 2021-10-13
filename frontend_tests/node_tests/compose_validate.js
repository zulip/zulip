"use strict";

const {strict: assert} = require("assert");

const {$t_html} = require("../zjsunit/i18n");
const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const channel = mock_esm("../../static/js/channel");
const compose_actions = mock_esm("../../static/js/compose_actions");
const compose_state = zrequire("compose_state");
const ui_util = mock_esm("../../static/js/ui_util");

const compose_pm_pill = zrequire("compose_pm_pill");
const compose_validate = zrequire("compose_validate");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const settings_config = zrequire("settings_config");
const settings_data = mock_esm("../../static/js/settings_data");
const stream_data = zrequire("stream_data");

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    date_joined: new Date(),
};

const alice = {
    email: "alice@example.com",
    user_id: 31,
    full_name: "Alice",
};

const bob = {
    email: "bob@example.com",
    user_id: 32,
    full_name: "Bob",
};

people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);

const welcome_bot = {
    email: "welcome-bot@example.com",
    user_id: 4,
    full_name: "Welcome Bot",
    is_bot: true,
    // cross realm bots have no owner
};

people.add_cross_realm_user(welcome_bot);

function test_ui(label, f) {
    // The sloppy_$ flag lets us re-use setup from prior tests.
    run_test(label, ({override, mock_template}) => {
        $("#compose-textarea").val("some message");
        f({override, mock_template});
    });
}

test_ui("validate_stream_message_address_info", ({mock_template}) => {
    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };
    stream_data.add_sub(sub);
    assert.ok(compose_validate.validate_stream_message_address_info("social"));

    sub.subscribed = false;
    stream_data.add_sub(sub);
    mock_template("compose_not_subscribed.hbs", false, () => "compose_not_subscribed_stub");
    assert.ok(!compose_validate.validate_stream_message_address_info("social"));
    assert.equal($("#compose-error-msg").html(), "compose_not_subscribed_stub");

    page_params.narrow_stream = false;
    channel.post = (payload) => {
        assert.equal(payload.data.stream, "social");
        payload.data.subscribed = true;
        payload.success(payload.data);
    };
    assert.ok(compose_validate.validate_stream_message_address_info("social"));

    sub.name = "Frontend";
    sub.stream_id = 102;
    stream_data.add_sub(sub);
    channel.post = (payload) => {
        assert.equal(payload.data.stream, "Frontend");
        payload.data.subscribed = false;
        payload.success(payload.data);
    };
    assert.ok(!compose_validate.validate_stream_message_address_info("Frontend"));
    assert.equal($("#compose-error-msg").html(), "compose_not_subscribed_stub");

    channel.post = (payload) => {
        assert.equal(payload.data.stream, "Frontend");
        payload.error({status: 404});
    };
    assert.ok(!compose_validate.validate_stream_message_address_info("Frontend"));
    assert.equal(
        $("#compose-error-msg").html(),
        "translated HTML: <p>The stream <b>Frontend</b> does not exist.</p><p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>",
    );

    channel.post = (payload) => {
        assert.equal(payload.data.stream, "social");
        payload.error({status: 500});
    };
    assert.ok(!compose_validate.validate_stream_message_address_info("social"));
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Error checking subscription"}),
    );
});

test_ui("validate", ({override, mock_template}) => {
    override(compose_actions, "update_placeholder_text", () => {});

    function initialize_pm_pill() {
        $.clear_all_elements();

        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $("#sending-indicator").hide();

        const pm_pill_container = $.create("fake-pm-pill-container");
        $("#private_message_recipient")[0] = {};
        $("#private_message_recipient").set_parent(pm_pill_container);
        pm_pill_container.set_find_results(".input", $("#private_message_recipient"));
        $("#private_message_recipient").before = () => {};

        compose_pm_pill.initialize();

        ui_util.place_caret_at_end = () => {};

        $("#zephyr-mirror-error").is = () => {};

        mock_template("input_pill.hbs", false, () => "<div>pill-html</div>");
    }

    function add_content_to_compose_box() {
        $("#compose-textarea").val("foobarfoobar");
    }

    initialize_pm_pill();
    assert.ok(!compose_validate.validate());
    assert.ok(!$("#sending-indicator").visible());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "You have nothing to send!"}),
    );

    compose_validate.validate();

    add_content_to_compose_box();
    let zephyr_checked = false;
    $("#zephyr-mirror-error").is = () => {
        if (!zephyr_checked) {
            zephyr_checked = true;
            return true;
        }
        return false;
    };
    assert.ok(!compose_validate.validate());
    assert.ok(zephyr_checked);
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({
            defaultMessage: "You need to be running Zephyr mirroring in order to send messages!",
        }),
    );

    initialize_pm_pill();
    add_content_to_compose_box();

    // test validating private messages
    compose_state.set_message_type("private");

    compose_state.private_message_recipient("");
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("foo@zulip.com");

    assert.ok(!compose_validate.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    compose_state.private_message_recipient("foo@zulip.com,alice@zulip.com");
    assert.ok(!compose_validate.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    people.add_active_user(bob);
    compose_state.private_message_recipient("bob@example.com");
    assert.ok(compose_validate.validate());

    people.deactivate(bob);
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "You cannot send messages to deactivated users."}),
    );

    page_params.realm_is_zephyr_mirror_realm = true;
    assert.ok(compose_validate.validate());
    page_params.realm_is_zephyr_mirror_realm = false;

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("welcome-bot@example.com");
    assert.ok(compose_validate.validate());

    compose_state.set_message_type("stream");
    compose_state.stream_name("");
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify a stream"}),
    );

    compose_state.stream_name("Denmark");
    page_params.realm_mandatory_topics = true;
    compose_state.topic("");
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify a topic"}),
    );
});

test_ui("get_invalid_recipient_emails", ({override}) => {
    const welcome_bot = {
        email: "welcome-bot@example.com",
        user_id: 124,
        full_name: "Welcome Bot",
    };

    page_params.user_id = me.user_id;

    const params = {};
    params.realm_users = [];
    params.realm_non_active_users = [];
    params.cross_realm_bots = [welcome_bot];

    people.initialize(page_params.user_id, params);

    override(compose_state, "private_message_recipient", () => "welcome-bot@example.com");
    assert.deepEqual(compose_validate.get_invalid_recipient_emails(), []);
});

test_ui("test_wildcard_mention_allowed", () => {
    page_params.user_id = me.user_id;

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_everyone.code;
    page_params.is_guest = true;
    page_params.is_admin = false;
    assert.ok(compose_validate.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.nobody.code;
    page_params.is_admin = true;
    assert.ok(!compose_validate.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_members.code;
    page_params.is_guest = true;
    page_params.is_admin = false;
    assert.ok(!compose_validate.wildcard_mention_allowed());

    page_params.is_guest = false;
    assert.ok(compose_validate.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_moderators_only.code;
    page_params.is_moderator = false;
    assert.ok(!compose_validate.wildcard_mention_allowed());

    page_params.is_moderator = true;
    assert.ok(compose_validate.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_stream_admins_only.code;
    page_params.is_admin = false;
    assert.ok(!compose_validate.wildcard_mention_allowed());

    // TODO: Add a by_admins_only case when we implement stream-level administrators.

    page_params.is_admin = true;
    assert.ok(compose_validate.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_full_members.code;
    const person = people.get_by_user_id(page_params.user_id);
    person.date_joined = new Date(Date.now());
    page_params.realm_waiting_period_threshold = 10;

    assert.ok(compose_validate.wildcard_mention_allowed());
    page_params.is_admin = false;
    assert.ok(!compose_validate.wildcard_mention_allowed());
});

test_ui("validate_stream_message", ({override, mock_template}) => {
    // This test is in kind of continuation to test_validate but since it is
    // primarily used to get coverage over functions called from validate()
    // we are separating it up in different test. Though their relative position
    // of execution should not be changed.
    page_params.user_id = me.user_id;
    page_params.realm_mandatory_topics = false;
    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };
    stream_data.add_sub(sub);
    compose_state.stream_name("social");
    assert.ok(compose_validate.validate());
    assert.ok(!$("#compose-all-everyone").visible());
    assert.ok(!$("#compose-send-status").visible());

    peer_data.get_subscriber_count = (stream_id) => {
        assert.equal(stream_id, 101);
        return 16;
    };
    mock_template("compose_all_everyone.hbs", false, (data) => {
        assert.equal(data.count, 16);
        return "compose_all_everyone_stub";
    });
    let compose_content;
    $("#compose-all-everyone").append = (data) => {
        compose_content = data;
    };

    override(compose_validate, "wildcard_mention_allowed", () => true);
    compose_state.message_content("Hey @**all**");
    assert.ok(!compose_validate.validate());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert.ok(!$("#compose-send-status").visible());
    assert.equal(compose_content, "compose_all_everyone_stub");
    assert.ok($("#compose-all-everyone").visible());

    override(compose_validate, "wildcard_mention_allowed", () => false);
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({
            defaultMessage: "You do not have permission to use wildcard mentions in this stream.",
        }),
    );
});

test_ui("test_validate_stream_message_post_policy_admin_only", () => {
    // This test is in continuation with test_validate but it has been separated out
    // for better readability. Their relative position of execution should not be changed.
    // Although the position with respect to test_validate_stream_message does not matter
    // as different stream is used for this test.
    page_params.is_admin = false;
    const sub = {
        stream_id: 102,
        name: "stream102",
        subscribed: true,
        stream_post_policy: stream_data.stream_post_policy_values.admins.code,
    };

    compose_state.topic("subject102");
    compose_state.stream_name("stream102");
    stream_data.add_sub(sub);
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Only organization admins are allowed to post to this stream."}),
    );

    // Reset error message.
    compose_state.stream_name("social");

    page_params.is_admin = false;
    page_params.is_guest = true;

    compose_state.topic("subject102");
    compose_state.stream_name("stream102");
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Only organization admins are allowed to post to this stream."}),
    );
});

test_ui("test_validate_stream_message_post_policy_moderators_only", () => {
    page_params.is_admin = false;
    page_params.is_moderator = false;
    page_params.is_guest = false;

    const sub = {
        stream_id: 104,
        name: "stream104",
        subscribed: true,
        stream_post_policy: stream_data.stream_post_policy_values.moderators.code,
    };

    compose_state.topic("subject104");
    compose_state.stream_name("stream104");
    stream_data.add_sub(sub);
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({
            defaultMessage:
                "Only organization admins and moderators are allowed to post to this stream.",
        }),
    );

    // Reset error message.
    compose_state.stream_name("social");

    page_params.is_guest = true;
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({
            defaultMessage:
                "Only organization admins and moderators are allowed to post to this stream.",
        }),
    );
});

test_ui("test_validate_stream_message_post_policy_full_members_only", () => {
    page_params.is_admin = false;
    page_params.is_guest = true;
    const sub = {
        stream_id: 103,
        name: "stream103",
        subscribed: true,
        stream_post_policy: stream_data.stream_post_policy_values.non_new_members.code,
    };

    compose_state.topic("subject103");
    compose_state.stream_name("stream103");
    stream_data.add_sub(sub);
    assert.ok(!compose_validate.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Guests are not allowed to post to this stream."}),
    );
});

test_ui("test_check_overflow_text", () => {
    page_params.max_message_length = 10000;

    const textarea = $("#compose-textarea");
    const indicator = $("#compose_limit_indicator");
    const send_button = $("#compose-send-button");

    // Indicator should show red colored text
    textarea.val("a".repeat(10000 + 1));
    compose_validate.check_overflow_text();
    assert.ok(indicator.hasClass("over_limit"));
    assert.equal(indicator.text(), "10001/10000");
    assert.ok(textarea.hasClass("over_limit"));
    assert.equal(
        $("#compose-error-msg").html(),
        "translated HTML: Message length shouldn't be greater than 10000 characters.",
    );
    assert.ok(send_button.prop("disabled"));

    $("#compose-send-status").stop = () => ({fadeOut: () => {}});

    // Indicator should show orange colored text
    textarea.val("a".repeat(9000 + 1));
    compose_validate.check_overflow_text();
    assert.ok(!indicator.hasClass("over_limit"));
    assert.equal(indicator.text(), "9001/10000");
    assert.ok(!textarea.hasClass("over_limit"));
    assert.ok(!send_button.prop("disabled"));

    // Indicator must be empty
    textarea.val("a".repeat(9000));
    compose_validate.check_overflow_text();
    assert.ok(!indicator.hasClass("over_limit"));
    assert.equal(indicator.text(), "");
    assert.ok(!textarea.hasClass("over_limit"));
});

test_ui("test_message_overflow", () => {
    page_params.max_message_length = 10000;

    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };

    stream_data.add_sub(sub);
    page_params.user_id = 30;
    const message = "a".repeat(10000 + 1);

    compose_state.stream_name("social");
    compose_state.topic("priyam");
    $("#compose-textarea").val(message);

    assert.ok(!compose_validate.validate());
    assert.equal($("#compose-error-msg").html(), "never-been-set");

    $("#compose-textarea").val("a");
    assert.ok(compose_validate.validate());
});

test_ui("needs_subscribe_warning", () => {
    const invalid_user_id = 999;

    const test_bot = {
        full_name: "Test Bot",
        email: "test-bot@example.com",
        user_id: 135,
        is_bot: true,
    };
    people.add_active_user(test_bot);

    const sub = {
        stream_id: 110,
        name: "stream",
    };

    stream_data.add_sub(sub);
    peer_data.set_subscribers(sub.stream_id, [bob.user_id, me.user_id]);

    blueslip.expect("error", "Unknown user_id in get_by_user_id: 999");
    // Test with an invalid user id.
    assert.equal(compose_validate.needs_subscribe_warning(invalid_user_id, sub.stream_id), false);

    // Test with bot user.
    assert.equal(compose_validate.needs_subscribe_warning(test_bot.user_id, sub.stream_id), false);

    // Test when user is subscribed to the stream.
    assert.equal(compose_validate.needs_subscribe_warning(bob.user_id, sub.stream_id), false);

    peer_data.remove_subscriber(sub.stream_id, bob.user_id);
    // Test when the user is not subscribed.
    assert.equal(compose_validate.needs_subscribe_warning(bob.user_id, sub.stream_id), true);
});

test_ui("warn_if_private_stream_is_linked", ({mock_template}) => {
    const test_sub = {
        name: compose_state.stream_name(),
        stream_id: 99,
    };

    stream_data.add_sub(test_sub);
    peer_data.set_subscribers(test_sub.stream_id, [1, 2]);

    let denmark = {
        stream_id: 100,
        name: "Denmark",
    };
    stream_data.add_sub(denmark);

    peer_data.set_subscribers(denmark.stream_id, [1, 2, 3]);

    function test_noop_case(invite_only) {
        compose_state.set_message_type("stream");
        denmark.invite_only = invite_only;
        compose_validate.warn_if_private_stream_is_linked(denmark);
        assert.equal($("#compose_private_stream_alert").visible(), false);
    }

    test_noop_case(false);
    // invite_only=true and current compose stream subscribers are a subset
    // of mentioned_stream subscribers.
    test_noop_case(true);

    $("#compose_private").hide();
    compose_state.set_message_type("stream");

    const checks = [
        (function () {
            let called;
            mock_template("compose_private_stream_alert.hbs", false, (context) => {
                called = true;
                assert.equal(context.stream_name, "Denmark");
                return "fake-compose_private_stream_alert-template";
            });
            return function () {
                assert.ok(called);
            };
        })(),

        (function () {
            let called;
            $("#compose_private_stream_alert").append = (html) => {
                called = true;
                assert.equal(html, "fake-compose_private_stream_alert-template");
            };
            return function () {
                assert.ok(called);
            };
        })(),
    ];

    denmark = {
        invite_only: true,
        name: "Denmark",
        stream_id: 22,
    };
    stream_data.add_sub(denmark);

    compose_validate.warn_if_private_stream_is_linked(denmark);
    assert.equal($("#compose_private_stream_alert").visible(), true);

    for (const f of checks) {
        f();
    }
});

test_ui("warn_if_mentioning_unsubscribed_user", ({override, mock_template}) => {
    override(settings_data, "user_can_subscribe_other_users", () => true);

    let mentioned = {
        email: "foo@bar.com",
    };

    $("#compose_invite_users .compose_invite_user").length = 0;

    function test_noop_case(is_private, is_zephyr_mirror, is_broadcast) {
        const msg_type = is_private ? "private" : "stream";
        compose_state.set_message_type(msg_type);
        page_params.realm_is_zephyr_mirror_realm = is_zephyr_mirror;
        mentioned.is_broadcast = is_broadcast;
        compose_validate.warn_if_mentioning_unsubscribed_user(mentioned);
        assert.equal($("#compose_invite_users").visible(), false);
    }

    test_noop_case(true, false, false);
    test_noop_case(false, true, false);
    test_noop_case(false, false, true);

    $("#compose_invite_users").hide();
    compose_state.set_message_type("stream");
    page_params.realm_is_zephyr_mirror_realm = false;

    // Test with empty stream name in compose box. It should return noop.
    assert.equal(compose_state.stream_name(), "");
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), false);

    compose_state.stream_name("random");
    const sub = {
        stream_id: 111,
        name: "random",
    };

    // Test with invalid stream in compose box. It should return noop.
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), false);

    // Test mentioning a user that should gets a warning.

    const checks = [
        (function () {
            let called;
            override(compose_validate, "needs_subscribe_warning", (user_id, stream_id) => {
                called = true;
                assert.equal(user_id, 34);
                assert.equal(stream_id, 111);
                return true;
            });
            return function () {
                assert.ok(called);
            };
        })(),

        (function () {
            let called;
            mock_template("compose_invite_users.hbs", false, (context) => {
                called = true;
                assert.equal(context.user_id, 34);
                assert.equal(context.stream_id, 111);
                assert.equal(context.name, "Foo Barson");
                return "fake-compose-invite-user-template";
            });
            return function () {
                assert.ok(called);
            };
        })(),

        (function () {
            let called;
            $("#compose_invite_users").append = (html) => {
                called = true;
                assert.equal(html, "fake-compose-invite-user-template");
            };
            return function () {
                assert.ok(called);
            };
        })(),
    ];

    mentioned = {
        email: "foo@bar.com",
        user_id: 34,
        full_name: "Foo Barson",
    };

    stream_data.add_sub(sub);
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), true);

    for (const f of checks) {
        f();
    }

    // Simulate that the row was added to the DOM.
    const warning_row = $("<warning row>");

    let looked_for_existing;
    warning_row.data = (field) => {
        if (field === "user-id") {
            looked_for_existing = true;
            return "34";
        }
        if (field === "stream-id") {
            return "111";
        }
        throw new Error(`Unknown field ${field}`);
    };

    const previous_users = $("#compose_invite_users .compose_invite_user");
    previous_users.length = 1;
    previous_users[0] = warning_row;
    $("#compose_invite_users").hide();

    // Now try to mention the same person again. The template should
    // not render.
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), true);
    assert.ok(looked_for_existing);
});
