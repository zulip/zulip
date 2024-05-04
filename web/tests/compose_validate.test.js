"use strict";

const {strict: assert} = require("assert");

const {mock_banners} = require("./lib/compose_banner");
const {$t} = require("./lib/i18n");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {current_user, realm} = require("./lib/zpage_params");

const compose_banner = zrequire("compose_banner");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_state = zrequire("compose_state");
const compose_validate = zrequire("compose_validate");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const resolved_topic = zrequire("../shared/src/resolved_topic");
const settings_config = zrequire("settings_config");
const settings_data = mock_esm("../src/settings_data");
const stream_data = zrequire("stream_data");
const compose_recipient = zrequire("/compose_recipient");

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

const social_sub = {
    stream_id: 101,
    name: "social",
    subscribed: true,
};
stream_data.add_sub(social_sub);

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
    // The sloppy_$ flag lets us reuse setup from prior tests.
    run_test(label, (helpers) => {
        $("textarea#compose-textarea").val("some message");
        f(helpers);
    });
}

function stub_message_row($textarea) {
    const $stub = $.create("message_row_stub");
    $textarea.closest = (selector) => {
        assert.equal(selector, ".message_row");
        $stub.length = 0;
        return $stub;
    };
}

test_ui("validate_stream_message_address_info", ({mock_template}) => {
    mock_banners();

    const party_sub = {
        stream_id: 101,
        name: "party",
        subscribed: true,
    };
    stream_data.add_sub(party_sub);
    assert.ok(compose_validate.validate_stream_message_address_info(party_sub));

    party_sub.subscribed = false;
    stream_data.add_sub(party_sub);
    $("#compose_banners .user_not_subscribed").length = 0;
    let user_not_subscribed_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", true, (data, html) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.user_not_subscribed);
        user_not_subscribed_rendered = true;
        return html;
    });
    assert.ok(!compose_validate.validate_stream_message_address_info(party_sub));
    assert.ok(user_not_subscribed_rendered);

    party_sub.name = "Frontend";
    party_sub.stream_id = 102;
    stream_data.add_sub(party_sub);
    user_not_subscribed_rendered = false;
    assert.ok(!compose_validate.validate_stream_message_address_info(party_sub));
    assert.ok(user_not_subscribed_rendered);
});

test_ui("validate", ({mock_template}) => {
    function initialize_pm_pill() {
        $.clear_all_elements();

        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $("#compose-send-button .loader").hide();

        const $pm_pill_container = $.create("fake-pm-pill-container");
        $("#private_message_recipient")[0] = {};
        $("#private_message_recipient").set_parent($pm_pill_container);
        $pm_pill_container.set_find_results(".input", $("#private_message_recipient"));
        $("#private_message_recipient").before = noop;

        compose_pm_pill.initialize({
            on_pill_create_or_remove: compose_recipient.update_placeholder_text,
        });

        $("#zephyr-mirror-error").is = noop;

        mock_template("input_pill.hbs", false, () => "<div>pill-html</div>");

        mock_banners();
    }

    function add_content_to_compose_box() {
        $("textarea#compose-textarea").val("foobarfoobar");
    }

    // test validating direct messages
    compose_state.set_message_type("private");

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("");
    let pm_recipient_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.missing_private_message_recipient);
        assert.equal(
            data.banner_text,
            $t({defaultMessage: "Please specify at least one valid recipient."}),
        );
        pm_recipient_error_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(pm_recipient_error_rendered);

    pm_recipient_error_rendered = false;

    people.add_active_user(bob);
    compose_state.private_message_recipient("bob@example.com");
    assert.ok(compose_validate.validate());
    assert.ok(!pm_recipient_error_rendered);

    people.deactivate(bob);
    let deactivated_user_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.deactivated_user);
        assert.equal(
            data.banner_text,
            $t({defaultMessage: "You cannot send messages to deactivated users."}),
        );
        deactivated_user_error_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(deactivated_user_error_rendered);

    realm.realm_is_zephyr_mirror_realm = true;
    assert.ok(compose_validate.validate());
    realm.realm_is_zephyr_mirror_realm = false;

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("welcome-bot@example.com");
    assert.ok(compose_validate.validate());

    let zephyr_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        if (data.classname === compose_banner.CLASSNAMES.zephyr_not_running) {
            assert.equal(
                data.banner_text,
                $t({
                    defaultMessage:
                        "You need to be running Zephyr mirroring in order to send messages!",
                }),
            );
            zephyr_error_rendered = true;
        }
        return "<banner-stub>";
    });
    initialize_pm_pill();
    compose_state.private_message_recipient("welcome-bot@example.com");
    $("textarea#compose-textarea").toggleClass = (classname, value) => {
        assert.equal(classname, "invalid");
        assert.equal(value, true);
    };
    assert.ok(!compose_validate.validate());
    assert.ok(!$("#compose-send-button .loader").visible());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    compose_validate.validate();

    add_content_to_compose_box();
    let zephyr_checked = false;
    $("#zephyr-mirror-error").is = (arg) => {
        assert.equal(arg, ":visible");
        zephyr_checked = true;
        return true;
    };
    assert.ok(!compose_validate.validate());
    assert.ok(zephyr_checked);
    assert.ok(zephyr_error_rendered);

    initialize_pm_pill();
    add_content_to_compose_box();

    // test validating stream messages
    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    let empty_stream_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.missing_stream);
        assert.equal(data.banner_text, $t({defaultMessage: "Please specify a channel."}));
        empty_stream_error_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(empty_stream_error_rendered);

    const denmark = {
        stream_id: 100,
        name: "Denmark",
    };
    stream_data.add_sub(denmark);
    compose_state.set_stream_id(denmark.stream_id);
    realm.realm_mandatory_topics = true;
    compose_state.topic("");
    let missing_topic_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.topic_missing);
        assert.equal(
            data.banner_text,
            $t({defaultMessage: "Topics are required in this organization."}),
        );
        missing_topic_error_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(missing_topic_error_rendered);

    missing_topic_error_rendered = false;
    compose_state.topic("(no topic)");
    assert.ok(!compose_validate.validate());
    assert.ok(missing_topic_error_rendered);
});

