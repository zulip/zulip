"use strict";

const assert = require("node:assert/strict");

const {mock_banners} = require("./lib/compose_banner.cjs");
const {FakeComposeBox} = require("./lib/compose_helpers.cjs");
const {$t} = require("./lib/i18n.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");

const compose_banner = zrequire("compose_banner");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_state = zrequire("compose_state");
const compose_validate = zrequire("compose_validate");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const resolved_topic = zrequire("../shared/src/resolved_topic");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const compose_recipient = zrequire("/compose_recipient");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");

mock_esm("../src/ui_util", {
    place_caret_at_end: noop,
});

mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config: () => ({
        allow_everyone_group: true,
    }),
});

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";
const realm = {realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const user_settings = {default_language: "en"};
initialize_user_settings({user_settings});

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
    is_admin: true,
};

const guest = {
    email: "guest@example.com",
    user_id: 33,
    full_name: "Guest",
    is_guest: true,
};

const moderator = {
    email: "moderator@example.com",
    user_id: 34,
    full_name: "Charlie",
    is_moderator: true,
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
people.add_active_user(guest);

const welcome_bot = {
    email: "welcome-bot@example.com",
    user_id: 4,
    full_name: "Welcome Bot",
    is_bot: true,
    // cross realm bots have no owner
};

people.add_cross_realm_user(welcome_bot);

const nobody = {
    name: "role:nobody",
    id: 1,
    members: new Set([]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
const everyone = {
    name: "role:everyone",
    id: 2,
    members: new Set([30, 33]),
    is_system_group: true,
    direct_subgroup_ids: new Set([5]),
};
const admin = {
    name: "role:administrators",
    id: 3,
    members: new Set([32]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
const moderators = {
    name: "role:moderators",
    id: 4,
    members: new Set([34]),
    is_system_group: true,
    direct_subgroup_ids: new Set([3]),
};
const members = {
    name: "role:members",
    id: 5,
    members: new Set([31]),
    is_system_group: true,
    direct_subgroup_ids: new Set([4]),
};

user_groups.initialize({realm_user_groups: [nobody, everyone, admin, moderators, members]});
function test_ui(label, f) {
    run_test(label, (helpers) => {
        $("textarea#compose-textarea").val("some message");
        return f(helpers);
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

function initialize_pm_pill(mock_template) {
    $.clear_all_elements();

    $(".message_comp").css = (property) => {
        assert.equal(property, "display");
        return "block";
    };
    $("#compose-send-button").trigger("focus");
    $("#compose-send-button .loader").hide();

    const $pm_pill_container = $.create("fake-pm-pill-container");
    $("#private_message_recipient")[0] = {};
    $("#private_message_recipient").set_parent($pm_pill_container);
    $pm_pill_container.set_find_results(".input", $("#private_message_recipient"));
    $("#private_message_recipient").before = noop;

    compose_pm_pill.initialize({
        on_pill_create_or_remove: compose_recipient.update_compose_area_placeholder_text,
    });

    mock_template("input_pill.hbs", false, () => "<div>pill-html</div>");

    mock_banners();
}

test_ui("validate_stream_message_address_info", ({mock_template, override}) => {
    // For this test we basically only use FakeComposeBox
    // to set up the DOM environment. We don't assert about
    // any side effects on the DOM, since the scope of this
    // test is mostly to make sure the template gets rendered.
    new FakeComposeBox();

    override(realm, "realm_can_access_all_users_group", everyone.id);

    const party_sub = {
        stream_id: 101,
        name: "party",
        subscribed: true,
        can_add_subscribers_group: nobody.id,
        can_subscribe_group: nobody.id,
    };
    stream_data.add_sub(party_sub);
    assert.ok(compose_validate.validate_stream_message_address_info(party_sub));

    party_sub.subscribed = false;
    stream_data.add_sub(party_sub);
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

test_ui("validate", ({mock_template, override}) => {
    function add_content_to_compose_box() {
        $("textarea#compose-textarea").val("foobarfoobar");
    }

    override(realm, "realm_can_access_all_users_group", everyone.id);

    // test validating direct messages
    compose_state.set_message_type("private");

    initialize_pm_pill(mock_template);
    add_content_to_compose_box();
    compose_state.private_message_recipient_emails("");
    let pm_recipient_error_rendered = false;
    override(realm, "realm_direct_message_permission_group", everyone.id);
    override(realm, "realm_direct_message_initiator_group", everyone.id);
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.missing_private_message_recipient);
        assert.equal(data.banner_text, compose_validate.NO_PRIVATE_RECIPIENT_ERROR_MESSAGE);
        pm_recipient_error_rendered = true;
        return "<banner-stub>";
    });
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
    assert.ok(!compose_validate.validate());
    assert.ok(pm_recipient_error_rendered);

    pm_recipient_error_rendered = false;

    people.add_active_user(bob);
    compose_state.private_message_recipient_emails("bob@example.com");
    assert.ok(compose_validate.validate());
    assert.ok(!pm_recipient_error_rendered);

    override(realm, "realm_direct_message_initiator_group", admin.id);
    assert.ok(compose_validate.validate());
    assert.ok(!pm_recipient_error_rendered);

    override(realm, "realm_direct_message_permission_group", admin.id);
    assert.ok(compose_validate.validate());
    assert.ok(!pm_recipient_error_rendered);

    override(realm, "realm_direct_message_initiator_group", everyone.id);
    override(realm, "realm_direct_message_permission_group", everyone.id);
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

    override(realm, "realm_is_zephyr_mirror_realm", true);
    assert.ok(compose_validate.validate());
    override(realm, "realm_is_zephyr_mirror_realm", false);

    initialize_pm_pill(mock_template);
    add_content_to_compose_box();
    compose_state.private_message_recipient_emails("welcome-bot@example.com");
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
    assert.ok(compose_validate.validate());

    let zephyr_error_rendered = false;
    // For this first block, we should fail due to empty compose.
    let expected_invalid_state = true;
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
    initialize_pm_pill(mock_template);
    compose_state.private_message_recipient_emails("welcome-bot@example.com");
    $("textarea#compose-textarea").toggleClass = (classname, value) => {
        assert.equal(classname, "invalid");
        assert.equal(value, expected_invalid_state);
    };
    assert.ok(!compose_validate.validate());
    assert.ok(!$("#compose-send-button .loader").visible());
    compose_validate.validate();

    // Now add content to compose, and expect to see the banner.
    add_content_to_compose_box();
    expected_invalid_state = false;
    $("#zephyr-mirror-error").addClass("show");
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
    assert.ok(!compose_validate.validate());
    assert.ok(zephyr_error_rendered);

    initialize_pm_pill(mock_template);
    add_content_to_compose_box();

    // test validating stream messages
    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    let empty_stream_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.missing_stream);
        assert.equal(data.banner_text, compose_validate.NO_CHANNEL_SELECTED_ERROR_MESSAGE);
        empty_stream_error_rendered = true;
        return "<banner-stub>";
    });
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
    assert.ok(!compose_validate.validate());
    assert.ok(empty_stream_error_rendered);

    const denmark = {
        stream_id: 100,
        name: "Denmark",
    };
    stream_data.add_sub(denmark);
    compose_state.set_stream_id(denmark.stream_id);
    override(realm, "realm_topics_policy", "disable_empty_topic");
    let missing_topic_error_rendered = false;
    mock_template("compose_banner/compose_banner.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.topic_missing);
        missing_topic_error_rendered = true;
        return "<banner-stub>";
    });

    for (const topic_name of ["", "(no topic)", `translated: ${REALM_EMPTY_TOPIC_DISPLAY_NAME}`]) {
        compose_state.topic(topic_name);
        missing_topic_error_rendered = false;
        assert.ok(!compose_validate.validate());
        assert.ok(missing_topic_error_rendered);
    }
});

test_ui("test_stream_wildcard_mention_allowed", ({override, override_rewire}) => {
    override(current_user, "user_id", me.user_id);

    // First, check for large streams (>15 subscribers) where the wildcard mention
    // policy matters.
    override_rewire(peer_data, "get_subscriber_count", () => 16);

    override(realm, "realm_can_mention_many_users_group", everyone.id);
    override(current_user, "user_id", guest.user_id);
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    override(realm, "realm_can_mention_many_users_group", nobody.id);
    override(current_user, "user_id", bob.user_id);
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    override(realm, "realm_can_mention_many_users_group", members.id);
    override(current_user, "user_id", guest.user_id);
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    override(current_user, "user_id", alice.user_id);
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    override(realm, "realm_can_mention_many_users_group", moderators.id);
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    override(current_user, "user_id", moderator.user_id);
    assert.ok(compose_validate.stream_wildcard_mention_allowed());

    override(realm, "realm_can_mention_many_users_group", admin.id);
    override(current_user, "user_id", moderator.user_id);
    assert.ok(!compose_validate.stream_wildcard_mention_allowed());

    // TODO: Add a by_admins_only case when we implement stream-level administrators.

    override(current_user, "user_id", bob.user_id);
    assert.ok(compose_validate.stream_wildcard_mention_allowed());
});

test_ui("validate_stream_message", ({override, override_rewire, mock_template}) => {
    // This test is in kind of continuation to test_validate but since it is
    // primarily used to get coverage over functions called from validate()
    // we are separating it up in different test. Though their relative position
    // of execution should not be changed.
    mock_banners();
    override(current_user, "user_id", me.user_id);
    override(realm, "realm_topics_policy", "allow_empty_topic");

    const special_sub = {
        stream_id: 101,
        name: "special",
        subscribed: true,
        can_send_message_group: everyone.id,
        topics_policy: "inherit",
    };
    stream_data.add_sub(special_sub);

    compose_state.set_stream_id(special_sub.stream_id);
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
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

    override(realm, "realm_can_mention_many_users_group", everyone.id);
    compose_state.message_content("Hey @**all**");
    assert.ok(!compose_validate.validate());
    assert.ok(stream_wildcard_warning_rendered);

    let wildcards_not_allowed_rendered = false;
    mock_template("compose_banner/wildcard_mention_not_allowed_error.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.wildcards_not_allowed);
        assert.equal(data.wildcard_mention_string, "all");
        wildcards_not_allowed_rendered = true;
        return "<banner-stub>";
    });
    override(realm, "realm_can_mention_many_users_group", admin.id);
    assert.ok(!compose_validate.validate());
    assert.ok(wildcards_not_allowed_rendered);
});

test_ui("test_stream_posting_permission", ({mock_template, override}) => {
    mock_banners();

    override(current_user, "user_id", 30);
    const sub_stream_102 = {
        stream_id: 102,
        name: "stream102",
        subscribed: true,
        can_send_message_group: admin.id,
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
    $("#send_message_form").set_find_results(".message-textarea", $("textarea#compose-textarea"));
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);

    override(current_user, "user_id", 32);

    banner_rendered = false;
    assert.ok(compose_validate.validate());
    assert.ok(!banner_rendered);

    sub_stream_102.can_send_message_group = everyone.id;
    override(current_user, "user_id", 30);
    banner_rendered = false;
    assert.ok(compose_validate.validate());
    assert.ok(!banner_rendered);

    // Reset error message.
    compose_state.set_stream_id(social_sub.stream_id);

    const anonymous_setting_group = {
        direct_subgroups: [admin.id],
        direct_members: [31],
    };
    sub_stream_102.can_send_message_group = anonymous_setting_group;

    compose_state.topic("topic102");
    compose_state.set_stream_id(sub_stream_102.stream_id);
    override(current_user, "user_id", 30);
    banner_rendered = false;
    assert.ok(!compose_validate.validate());
    assert.ok(banner_rendered);

    override(current_user, "user_id", 31);
    banner_rendered = false;
    assert.ok(compose_validate.validate());
    assert.ok(!banner_rendered);

    override(current_user, "user_id", 32);
    banner_rendered = false;
    assert.ok(compose_validate.validate());
    assert.ok(!banner_rendered);
});

test_ui("test_check_overflow_text", ({override, override_rewire}) => {
    const fake_compose_box = new FakeComposeBox();

    override_rewire(compose_validate, "validate_and_update_send_button_status", noop);
    override(realm, "max_message_length", 10000);

    // RED
    {
        fake_compose_box.set_textarea_val("a".repeat(10005));
        compose_validate.check_overflow_text(fake_compose_box.$send_message_form);
        fake_compose_box.assert_message_size_is_over_the_limit("-5\n");
    }

    // ORANGE
    {
        fake_compose_box.set_textarea_val("a".repeat(9100));
        compose_validate.check_overflow_text(fake_compose_box.$send_message_form);
        fake_compose_box.assert_message_size_is_under_the_limit("900\n");
    }

    // ALL CLEAR
    {
        fake_compose_box.set_textarea_val("a".repeat(9100 - 1));
        compose_validate.check_overflow_text(fake_compose_box.$send_message_form);
        fake_compose_box.assert_message_size_is_under_the_limit();
    }
});

test_ui("needs_subscribe_warning", async () => {
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
    assert.equal(
        await compose_validate.needs_subscribe_warning(invalid_user_id, sub.stream_id),
        false,
    );

    // Test with bot user.
    assert.equal(
        await compose_validate.needs_subscribe_warning(test_bot.user_id, sub.stream_id),
        false,
    );

    // Test when user is subscribed to the stream.
    assert.equal(await compose_validate.needs_subscribe_warning(bob.user_id, sub.stream_id), false);

    peer_data.remove_subscriber(sub.stream_id, bob.user_id);
    // Test when the user is not subscribed.
    assert.equal(await compose_validate.needs_subscribe_warning(bob.user_id, sub.stream_id), true);
});

test_ui("warn_if_private_stream_is_linked", async ({mock_template}) => {
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

    async function test_noop_case(invite_only) {
        banner_rendered = false;
        compose_state.set_message_type("stream");
        denmark.invite_only = invite_only;
        await compose_validate.warn_if_private_stream_is_linked(denmark, $textarea);
        assert.ok(!banner_rendered);
    }

    compose_state.set_selected_recipient_id(undefined);
    void test_noop_case(false);
    // invite_only=true and current compose stream subscribers are a subset
    // of mentioned_stream subscribers.
    void test_noop_case(true);

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
    peer_data.set_subscribers(secret_stream.stream_id, []);
    stream_data.add_sub(secret_stream);
    banner_rendered = false;
    const $banner_container = $("#compose_banners");
    $banner_container.set_find_results(".private_stream_warning", []);
    await compose_validate.warn_if_private_stream_is_linked(secret_stream, $textarea);
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
    await compose_validate.warn_if_private_stream_is_linked(secret_stream, $textarea);
    assert.ok(!banner_rendered);
});

test_ui("warn_if_mentioning_unsubscribed_user", async ({override, mock_template}) => {
    const $textarea = $("<textarea>").attr("id", "compose-textarea");
    stub_message_row($textarea);
    compose_state.set_stream_id("");

    override(realm, "realm_can_add_subscribers_group", everyone.id);

    let mentioned_details = {
        user: {
            email: "foo@bar.com",
        },
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

    async function test_noop_case(is_private, is_zephyr_mirror, type) {
        new_banner_rendered = false;
        const msg_type = is_private ? "private" : "stream";
        compose_state.set_message_type(msg_type);
        override(realm, "realm_is_zephyr_mirror_realm", is_zephyr_mirror);
        mentioned_details.type = type;
        await compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
        assert.ok(!new_banner_rendered);
    }

    await test_noop_case(true, false, "user");
    await test_noop_case(false, true, "user");
    await test_noop_case(false, false, "broadcast");

    $("#compose_invite_users").hide();
    compose_state.set_message_type("stream");
    override(realm, "realm_is_zephyr_mirror_realm", false);

    // Test with empty stream name in compose box. It should return noop.
    new_banner_rendered = false;
    assert.equal(compose_state.stream_name(), "");
    await compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);

    const sub = {
        stream_id: 111,
        name: "random",
        can_add_subscribers_group: admin.id,
        can_administer_channel_group: admin.id,
        can_subscribe_group: admin.id,
    };
    stream_data.add_sub(sub);
    compose_state.set_stream_id(sub.stream_id);

    // Test with invalid stream in compose box. It should return noop.
    new_banner_rendered = false;
    await compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);

    // Test mentioning a user that should get a warning.
    mentioned_details = {
        type: "user",
        user: {
            email: "foo@bar.com",
            user_id: 34,
            full_name: "Foo Barson",
        },
    };
    people.add_active_user(mentioned_details.user);

    new_banner_rendered = false;
    const $banner_container = $("#compose_banners");
    $banner_container.set_find_results(".recipient_not_subscribed", []);
    channel.get = (opts) => {
        assert.equal(opts.url, `/json/streams/${sub.stream_id}/members`);
        return {
            subscribers: [],
        };
    };

    await compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
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
    await compose_validate.warn_if_mentioning_unsubscribed_user(mentioned_details, $textarea);
    assert.ok(!new_banner_rendered);
});

test_ui("test warn_if_topic_resolved", ({override, mock_template}) => {
    mock_banners();
    $("#compose_banners .topic_resolved").length = 0;
    override(realm, "realm_can_resolve_topics_group", everyone.id);

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
        can_administer_channel_group: nobody.id,
        can_move_messages_out_of_channel_group: nobody.id,
        can_move_messages_within_channel_group: nobody.id,
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

test_ui("test_warn_if_guest_in_dm_recipient", ({mock_template, override}) => {
    let is_active = false;

    override(realm, "realm_can_access_all_users_group", everyone.id);

    mock_template("compose_banner/guest_in_dm_recipient_warning.hbs", false, (data) => {
        assert.equal(data.classname, compose_banner.CLASSNAMES.guest_in_dm_recipient_warning);
        assert.equal(
            data.banner_text,
            $t({defaultMessage: "Guest is a guest in this organization."}),
        );
        is_active = true;
        return "<banner-stub>";
    });

    compose_state.set_message_type("private");
    initialize_pm_pill(mock_template);
    compose_state.private_message_recipient_emails("guest@example.com");
    const classname = compose_banner.CLASSNAMES.guest_in_dm_recipient_warning;
    let $banner = $(`#compose_banners .${CSS.escape(classname)}`);

    // if setting is disabled, remove warning if exists
    realm.realm_enable_guest_user_dm_warning = false;
    compose_validate.warn_if_guest_in_dm_recipient();
    assert.ok(!is_active);

    // to show warning for guest emails, banner should be created
    realm.realm_enable_guest_user_dm_warning = true;
    $banner.length = 0;
    compose_validate.warn_if_guest_in_dm_recipient();
    assert.ok(is_active);
    assert.deepEqual(compose_state.get_recipient_guest_ids_for_dm_warning(), [33]);

    // don't show warning for same guests if user closed the banner.
    is_active = false;
    compose_validate.warn_if_guest_in_dm_recipient();
    assert.ok(!is_active);

    // on modifying the guest recipient, update banner if already shown.
    is_active = true;
    const new_guest = {
        email: "new_guest@example.com",
        user_id: 34,
        full_name: "New Guest",
        is_guest: true,
    };
    people.add_active_user(new_guest);

    initialize_pm_pill(mock_template);
    compose_state.private_message_recipient_emails("guest@example.com, new_guest@example.com");
    $banner = $(`#compose_banners .${CSS.escape(classname)}`);
    $banner.length = 1;
    let is_updated = false;
    $banner.set_find_results(".banner_content", {
        text(content) {
            assert.equal(
                content,
                $t({defaultMessage: "Guest and New Guest are guests in this organization."}),
            );
            is_updated = true;
        },
    });
    compose_validate.warn_if_guest_in_dm_recipient();
    assert.ok(is_updated);
    assert.deepEqual(compose_state.get_recipient_guest_ids_for_dm_warning(), [33, 34]);
});
