"use strict";

const {strict: assert} = require("assert");

const {stub_templates} = require("../zjsunit/handlebars");
const {$t_html} = require("../zjsunit/i18n");
const {mock_cjs, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

mock_cjs("jquery", $);

const noop = () => {};

set_global("document", {location: {}});
set_global("hash_util", {
    by_stream_uri: noop,
});

const channel = mock_esm("../../static/js/channel");
const compose_actions = mock_esm("../../static/js/compose_actions");
const compose_state = zrequire("compose_state");
const reminder = mock_esm("../../static/js/reminder");
const ui_util = mock_esm("../../static/js/ui_util");

const compose = zrequire("compose");
const compose_pm_pill = zrequire("compose_pm_pill");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
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

function test_ui(label, f) {
    // The sloppy_$ flag lets us re-use setup from prior tests.
    run_test(label, (override) => {
        $("#compose-textarea").val("some message");
        f(override);
    });
}

test_ui("validate_stream_message_address_info", () => {
    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };
    stream_data.add_sub(sub);
    assert(compose.validate_stream_message_address_info("social"));

    sub.subscribed = false;
    stream_data.add_sub(sub);
    stub_templates((template_name) => {
        assert.equal(template_name, "compose_not_subscribed");
        return "compose_not_subscribed_stub";
    });
    assert(!compose.validate_stream_message_address_info("social"));
    assert.equal($("#compose-error-msg").html(), "compose_not_subscribed_stub");

    page_params.narrow_stream = false;
    channel.post = (payload) => {
        assert.equal(payload.data.stream, "social");
        payload.data.subscribed = true;
        payload.success(payload.data);
    };
    assert(compose.validate_stream_message_address_info("social"));

    sub.name = "Frontend";
    sub.stream_id = 102;
    stream_data.add_sub(sub);
    channel.post = (payload) => {
        assert.equal(payload.data.stream, "Frontend");
        payload.data.subscribed = false;
        payload.success(payload.data);
    };
    assert(!compose.validate_stream_message_address_info("Frontend"));
    assert.equal($("#compose-error-msg").html(), "compose_not_subscribed_stub");

    channel.post = (payload) => {
        assert.equal(payload.data.stream, "Frontend");
        payload.error({status: 404});
    };
    assert(!compose.validate_stream_message_address_info("Frontend"));
    assert.equal(
        $("#compose-error-msg").html(),
        "translated HTML: <p>The stream <b>Frontend</b> does not exist.</p><p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>",
    );

    channel.post = (payload) => {
        assert.equal(payload.data.stream, "social");
        payload.error({status: 500});
    };
    assert(!compose.validate_stream_message_address_info("social"));
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Error checking subscription"}),
    );
});

test_ui("validate", (override) => {
    override(compose_actions, "update_placeholder_text", () => {});
    override(reminder, "is_deferred_delivery", () => false);

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

        stub_templates((fn) => {
            assert.equal(fn, "input_pill");
            return "<div>pill-html</div>";
        });
    }

    function add_content_to_compose_box() {
        $("#compose-textarea").val("foobarfoobar");
    }

    initialize_pm_pill();
    assert(!compose.validate());
    assert(!$("#sending-indicator").visible());
    assert(!$("#compose-send-button").is_focused());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "You have nothing to send!"}),
    );

    reminder.is_deferred_delivery = () => true;
    compose.validate();
    assert.equal($("#sending-indicator").text(), "translated: Scheduling...");
    reminder.is_deferred_delivery = () => {};

    add_content_to_compose_box();
    let zephyr_checked = false;
    $("#zephyr-mirror-error").is = () => {
        if (!zephyr_checked) {
            zephyr_checked = true;
            return true;
        }
        return false;
    };
    assert(!compose.validate());
    assert(zephyr_checked);
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
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("foo@zulip.com");

    assert(!compose.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    compose_state.private_message_recipient("foo@zulip.com,alice@zulip.com");
    assert(!compose.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify at least one valid recipient"}),
    );

    people.add_active_user(bob);
    compose_state.private_message_recipient("bob@example.com");
    assert(compose.validate());

    page_params.realm_is_zephyr_mirror_realm = true;
    assert(compose.validate());
    page_params.realm_is_zephyr_mirror_realm = false;

    compose_state.set_message_type("stream");
    compose_state.stream_name("");
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify a stream"}),
    );

    compose_state.stream_name("Denmark");
    page_params.realm_mandatory_topics = true;
    compose_state.topic("");
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Please specify a topic"}),
    );
});

test_ui("get_invalid_recipient_emails", (override) => {
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
    assert.deepEqual(compose.get_invalid_recipient_emails(), []);
});

test_ui("validate_stream_message", (override) => {
    override(reminder, "is_deferred_delivery", () => false);

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
    assert(compose.validate());
    assert(!$("#compose-all-everyone").visible());
    assert(!$("#compose-send-status").visible());

    peer_data.get_subscriber_count = (stream_id) => {
        assert.equal(stream_id, 101);
        return 16;
    };
    stub_templates((template_name, data) => {
        assert.equal(template_name, "compose_all_everyone");
        assert.equal(data.count, 16);
        return "compose_all_everyone_stub";
    });
    let compose_content;
    $("#compose-all-everyone").append = (data) => {
        compose_content = data;
    };

    override(compose, "wildcard_mention_allowed", () => true);
    compose_state.message_content("Hey @**all**");
    assert(!compose.validate());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert(!$("#compose-send-status").visible());
    assert.equal(compose_content, "compose_all_everyone_stub");
    assert($("#compose-all-everyone").visible());

    override(compose, "wildcard_mention_allowed", () => false);
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({
            defaultMessage: "You do not have permission to use wildcard mentions in this stream.",
        }),
    );
});

test_ui("test_validate_stream_message_post_policy_admin_only", (override) => {
    override(reminder, "is_deferred_delivery", () => false);

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
        role: stream_data.sub_role_values.member.code,
    };
    peer_data.get_subscriber_count = noop;

    compose_state.topic("subject102");
    compose_state.stream_name("stream102");
    stream_data.add_sub(sub);
    assert(!compose.validate());
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
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Only organization admins are allowed to post to this stream."}),
    );

    compose_state.topic("subject102");
    compose_state.stream_name("stream102");

    page_params.is_admin = true;
    page_params.is_guest = false;
    assert(compose.validate());

    page_params.is_admin = false;
    sub.role = stream_data.sub_role_values.stream_admin.code;
    assert(compose.validate());
});

test_ui("test_validate_stream_message_post_policy_moderators_only", (override) => {
    override(reminder, "is_deferred_delivery", () => false);

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
    assert(!compose.validate());
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

test_ui("test_validate_stream_message_post_policy_full_members_only", (override) => {
    override(reminder, "is_deferred_delivery", () => false);

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
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        $t_html({defaultMessage: "Guests are not allowed to post to this stream."}),
    );
});