test_ui("get_invalid_recipient_emails", ({override_rewire}) => {
    const welcome_bot = {
        email: "welcome-bot@example.com",
        user_id: 124,
        full_name: "Welcome Bot",
    };

    current_user.user_id = me.user_id;

    const params = {};
    params.realm_users = [];
    params.realm_non_active_users = [];
    params.cross_realm_bots = [welcome_bot];

    people.initialize(current_user.user_id, params);

    override_rewire(compose_state, "private_message_recipient", () => "welcome-bot@example.com");
    assert.deepEqual(compose_validate.get_invalid_recipient_emails(), []);
});

test_ui("test_stream_wildcard_mention_allowed", ({override_rewire}) => {
    current_user.user_id = me.user_id;

    // First, check for large streams (>15 subscribers) where the wildcard mention
    // policy matters.
    override_rewire(peer_data, "get_subscriber_count", () => 16);

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_everyone.code;
    current_user.is_guest = true;
    current_user.is_admin = false;
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.nobody.code;
    current_user.is_admin = true;
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_members.code;
    current_user.is_guest = true;
    current_user.is_admin = false;
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    current_user.is_guest = false;
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_moderators_only.code;
    current_user.is_moderator = false;
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    current_user.is_moderator = true;
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_admins_only.code;
    current_user.is_admin = false;
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    // TODO: Add a by_admins_only case when we implement stream-level administrators.

    current_user.is_admin = true;
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_full_members.code;
    const person = people.get_by_user_id(current_user.user_id);
    person.date_joined = new Date(Date.now());
    realm.realm_waiting_period_threshold = 10;

    assert.ok(compose_validate.stream_wildcard_mention_allowed());
    current_user.is_admin = false;
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    // Now, check for small streams (<=15 subscribers) where the wildcard mention
    // policy doesn't matter; everyone is allowed to use wildcard mentions.
    override_rewire(peer_data, "get_subscriber_count", () => 14);
    realm.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_admins_only.code;
    current_user.is_admin = false;
    current_user.is_guest = true;
    assert.ok(compose_validate.stream_wildcard_mention_allowed());
});

test_ui("validate_stream_message", ({override_rewire, mock_template}) => {
    // This test is in kind of continuation to test_validate but since it is
    // primarily used to get coverage over functions called from validate()
    // we are separating it up in different test. Though their relative position
    // of execution should not be changed.
    mock_banners();
    current_user.user_id = me.user_id;
    realm.realm_mandatory_topics = false;

    const special_sub = {
        stream_id: 101,
        name: "special",
        subscribed: true,
    };
    stream_data.add_sub(special_sub);

    compose_state.set_stream_id(special_sub.stream_id);
    assert.ok(compose_validate.validate());
    assert.ok(!$("#compose-all-everyone").visible());

    override_rewire(peer_data, "get_subscriber_count", (stream_id) => {
        assert.equal(stream_id, 101);
        return 16;
    });
    let stream_wildcard_warning_rendered = false;
    $("#compose_banner_area .wildcard_warning").length = 0;
    mock_template("compose_banner/stream_wildcard_warning.hbs", false, (data) => {
        stream_wildcard_warning_rendered = true;
        assert.equal(data.subscriber_count, 16);
        return "<banner-stub>";
    });

    override_rewire(compose_validate, "wildcard_mention_policy_authorizes_user", () => true);
    compose_state.message_content("Hey @**all**");
    assert.ok(!compose_validate.validate());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert.ok(stream_wildcard_warning_rendered);

    let wildcards_not_allowed_rendered = false;
    mock_template("compose_banner/wildcard_mention_not_allowed_error.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.wildcards_not_allowed);
        assert.equal(data.wildcard_mention_string, "all");
        wildcards_not_allowed_rendered = true;
        return "<banner-stub>";
    });
    override_rewire(compose_validate, "wildcard_mention_policy_authorizes_user", () => false);
    assert.ok(!compose_validate.validate());
    assert.ok(wildcards_not_allowed_rendered);
});

test_ui("test_validate_stream_message_post_policy_admin_only", ({mock_template}) => {
    // This test is in continuation with test_validate but it has been separated out
    // for better readability. Their relative position of execution should not be changed.
    // Although the position with respect to test_validate_stream_message does not matter
    // as different stream is used for this test.
    mock_banners();
    current_user.is_admin = false;
    const sub_stream_102 = {
        stream_id: 102,
        name: "stream102",
        subscribed: true,
        stream_post_policy: settings_config.stream_post_policy_values.admins.code,
    };

    stream_data.add_sub(sub_stream_102);
    compose_state.topic("topic102");
    compose_state.set_stream_id(sub_stream_102.stream_id);

    let banner_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.no_post_permissions);
        assert.equal(
            data.banner_text,
            $t({
                defaultMessage: "You do not have permission to post in this channel.",
            }),
        );
        banner_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);

    // Reset error message.
    compose_state.set_stream_id(social_sub.stream_id);

    current_user.is_admin = false;
    current_user.is_guest = true;

    compose_state.topic("topic102");
    compose_state.set_stream_id(sub_stream_102.stream_id);
    banner_rendered = false;
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);
});

test_ui("test_validate_stream_message_post_policy_moderators_only", ({mock_template}) => {
    mock_banners();

    current_user.is_admin = false;
    current_user.is_moderator = false;
    current_user.is_guest = false;

    const sub = {
        stream_id: 104,
        name: "stream104",
        subscribed: true,
        stream_post_policy: settings_config.stream_post_policy_values.moderators.code,
    };

    stream_data.add_sub(sub);
    compose_state.topic("topic104");
    compose_state.set_stream_id(sub.stream_id);
    let banner_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.no_post_permissions);
        assert.equal(
            data.banner_text,
            $t({
                defaultMessage: "You do not have permission to post in this channel.",
            }),
        );
        banner_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);
    // Reset error message.
    compose_state.set_stream_id(social_sub.stream_id);

    current_user.is_guest = true;
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);
});

test_ui("test_validate_stream_message_post_policy_full_members_only", ({mock_template}) => {
    mock_banners();
    current_user.is_admin = false;
    current_user.is_guest = true;
    const sub = {
        stream_id: 103,
        name: "stream103",
        subscribed: true,
        stream_post_policy: settings_config.stream_post_policy_values.non_new_members.code,
    };

    stream_data.add_sub(sub);
    compose_state.topic("topic103");
    compose_state.set_stream_id(sub.stream_id);
    let banner_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.no_post_permissions);
        assert.equal(
            data.banner_text,
            $t({
                defaultMessage: "You do not have permission to post in this channel.",
            }),
        );
        banner_rendered = true;
        return "<banner-stub>";
    });
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);
});

test_ui("test_check_overflow_text", ({mock_template}) => {
    realm.max_message_length = 10000;

    const $textarea = $("textarea#compose-textarea");
    const $indicator = $("#compose-limit-indicator");

    // Indicator should show red colored text
    let limit_indicator_html;
    mock_template("compose_limit_indicator.hbs", true, (_data, html) => {
        limit_indicator_html = html;
    });
    $textarea.val("a".repeat(10000 + 1));
    compose_validate.check_overflow_text();
    assert.ok($indicator.hasClass("over_limit"));
    assert.equal(limit_indicator_html, "-1\n");
    assert.ok($textarea.hasClass("over_limit"));
    assert.ok($(".message-send-controls").hasClass("disabled-message-send-controls"));

    // Indicator should show orange colored text
    $textarea.val("a".repeat(9100));
    compose_validate.check_overflow_text();
    assert.ok(!$indicator.hasClass("over_limit"));
    assert.equal(limit_indicator_html, "900\n");
    assert.ok(!$textarea.hasClass("over_limit"));
    assert.ok(!$(".message-send-controls").hasClass("disabled-message-send-controls"));

    // Indicator must be empty
    $textarea.val("a".repeat(9100 - 1));
    compose_validate.check_overflow_text();
    assert.ok(!$indicator.hasClass("over_limit"));
    assert.equal($indicator.text(), "");
    assert.ok(!$textarea.hasClass("over_limit"));
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

    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id");
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
    const $textarea = $("<textarea>").attr("id", "compose-textarea");
    stub_message_row($textarea);
    const test_sub = {
        name: compose_state.stream_name(),
        stream_id: 99,
    };

    stream_data.add_sub(test_sub);
    peer_data.set_subscribers(test_sub.stream_id, [1, 2]);

    const denmark = {
        stream_id: 100,
        name: "Denmark",
    };
    stream_data.add_sub(denmark);

    peer_data.set_subscribers(denmark.stream_id, [1, 2, 3]);

    let banner_rendered = false;
    mock_template("compose_banner/private_stream_warning.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.private_stream_warning);
        assert.equal(data.channel_name, "Denmark");
        banner_rendered = true;
        return "<banner-stub>";
    });

    function test_noop_case(invite_only) {
        banner_rendered = false;
        compose_state.set_message_type("stream");
        denmark.invite_only = invite_only;
        compose_validate.warn_if_private_stream_is_linked(denmark, $textarea);
        assert.ok(!banner_rendered);
    }

    test_noop_case(false);
    // invite_only=true and current compose stream subscribers are a subset
    // of mentioned_stream subscribers.
    test_noop_case(true);

    $("#compose_private").hide();
    compose_state.set_message_type("stream");

    // Not everyone is subscribed to secret_stream in denmark, so the
    // warning is rendered.
    compose_state.set_selected_recipient_id(denmark.stream_id);
    const secret_stream = {
        invite_only: true,
        name: "Denmark",
        stream_id: 22,
    };
    stream_data.add_sub(secret_stream);
    banner_rendered = false;
    const $banner_container = $("#compose_banners");
    $banner_container.set_find_results(".private_stream_warning", []);
    compose_validate.warn_if_private_stream_is_linked(secret_stream, $textarea);
    assert.ok(banner_rendered);

    // Simulate that the row was added to the DOM.
    const $warning_row = $("#compose_banners .private_stream_warning");
    $warning_row.attr("data-stream-id", "22");
    $("#compose_banners .private_stream_warning").length = 1;
    $("#compose_banners .private_stream_warning")[0] = $warning_row;

    // Now try to mention the same stream again. The template should
    // not render.
    banner_rendered = false;
    $banner_container.set_find_results(".private_stream_warning", $warning_row);
    compose_validate.warn_if_private_stream_is_linked(secret_stream, $textarea);
    assert.ok(!banner_rendered);
});

test_ui("warn_if_mentioning_unsubscribed_user", ({override, mock_template}) => {
    const $textarea = $("<textarea>").attr("id", "compose-textarea");
    stub_message_row($textarea);
    compose_state.set_stream_id("");
    override(settings_data, "user_can_subscribe_other_users", () => true);

    let mentioned_details = {
        email: "foo@bar.com",
    };

    let new_banner_rendered = false;
    mock_template("compose_banner/not_subscribed_warning.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.recipient_not_subscribed);
        assert.equal(data.user_id, 34);
        assert.equal(data.stream_id, 111);
        assert.equal(data.name, "Foo Barson");
        new_banner_rendered = true;
        return "<banner-stub>";
    });

    function test_noop_case(is_private, is_zephyr_mirror, is_broadcast) {
        new_banner_rendered = false;
        const msg_type = is_private ? "private" : "stream";
        compose_state.set_message_type(msg_type);
        realm.realm_is_zephyr_mirror_realm = is_zephyr_mirror;
        mentioned_details.is_broadcast = is_broadcast;
        compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
        assert.ok(!new_banner_rendered);
    }

    test_noop_case(true, false, false);
    test_noop_case(false, true, false);
    test_noop_case(false, false, true);

    $("#compose_invite_users").hide();
    compose_state.set_message_type("stream");
    realm.realm_is_zephyr_mirror_realm = false;

    // Test with empty stream name in compose box. It should return noop.
    new_banner_rendered = false;
    assert.equal(compose_state.stream_name(), "");
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);

    const sub = {
        stream_id: 111,
        name: "random",
    };
    stream_data.add_sub(sub);
    compose_state.set_stream_id(sub.stream_id);

    // Test with invalid stream in compose box. It should return noop.
    new_banner_rendered = false;
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);

    // Test mentioning a user that should gets a warning.
    mentioned_details = {
        email: "foo@bar.com",
        user_id: 34,
        full_name: "Foo Barson",
    };
    people.add_active_user(mentioned_details);

    new_banner_rendered = false;
    const $banner_container = $("#compose_banners");
    $banner_container.set_find_results(".recipient_not_subscribed", []);

    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(new_banner_rendered);

    // Simulate that the row was added to the DOM.
    const $warning_row = $("#compose_banners .recipient_not_subscribed");
    $warning_row.attr("data-user-id", "34");
    $warning_row.attr("data-stream-id", "111");
    $("#compose_banners .recipient_not_subscribed").length = 1;
    $("#compose_banners .recipient_not_subscribed")[0] = $warning_row;

    // Now try to mention the same person again. The template should
    // not render.
    new_banner_rendered = false;
    $banner_container.set_find_results(".recipient_not_subscribed", $warning_row);
    compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);
});

test_ui("test warn_if_topic_resolved", ({override, mock_template}) => {
    mock_banners();
    $("#compose_banners .topic_resolved").length = 0;
    override(settings_data, "user_can_move_messages_to_another_topic", () => true);

    let error_shown = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.topic_resolved);
        assert.equal(
            data.banner_text,
            $t({
                defaultMessage:
                    "You are sending a message to a resolved topic. You can send as-is or unresolve the topic first.",
            }),
        );
        error_shown = true;
        return "<banner-stub>";
    });

    const sub = {
        stream_id: 111,
        name: "random",
    };
    stream_data.add_sub(sub);

    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    compose_state.topic(resolved_topic.resolve_name("hello"));
    compose_state.message_content("content");

    error_shown = false;
    compose_validate.warn_if_topic_resolved(true);
    assert.ok(!error_shown);

    compose_state.set_stream_id(sub.stream_id);

    // Show the warning now as stream also exists
    error_shown = false;
    compose_validate.warn_if_topic_resolved(true);
    assert.ok(error_shown);

    // We reset the state to be able to show the banner again
    compose_state.set_recipient_viewed_topic_resolved_banner(false);

    // Call it again with false; this should do the same thing.
    error_shown = false;
    compose_validate.warn_if_topic_resolved(false);
    assert.ok(error_shown);

    // Call the func again. This should not show the error because
    // we have already shown the error once for this topic.
    error_shown = false;
    compose_validate.warn_if_topic_resolved(false);
    assert.ok(!error_shown);

    compose_state.topic("hello");

    // The warning will be cleared now
    error_shown = false;
    compose_validate.warn_if_topic_resolved(true);
    assert.ok(!error_shown);

    // Calling with false won't do anything.
    error_shown = false;
    compose_validate.warn_if_topic_resolved(false);
    assert.ok(!error_shown);
});
