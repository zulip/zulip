"use strict";

const {strict: assert} = require("assert");

const {JSDOM} = require("jsdom");
const MockDate = require("mockdate");
const rewiremock = require("rewiremock/node");

const {stub_templates} = require("../zjsunit/handlebars");
const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

const events = require("./lib/events");

set_global("bridge", false);

const noop = function () {};

set_global("$", make_zjquery());
set_global("DOMParser", new JSDOM().window.DOMParser);
set_global("compose_actions", {
    update_placeholder_text: noop,
});

const _navigator = {
    platform: "",
};

const _document = {
    execCommand() {
        return false;
    },
    location: {},
};

const _drafts = {
    delete_draft_after_send: noop,
};

const _sent_messages = {
    start_tracking_message: noop,
};
const _notifications = {
    notify_above_composebox: noop,
    clear_compose_notifications: noop,
};
const _reminder = {
    is_deferred_delivery: noop,
};

set_global("document", _document);
set_global("drafts", _drafts);
set_global("navigator", _navigator);
set_global("notifications", _notifications);
set_global("reminder", _reminder);
set_global("sent_messages", _sent_messages);

set_global("local_message", {});
set_global("transmit", {});
set_global("channel", {});
set_global("stream_edit", {});
set_global("markdown", {});
set_global("loading", {});
set_global("page_params", {});
set_global("resize", {});
set_global("subs", {});
set_global("ui_util", {});

// Setting these up so that we can test that links to uploads within messages are
// automatically converted to server relative links.
document.location.protocol = "https:";
document.location.host = "foo.com";

const fake_now = 555;
MockDate.set(new Date(fake_now * 1000));

zrequire("zcommand");
zrequire("compose_ui");
const peer_data = zrequire("peer_data");
const util = zrequire("util");
zrequire("rtl");
zrequire("common");
zrequire("stream_data");
zrequire("compose_state");
const people = zrequire("people");
zrequire("input_pill");
zrequire("user_pill");
zrequire("compose_pm_pill");
zrequire("echo");
rewiremock.proxy(() => zrequire("compose"), {
    "../../static/js/rendered_markdown": {
        update_elements: () => {},
    },
});
zrequire("upload");
zrequire("server_events_dispatch");
const settings_config = zrequire("settings_config");

people.small_avatar_url_for_person = function () {
    return "http://example.com/example.png";
};

function stub_out_video_calls() {
    const elem = $("#below-compose-content .video_link");
    elem.toggle = (show) => {
        if (show) {
            elem.show();
        } else {
            elem.hide();
        }
    };
}

function reset_jquery() {
    // Avoid leaks.
    set_global("$", make_zjquery());
}

const new_user = {
    email: "new_user@example.com",
    user_id: 101,
    full_name: "New User",
    date_joined: new Date(),
};

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

people.add_active_user(new_user);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);

run_test("validate_stream_message_address_info", () => {
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
    channel.post = function (payload) {
        assert.equal(payload.data.stream, "social");
        payload.data.subscribed = true;
        payload.success(payload.data);
    };
    assert(compose.validate_stream_message_address_info("social"));

    sub.name = "Frontend";
    sub.stream_id = 102;
    stream_data.add_sub(sub);
    channel.post = function (payload) {
        assert.equal(payload.data.stream, "Frontend");
        payload.data.subscribed = false;
        payload.success(payload.data);
    };
    assert(!compose.validate_stream_message_address_info("Frontend"));
    assert.equal($("#compose-error-msg").html(), "compose_not_subscribed_stub");

    channel.post = function (payload) {
        assert.equal(payload.data.stream, "Frontend");
        payload.error({status: 404});
    };
    assert(!compose.validate_stream_message_address_info("Frontend"));
    assert.equal(
        $("#compose-error-msg").html(),
        "translated: <p>The stream <b>Frontend</b> does not exist.</p><p>Manage your subscriptions <a href='#streams/all'>on your Streams page</a>.</p>",
    );

    channel.post = function (payload) {
        assert.equal(payload.data.stream, "social");
        payload.error({status: 500});
    };
    assert(!compose.validate_stream_message_address_info("social"));
    assert.equal($("#compose-error-msg").html(), i18n.t("Error checking subscription"));
});

run_test("validate", () => {
    function initialize_pm_pill() {
        set_global("$", make_zjquery());

        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $("#sending-indicator").hide();

        const pm_pill_container = $.create("fake-pm-pill-container");
        $("#private_message_recipient")[0] = {};
        $("#private_message_recipient").set_parent(pm_pill_container);
        pm_pill_container.set_find_results(".input", $("#private_message_recipient"));
        $("#private_message_recipient").before = noop;

        compose_pm_pill.initialize();

        ui_util.place_caret_at_end = noop;

        $("#zephyr-mirror-error").is = noop;

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
    assert.equal($("#compose-error-msg").html(), i18n.t("You have nothing to send!"));

    reminder.is_deferred_delivery = () => true;
    compose.validate();
    assert.equal($("#sending-indicator").text(), "translated: Scheduling...");
    reminder.is_deferred_delivery = noop;

    add_content_to_compose_box();
    let zephyr_checked = false;
    $("#zephyr-mirror-error").is = function () {
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
        i18n.t("You need to be running Zephyr mirroring in order to send messages!"),
    );

    initialize_pm_pill();
    add_content_to_compose_box();

    // test validating private messages
    compose_state.set_message_type("private");

    compose_state.private_message_recipient("");
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        i18n.t("Please specify at least one valid recipient"),
    );

    initialize_pm_pill();
    add_content_to_compose_box();
    compose_state.private_message_recipient("foo@zulip.com");

    assert(!compose.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        i18n.t("Please specify at least one valid recipient", {}),
    );

    compose_state.private_message_recipient("foo@zulip.com,alice@zulip.com");
    assert(!compose.validate());

    assert.equal(
        $("#compose-error-msg").html(),
        i18n.t("Please specify at least one valid recipient", {}),
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
    assert.equal($("#compose-error-msg").html(), i18n.t("Please specify a stream"));

    compose_state.stream_name("Denmark");
    page_params.realm_mandatory_topics = true;
    compose_state.topic("");
    assert(!compose.validate());
    assert.equal($("#compose-error-msg").html(), i18n.t("Please specify a topic"));
});

run_test("get_invalid_recipient_emails", () => {
    const welcome_bot = {
        email: "welcome-bot@example.com",
        user_id: 124,
        full_name: "Welcome Bot",
    };

    page_params.user_id = 30;

    const params = {};
    params.realm_users = [];
    params.realm_non_active_users = [];
    params.cross_realm_bots = [welcome_bot];

    people.initialize(page_params.user_id, params);

    compose_state.private_message_recipient("welcome-bot@example.com");
    assert.deepEqual(compose.get_invalid_recipient_emails(), []);
});

run_test("test_wildcard_mention_allowed", () => {
    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_everyone.code;
    page_params.is_guest = true;
    page_params.is_admin = false;
    assert(compose.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.nobody.code;
    page_params.is_admin = true;
    assert(!compose.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_members.code;
    page_params.is_guest = true;
    page_params.is_admin = false;
    assert(!compose.wildcard_mention_allowed());

    page_params.is_guest = false;
    assert(compose.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_stream_admins_only.code;
    page_params.is_admin = false;
    assert(!compose.wildcard_mention_allowed());

    // TODO: Add a by_admins_only case when we implement stream-level administrators.

    page_params.is_admin = true;
    assert(compose.wildcard_mention_allowed());

    page_params.realm_wildcard_mention_policy =
        settings_config.wildcard_mention_policy_values.by_full_members.code;
    const person = people.get_by_user_id(page_params.user_id);
    person.date_joined = new Date(Date.now());
    page_params.realm_waiting_period_threshold = 10;

    assert(compose.wildcard_mention_allowed());
    page_params.is_admin = false;
    assert(!compose.wildcard_mention_allowed());
});

run_test("validate_stream_message", () => {
    // This test is in kind of continuation to test_validate but since it is
    // primarily used to get coverage over functions called from validate()
    // we are separating it up in different test. Though their relative position
    // of execution should not be changed.
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

    peer_data.get_subscriber_count = function (stream_id) {
        assert.equal(stream_id, 101);
        return 16;
    };
    stub_templates((template_name, data) => {
        assert.equal(template_name, "compose_all_everyone");
        assert.equal(data.count, 16);
        return "compose_all_everyone_stub";
    });
    let compose_content;
    $("#compose-all-everyone").append = function (data) {
        compose_content = data;
    };

    compose.wildcard_mention_allowed = function () {
        return true;
    };
    compose_state.message_content("Hey @**all**");
    assert(!compose.validate());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert(!$("#compose-send-status").visible());
    assert.equal(compose_content, "compose_all_everyone_stub");
    assert($("#compose-all-everyone").visible());

    compose.wildcard_mention_allowed = function () {
        return false;
    };
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        i18n.t("You do not have permission to use wildcard mentions in this stream."),
    );
});

run_test("test_validate_stream_message_post_policy_admin_only", () => {
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
    assert(!compose.validate());
    assert.equal(
        $("#compose-error-msg").html(),
        i18n.t("Only organization admins are allowed to post to this stream."),
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
        i18n.t("Only organization admins are allowed to post to this stream."),
    );
});

run_test("test_validate_stream_message_post_policy_full_members_only", () => {
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
        i18n.t("Guests are not allowed to post to this stream."),
    );

    // reset compose_state.stream_name to 'social' again so that any tests occurring after this
    // do not reproduce this error.
    compose_state.stream_name("social");
    // Reset page_params
    page_params.is_guest = false;
});

run_test("markdown_rtl", () => {
    const textarea = $("#compose-textarea");

    const event = {
        keyCode: 65, // A
    };

    rtl.get_direction = (text) => {
        assert.equal(text, " foo");
        return "rtl";
    };

    assert.equal(textarea.hasClass("rtl"), false);

    textarea.val("```quote foo");
    compose.handle_keyup(event, $("#compose-textarea"));

    assert.equal(textarea.hasClass("rtl"), true);
});

// This is important for subsequent tests--put
// us back to the "normal" ltr case.
rtl.get_direction = () => "ltr";

run_test("markdown_ltr", () => {
    const textarea = $("#compose-textarea");

    const event = {
        keyCode: 65, // A
    };

    assert.equal(textarea.hasClass("rtl"), true);
    textarea.val("```quote foo");
    compose.handle_keyup(event, textarea);

    assert.equal(textarea.hasClass("rtl"), false);
});

run_test("markdown_shortcuts", () => {
    let queryCommandEnabled = true;
    const event = {
        keyCode: 66,
        target: {
            id: "compose-textarea",
        },
        stopPropagation: noop,
        preventDefault: noop,
    };
    let input_text = "";
    let range_start = 0;
    let range_length = 0;
    let compose_value = $("#compose_textarea").val();
    let selected_word = "";

    document.queryCommandEnabled = function () {
        return queryCommandEnabled;
    };
    document.execCommand = function (cmd, bool, markdown) {
        const compose_textarea = $("#compose-textarea");
        const value = compose_textarea.val();
        $("#compose-textarea").val(
            value.slice(0, compose_textarea.range().start) +
                markdown +
                value.slice(compose_textarea.range().end),
        );
    };

    $("#compose-textarea")[0] = {};
    $("#compose-textarea").range = function () {
        return {
            start: range_start,
            end: range_start + range_length,
            length: range_length,
            range: noop,
            text: $("#compose-textarea")
                .val()
                .slice(range_start, range_length + range_start),
        };
    };
    $("#compose-textarea").caret = noop;

    function test_i_typed(isCtrl, isCmd) {
        // Test 'i' is typed correctly.
        $("#compose-textarea").val("i");
        event.keyCode = undefined;
        event.which = 73;
        event.metaKey = isCmd;
        event.ctrlKey = isCtrl;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("i", $("#compose-textarea").val());
    }

    function all_markdown_test(isCtrl, isCmd) {
        input_text = "Any text.";
        $("#compose-textarea").val(input_text);
        compose_value = $("#compose-textarea").val();
        // Select "text" word in compose box.
        selected_word = "text";
        range_start = compose_value.search(selected_word);
        range_length = selected_word.length;

        // Test bold:
        // Mac env = Cmd+b
        // Windows/Linux = Ctrl+b
        event.keyCode = 66;
        event.ctrlKey = isCtrl;
        event.metaKey = isCmd;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("Any **text**.", $("#compose-textarea").val());
        // Test if no text is selected.
        range_start = 0;
        // Change cursor to first position.
        range_length = 0;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("****Any **text**.", $("#compose-textarea").val());

        // Test italic:
        // Mac = Cmd+I
        // Windows/Linux = Ctrl+I
        $("#compose-textarea").val(input_text);
        range_start = compose_value.search(selected_word);
        range_length = selected_word.length;
        event.keyCode = 73;
        event.shiftKey = false;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("Any *text*.", $("#compose-textarea").val());
        // Test if no text is selected.
        range_length = 0;
        // Change cursor to first position.
        range_start = 0;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("**Any *text*.", $("#compose-textarea").val());

        // Test link insertion:
        // Mac = Cmd+Shift+L
        // Windows/Linux = Ctrl+Shift+L
        $("#compose-textarea").val(input_text);
        range_start = compose_value.search(selected_word);
        range_length = selected_word.length;
        event.keyCode = 76;
        event.which = undefined;
        event.shiftKey = true;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal("Any [text](url).", $("#compose-textarea").val());
        // Test if exec command is not enabled in browser.
        queryCommandEnabled = false;
        compose.handle_keydown(event, $("#compose-textarea"));
    }

    // This function cross tests the Cmd/Ctrl + Markdown shortcuts in
    // Mac and Linux/Windows environments.  So in short, this tests
    // that e.g. Cmd+B should be ignored on Linux/Windows and Ctrl+B
    // should be ignored on Mac.
    function os_specific_markdown_test(isCtrl, isCmd) {
        input_text = "Any text.";
        $("#compose-textarea").val(input_text);
        compose_value = $("#compose-textarea").val();
        selected_word = "text";
        range_start = compose_value.search(selected_word);
        range_length = selected_word.length;
        event.metaKey = isCmd;
        event.ctrlKey = isCtrl;

        event.keyCode = 66;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal(input_text, $("#compose-textarea").val());

        event.keyCode = 73;
        event.shiftKey = false;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal(input_text, $("#compose-textarea").val());

        event.keyCode = 76;
        event.shiftKey = true;
        compose.handle_keydown(event, $("#compose-textarea"));
        assert.equal(input_text, $("#compose-textarea").val());
    }

    // These keyboard shortcuts differ as to what key one should use
    // on MacOS vs. other platforms: Cmd (Mac) vs. Ctrl (non-Mac).

    // Default (Linux/Windows) userAgent tests:
    test_i_typed(false, false);
    // Check all the Ctrl + Markdown shortcuts work correctly
    all_markdown_test(true, false);
    // The Cmd + Markdown shortcuts should do nothing on Linux/Windows
    os_specific_markdown_test(false, true);

    // Setting following platform to test in mac env
    _navigator.platform = "MacIntel";

    // Mac userAgent tests:
    test_i_typed(false, false);
    // The Ctrl + Markdown shortcuts should do nothing on mac
    os_specific_markdown_test(true, false);
    // Check all the Cmd + Markdown shortcuts work correctly
    all_markdown_test(false, true);

    // Reset userAgent
    _navigator.userAgent = "";
});

run_test("send_message_success", () => {
    $("#compose-textarea").val("foobarfoobar");
    $("#compose-textarea").trigger("blur");
    $("#compose-send-status").show();
    $("#compose-send-button").prop("disabled", true);
    $("#sending-indicator").show();

    let reify_message_id_checked;
    echo.reify_message_id = function (local_id, message_id) {
        assert.equal(local_id, "1001");
        assert.equal(message_id, 12);
        reify_message_id_checked = true;
    };

    compose.send_message_success("1001", 12, false);

    assert.equal($("#compose-textarea").val(), "");
    assert($("#compose-textarea").is_focused());
    assert(!$("#compose-send-status").visible());
    assert.equal($("#compose-send-button").prop("disabled"), false);
    assert(!$("#sending-indicator").visible());

    assert(reify_message_id_checked);
});

run_test("send_message", () => {
    // This is the common setup stuff for all of the four tests.
    let stub_state;
    function initialize_state_stub_dict() {
        stub_state = {};
        stub_state.send_msg_called = 0;
        stub_state.get_events_running_called = 0;
        stub_state.reify_message_id_checked = 0;
        return stub_state;
    }

    set_global("setTimeout", (func) => {
        func();
    });
    set_global("server_events", {
        assert_get_events_running() {
            stub_state.get_events_running_called += 1;
        },
    });

    // Tests start here.
    (function test_message_send_success_codepath() {
        stub_state = initialize_state_stub_dict();
        compose_state.topic("");
        compose_state.set_message_type("private");
        page_params.user_id = 101;
        compose_state.private_message_recipient = function () {
            return "alice@example.com";
        };

        const server_message_id = 127;
        local_message.insert_message = (message) => {
            assert.equal(message.timestamp, fake_now);
        };

        markdown.apply_markdown = () => {};
        markdown.add_topic_links = () => {};

        echo.try_deliver_locally = function (message_request) {
            const local_id_float = 123.04;
            return echo.insert_local_message(message_request, local_id_float);
        };
        transmit.send_message = function (payload, success) {
            const single_msg = {
                type: "private",
                content: "[foobar](/user_uploads/123456)",
                sender_id: 101,
                queue_id: undefined,
                stream: "",
                topic: "",
                to: `[${alice.user_id}]`,
                reply_to: "alice@example.com",
                private_message_recipient: "alice@example.com",
                to_user_ids: "31",
                local_id: "123.04",
                locally_echoed: true,
            };

            assert.deepEqual(payload, single_msg);
            payload.id = server_message_id;
            success(payload);
            stub_state.send_msg_called += 1;
        };
        echo.reify_message_id = function (local_id, message_id) {
            assert.equal(typeof local_id, "string");
            assert.equal(typeof message_id, "number");
            assert.equal(message_id, server_message_id);
            stub_state.reify_message_id_checked += 1;
        };

        // Setting message content with a host server link and we will assert
        // later that this has been converted to a relative link.
        $("#compose-textarea").val("[foobar](https://foo.com/user_uploads/123456)");
        $("#compose-textarea").trigger("blur");
        $("#compose-send-status").show();
        $("#compose-send-button").prop("disabled", true);
        $("#sending-indicator").show();

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 1,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert.equal($("#compose-textarea").val(), "");
        assert($("#compose-textarea").is_focused());
        assert(!$("#compose-send-status").visible());
        assert.equal($("#compose-send-button").prop("disabled"), false);
        assert(!$("#sending-indicator").visible());
    })();

    // This is the additional setup which is common to both the tests below.
    transmit.send_message = function (payload, success, error) {
        stub_state.send_msg_called += 1;
        error("Error sending message: Server says 408");
    };

    let echo_error_msg_checked;

    echo.message_send_error = function (local_id, error_response) {
        assert.equal(local_id, 123.04);
        assert.equal(error_response, "Error sending message: Server says 408");
        echo_error_msg_checked = true;
    };

    // Tests start here.
    (function test_param_error_function_passed_from_send_message() {
        stub_state = initialize_state_stub_dict();

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 0,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert(echo_error_msg_checked);
    })();

    (function test_error_codepath_local_id_undefined() {
        stub_state = initialize_state_stub_dict();
        $("#compose-textarea").val("foobarfoobar");
        $("#compose-textarea").trigger("blur");
        $("#compose-send-status").show();
        $("#compose-send-button").prop("disabled", true);
        $("#sending-indicator").show();
        $("#compose-textarea").off("select");
        echo_error_msg_checked = false;
        echo.try_deliver_locally = function () {
            return;
        };

        sent_messages.get_new_local_id = function () {
            return "loc-55";
        };

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 0,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert(!echo_error_msg_checked);
        assert.equal($("#compose-send-button").prop("disabled"), false);
        assert.equal($("#compose-error-msg").html(), "Error sending message: Server says 408");
        assert.equal($("#compose-textarea").val(), "foobarfoobar");
        assert($("#compose-textarea").is_focused());
        assert($("#compose-send-status").visible());
        assert.equal($("#compose-send-button").prop("disabled"), false);
        assert(!$("#sending-indicator").visible());
    })();
});

set_global("document", "document-stub");

run_test("enter_with_preview_open", () => {
    // Test sending a message with content.
    compose_state.set_message_type("stream");
    $("#compose-textarea").val("message me");
    $("#compose-textarea").hide();
    $("#undo_markdown_preview").show();
    $("#preview_message_area").show();
    $("#markdown_preview").hide();
    page_params.enter_sends = true;
    let send_message_called = false;
    compose.send_message = function () {
        send_message_called = true;
    };
    compose.enter_with_preview_open();
    assert($("#compose-textarea").visible());
    assert(!$("#undo_markdown_preview").visible());
    assert(!$("#preview_message_area").visible());
    assert($("#markdown_preview").visible());
    assert(send_message_called);

    page_params.enter_sends = false;
    $("#compose-textarea").trigger("blur");
    compose.enter_with_preview_open();
    assert($("#compose-textarea").is_focused());

    // Test sending a message without content.
    $("#compose-textarea").val("");
    $("#preview_message_area").show();
    $("#enter_sends").prop("checked", true);
    page_params.enter_sends = true;

    compose.enter_with_preview_open();

    assert($("#enter_sends").prop("checked"));
    assert.equal($("#compose-error-msg").html(), i18n.t("You have nothing to send!"));
});

run_test("finish", () => {
    (function test_when_compose_validation_fails() {
        $("#compose_invite_users").show();
        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $("#sending-indicator").hide();
        $("#compose-textarea").off("select");
        $("#compose-textarea").val("");
        const res = compose.finish();
        assert.equal(res, false);
        assert(!$("#compose_invite_users").visible());
        assert(!$("#sending-indicator").visible());
        assert(!$("#compose-send-button").is_focused());
        assert.equal($("#compose-send-button").prop("disabled"), false);
        assert.equal($("#compose-error-msg").html(), i18n.t("You have nothing to send!"));
    })();

    (function test_when_compose_validation_succeed() {
        $("#compose-textarea").hide();
        $("#undo_markdown_preview").show();
        $("#preview_message_area").show();
        $("#markdown_preview").hide();
        $("#compose-textarea").val("foobarfoobar");
        compose_state.set_message_type("private");
        compose_state.private_message_recipient = function () {
            return "bob@example.com";
        };

        let compose_finished_event_checked = false;
        $(document).on("compose_finished.zulip", () => {
            compose_finished_event_checked = true;
        });
        let send_message_called = false;
        compose.send_message = function () {
            send_message_called = true;
        };
        assert(compose.finish());
        assert($("#compose-textarea").visible());
        assert(!$("#undo_markdown_preview").visible());
        assert(!$("#preview_message_area").visible());
        assert($("#markdown_preview").visible());
        assert(send_message_called);
        assert(compose_finished_event_checked);
    })();
});

run_test("warn_if_private_stream_is_linked", () => {
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
        compose.warn_if_private_stream_is_linked(denmark);
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
            stub_templates((template_name, context) => {
                called = true;
                assert.equal(template_name, "compose_private_stream_alert");
                assert.equal(context.stream_name, "Denmark");
                return "fake-compose_private_stream_alert-template";
            });
            return function () {
                assert(called);
            };
        })(),

        (function () {
            let called;
            $("#compose_private_stream_alert").append = function (html) {
                called = true;
                assert.equal(html, "fake-compose_private_stream_alert-template");
            };
            return function () {
                assert(called);
            };
        })(),
    ];

    denmark = {
        invite_only: true,
        name: "Denmark",
        stream_id: 22,
    };
    stream_data.add_sub(denmark);

    compose.warn_if_private_stream_is_linked(denmark);
    assert.equal($("#compose_private_stream_alert").visible(), true);

    for (const f of checks) {
        f();
    }
});

run_test("initialize", () => {
    // In this test we mostly do the setup stuff in addition to testing the
    // normal workflow of the function. All the tests for the on functions are
    // done in subsequent tests directly below this test.

    let resize_watch_manual_resize_checked = false;
    resize.watch_manual_resize = function (elem) {
        assert.equal("#compose-textarea", elem);
        resize_watch_manual_resize_checked = true;
    };
    set_global("bridge", true);
    let xmlhttprequest_checked = false;
    set_global("XMLHttpRequest", function () {
        this.upload = true;
        xmlhttprequest_checked = true;
    });
    $("#compose #attach_files").addClass("notdisplayed");

    set_global("document", "document-stub");
    set_global("csrf_token", "fake-csrf-token");

    page_params.max_file_upload_size_mib = 512;

    let setup_upload_called = false;
    let uppy_cancel_all_called = false;
    upload.setup_upload = function (config) {
        assert.equal(config.mode, "compose");
        setup_upload_called = true;
        return {
            cancelAll: () => {
                uppy_cancel_all_called = true;
            },
        };
    };

    page_params.realm_available_video_chat_providers = {
        disabled: {
            id: 0,
            name: "disabled",
        },
        jitsi_meet: {
            id: 1,
            name: "Jitsi Meet",
        },
        zoom: {
            id: 3,
            name: "Zoom",
        },
        big_blue_button: {
            id: 4,
            name: "Big Blue Button",
        },
    };

    page_params.realm_video_chat_provider =
        page_params.realm_available_video_chat_providers.disabled.id;

    stub_out_video_calls();
    compose.initialize();

    assert(resize_watch_manual_resize_checked);
    assert(xmlhttprequest_checked);
    assert(!$("#compose #attach_files").hasClass("notdisplayed"));
    assert(setup_upload_called);

    let compose_actions_start_checked;

    function set_up_compose_start_mock(expected_opts) {
        compose_actions_start_checked = false;

        set_global("compose_actions", {
            start(msg_type, opts) {
                assert.equal(msg_type, "stream");
                assert.deepEqual(opts, expected_opts);
                compose_actions_start_checked = true;
            },
        });
    }

    (function test_page_params_narrow_path() {
        page_params.narrow = true;

        reset_jquery();
        stub_out_video_calls();
        set_up_compose_start_mock({});

        compose.initialize();

        assert(compose_actions_start_checked);
    })();

    (function test_page_params_narrow_topic() {
        page_params.narrow_topic = "testing";

        reset_jquery();
        stub_out_video_calls();
        set_up_compose_start_mock({topic: "testing"});

        compose.initialize();

        assert(compose_actions_start_checked);
    })();

    (function test_abort_xhr() {
        $("#compose-send-button").prop("disabled", true);

        reset_jquery();
        stub_out_video_calls();
        compose.initialize();

        compose.abort_xhr();

        assert.equal($("#compose-send-button").attr(), undefined);
        assert(uppy_cancel_all_called);
    })();
});

run_test("update_fade", () => {
    const selector =
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient";
    const keyup_handler_func = $(selector).get_on_handler("keyup");

    let set_focused_recipient_checked = false;
    let update_all_called = false;

    set_global("compose_fade", {
        set_focused_recipient(msg_type) {
            assert.equal(msg_type, "private");
            set_focused_recipient_checked = true;
        },
        update_all() {
            update_all_called = true;
        },
    });

    compose_state.set_message_type(false);
    keyup_handler_func();
    assert(!set_focused_recipient_checked);
    assert(!update_all_called);

    compose_state.set_message_type("private");
    keyup_handler_func();
    assert(set_focused_recipient_checked);
    assert(update_all_called);
});

run_test("trigger_submit_compose_form", () => {
    let prevent_default_checked = false;
    let compose_finish_checked = false;
    const e = {
        preventDefault() {
            prevent_default_checked = true;
        },
    };
    compose.finish = function () {
        compose_finish_checked = true;
    };

    const submit_handler = $("#compose form").get_on_handler("submit");

    submit_handler(e);

    assert(prevent_default_checked);
    assert(compose_finish_checked);
});

run_test("needs_subscribe_warning", () => {
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
        can_access_subscribers: true,
    };

    stream_data.add_sub(sub);
    peer_data.set_subscribers(sub.stream_id, [bob.user_id, me.user_id]);

    blueslip.expect("error", "Unknown user_id in get_by_user_id: 999");
    // Test with an invalid user id.
    assert.equal(compose.needs_subscribe_warning(invalid_user_id, sub.stream_id), false);

    // Test with bot user.
    assert.equal(compose.needs_subscribe_warning(test_bot.user_id, sub.stream_id), false);

    // Test when user is subscribed to the stream.
    assert.equal(compose.needs_subscribe_warning(bob.user_id, sub.stream_id), false);

    peer_data.remove_subscriber(sub.stream_id, bob.user_id);
    // Test when the user is not subscribed.
    assert.equal(compose.needs_subscribe_warning(bob.user_id, sub.stream_id), true);
});

run_test("warn_if_mentioning_unsubscribed_user", () => {
    let mentioned = {
        email: "foo@bar.com",
    };

    $("#compose_invite_users .compose_invite_user").length = 0;

    function test_noop_case(is_private, is_zephyr_mirror, is_broadcast) {
        const msg_type = is_private ? "private" : "stream";
        compose_state.set_message_type(msg_type);
        page_params.realm_is_zephyr_mirror_realm = is_zephyr_mirror;
        mentioned.is_broadcast = is_broadcast;
        compose.warn_if_mentioning_unsubscribed_user(mentioned);
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
    compose.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), false);

    compose_state.stream_name("random");
    const sub = {
        stream_id: 111,
        name: "random",
    };

    // Test with invalid stream in compose box. It should return noop.
    compose.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), false);

    // Test mentioning a user that should gets a warning.

    const checks = [
        (function () {
            let called;
            compose.needs_subscribe_warning = function (user_id, stream_id) {
                called = true;
                assert.equal(user_id, 34);
                assert.equal(stream_id, 111);
                return true;
            };
            return function () {
                assert(called);
            };
        })(),

        (function () {
            let called;
            stub_templates((template_name, context) => {
                called = true;
                assert.equal(template_name, "compose_invite_users");
                assert.equal(context.user_id, 34);
                assert.equal(context.stream_id, 111);
                assert.equal(context.name, "Foo Barson");
                return "fake-compose-invite-user-template";
            });
            return function () {
                assert(called);
            };
        })(),

        (function () {
            let called;
            $("#compose_invite_users").append = function (html) {
                called = true;
                assert.equal(html, "fake-compose-invite-user-template");
            };
            return function () {
                assert(called);
            };
        })(),
    ];

    mentioned = {
        email: "foo@bar.com",
        user_id: 34,
        full_name: "Foo Barson",
    };

    stream_data.add_sub(sub);
    compose.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), true);

    for (const f of checks) {
        f();
    }

    // Simulate that the row was added to the DOM.
    const warning_row = $("<warning row>");

    let looked_for_existing;
    warning_row.data = function (field) {
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
    stub_templates(noop);
    compose.warn_if_mentioning_unsubscribed_user(mentioned);
    assert.equal($("#compose_invite_users").visible(), true);
    assert(looked_for_existing);
});

run_test("on_events", () => {
    function setup_parents_and_mock_remove(container_sel, target_sel, parent) {
        const container = $.create("fake " + container_sel);
        let container_removed = false;

        container.remove = function () {
            container_removed = true;
        };

        const target = $.create("fake click target (" + target_sel + ")");

        target.set_parents_result(parent, container);

        const event = {
            preventDefault: noop,
            target,
        };

        const helper = {
            event,
            container,
            target,
            container_was_removed: () => container_removed,
        };

        return helper;
    }

    (function test_compose_all_everyone_confirm_clicked() {
        const handler = $("#compose-all-everyone").get_on_handler(
            "click",
            ".compose-all-everyone-confirm",
        );

        const helper = setup_parents_and_mock_remove(
            "compose-all-everyone",
            "compose-all-everyone",
            ".compose-all-everyone",
        );

        $("#compose-all-everyone").show();
        $("#compose-send-status").show();

        let compose_finish_checked = false;
        compose.finish = function () {
            compose_finish_checked = true;
        };

        handler(helper.event);

        assert(helper.container_was_removed());
        assert(compose_finish_checked);
        assert(!$("#compose-all-everyone").visible());
        assert(!$("#compose-send-status").visible());
    })();

    (function test_compose_invite_users_clicked() {
        const handler = $("#compose_invite_users").get_on_handler("click", ".compose_invite_link");
        const subscription = {
            stream_id: 102,
            name: "test",
            subscribed: true,
        };
        const mentioned = {
            full_name: "Foo Barson",
            email: "foo@bar.com",
            user_id: 34,
        };
        people.add_active_user(mentioned);
        let invite_user_to_stream_called = false;
        stream_edit.invite_user_to_stream = function (user_ids, sub, success) {
            invite_user_to_stream_called = true;
            assert.deepEqual(user_ids, [mentioned.user_id]);
            assert.equal(sub, subscription);
            success(); // This will check success callback path.
        };

        const helper = setup_parents_and_mock_remove(
            "compose_invite_users",
            "compose_invite_link",
            ".compose_invite_user",
        );

        helper.container.data = function (field) {
            if (field === "user-id") {
                return "34";
            }
            if (field === "stream-id") {
                return "102";
            }
            throw new Error(`Unknown field ${field}`);
        };
        helper.target.prop("disabled", false);

        // !sub will result in true here and we check the success code path.
        stream_data.add_sub(subscription);
        $("#stream_message_recipient_stream").val("test");
        let all_invite_children_called = false;
        $("#compose_invite_users").children = function () {
            all_invite_children_called = true;
            return [];
        };
        $("#compose_invite_users").show();

        handler(helper.event);

        assert(helper.container_was_removed());
        assert(!$("#compose_invite_users").visible());
        assert(invite_user_to_stream_called);
        assert(all_invite_children_called);
    })();

    (function test_compose_invite_close_clicked() {
        const handler = $("#compose_invite_users").get_on_handler("click", ".compose_invite_close");

        const helper = setup_parents_and_mock_remove(
            "compose_invite_users_close",
            "compose_invite_close",
            ".compose_invite_user",
        );

        let all_invite_children_called = false;
        $("#compose_invite_users").children = function () {
            all_invite_children_called = true;
            return [];
        };
        $("#compose_invite_users").show();

        handler(helper.event);

        assert(helper.container_was_removed());
        assert(all_invite_children_called);
        assert(!$("#compose_invite_users").visible());
    })();

    (function test_compose_not_subscribed_clicked() {
        const handler = $("#compose-send-status").get_on_handler("click", ".sub_unsub_button");
        const subscription = {
            stream_id: 102,
            name: "test",
            subscribed: false,
        };
        let compose_not_subscribed_called = false;
        subs.sub_or_unsub = function () {
            compose_not_subscribed_called = true;
        };

        const helper = setup_parents_and_mock_remove(
            "compose-send-status",
            "sub_unsub_button",
            ".compose_not_subscribed",
        );

        handler(helper.event);

        assert(compose_not_subscribed_called);

        stream_data.add_sub(subscription);
        $("#stream_message_recipient_stream").val("test");
        $("#compose-send-status").show();

        handler(helper.event);

        assert(!$("#compose-send-status").visible());
    })();

    (function test_compose_not_subscribed_close_clicked() {
        const handler = $("#compose-send-status").get_on_handler(
            "click",
            "#compose_not_subscribed_close",
        );

        const helper = setup_parents_and_mock_remove(
            "compose_user_not_subscribed_close",
            "compose_not_subscribed_close",
            ".compose_not_subscribed",
        );

        $("#compose-send-status").show();

        handler(helper.event);

        assert(!$("#compose-send-status").visible());
    })();

    (function test_attach_files_compose_clicked() {
        const handler = $("#compose").get_on_handler("click", "#attach_files");
        $("#file_input").clone = function (param) {
            assert(param);
        };
        let compose_file_input_clicked = false;
        $("#compose #file_input").on("click", () => {
            compose_file_input_clicked = true;
        });

        const event = {
            preventDefault: noop,
        };

        handler(event);
        assert(compose_file_input_clicked);
    })();

    (function test_no_provider_video_link_compose_clicked() {
        let called = false;

        const textarea = $.create("target-stub");

        const ev = {
            preventDefault: noop,
            target: {
                to_$: () => textarea,
            },
        };

        compose_ui.insert_syntax_and_focus = function () {
            called = true;
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        handler(ev);
        assert(!called);
    })();

    (function test_jitsi_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("jitsi-target-stub");

        const ev = {
            preventDefault: noop,
            target: {
                to_$: () => textarea,
            },
        };

        compose_ui.insert_syntax_and_focus = function (syntax) {
            syntax_to_insert = syntax;
            called = true;
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider =
            page_params.realm_available_video_chat_providers.jitsi_meet.id;

        page_params.jitsi_server_url = null;
        handler(ev);
        assert(!called);

        page_params.jitsi_server_url = "https://meet.jit.si";
        handler(ev);
        // video link ids consist of 15 random digits
        const video_link_regex = /\[translated: Click to join video call]\(https:\/\/meet.jit.si\/\d{15}\)/;
        assert(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_zoom_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("zoom-target-stub");

        const ev = {
            preventDefault: noop,
            target: {
                to_$: () => textarea,
            },
        };

        compose_ui.insert_syntax_and_focus = function (syntax) {
            syntax_to_insert = syntax;
            called = true;
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider =
            page_params.realm_available_video_chat_providers.zoom.id;
        page_params.has_zoom_token = false;

        window.open = function (url) {
            assert(url.endsWith("/calls/zoom/register"));

            // The event here has value=true.  We keep it in events.js to
            // allow our tooling to verify its schema.
            server_events_dispatch.dispatch_normal_event(events.fixtures.has_zoom_token);
        };

        channel.post = function (payload) {
            assert.equal(payload.url, "/json/calls/zoom/create");
            payload.success({url: "example.zoom.com"});
            return {abort: () => {}};
        };

        handler(ev);
        const video_link_regex = /\[translated: Click to join video call]\(example\.zoom\.com\)/;
        assert(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_bbb_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("bbb-target-stub");

        const ev = {
            preventDefault: noop,
            target: {
                to_$: () => textarea,
            },
        };

        compose_ui.insert_syntax_and_focus = function (syntax) {
            syntax_to_insert = syntax;
            called = true;
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider =
            page_params.realm_available_video_chat_providers.big_blue_button.id;

        channel.get = function (options) {
            assert(options.url === "/json/calls/bigbluebutton/create");
            options.success({
                url:
                    "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22",
            });
        };

        handler(ev);
        const video_link_regex = /\[translated: Click to join video call]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_markdown_preview_compose_clicked() {
        // Tests setup
        function setup_visibilities() {
            $("#compose-textarea").show();
            $("#markdown_preview").show();
            $("#undo_markdown_preview").hide();
            $("#preview_message_area").hide();
        }

        function assert_visibilities() {
            assert(!$("#compose-textarea").visible());
            assert(!$("#markdown_preview").visible());
            assert($("#undo_markdown_preview").visible());
            assert($("#preview_message_area").visible());
        }

        function setup_mock_markdown_contains_backend_only_syntax(msg_content, return_val) {
            markdown.contains_backend_only_syntax = function (msg) {
                assert.equal(msg, msg_content);
                return return_val;
            };
        }

        function setup_mock_markdown_is_status_message(msg_content, return_val) {
            markdown.is_status_message = function (content) {
                assert.equal(content, msg_content);
                return return_val;
            };
        }

        function test_post_success(success_callback) {
            const resp = {
                rendered: "Server: foobarfoobar",
            };
            success_callback(resp);
            assert.equal($("#preview_content").html(), "Server: foobarfoobar");
        }

        function test_post_error(error_callback) {
            error_callback();
            assert.equal($("#preview_content").html(), "translated: Failed to generate preview");
        }

        function mock_channel_post(msg) {
            channel.post = function (payload) {
                assert.equal(payload.url, "/json/messages/render");
                assert(payload.idempotent);
                assert(payload.data);
                assert.deepEqual(payload.data.content, msg);

                function test(func, param) {
                    let destroy_indicator_called = false;
                    loading.destroy_indicator = function (spinner) {
                        assert.equal(spinner, $("#markdown_preview_spinner"));
                        destroy_indicator_called = true;
                    };
                    setup_mock_markdown_contains_backend_only_syntax(msg, true);

                    func(param);

                    assert(destroy_indicator_called);
                }

                test(test_post_error, payload.error);
                test(test_post_success, payload.success);
            };
        }

        const handler = $("#compose").get_on_handler("click", "#markdown_preview");

        // Tests start here
        $("#compose-textarea").val("");
        setup_visibilities();

        const event = {
            preventDefault: noop,
        };

        handler(event);

        assert.equal($("#preview_content").html(), "translated: Nothing to preview");
        assert_visibilities();

        let make_indicator_called = false;
        $("#compose-textarea").val("```foobarfoobar```");
        setup_visibilities();
        setup_mock_markdown_contains_backend_only_syntax("```foobarfoobar```", true);
        setup_mock_markdown_is_status_message("```foobarfoobar```", false);
        loading.make_indicator = function (spinner) {
            assert.equal(spinner.selector, "#markdown_preview_spinner");
            make_indicator_called = true;
        };
        mock_channel_post("```foobarfoobar```");

        handler(event);

        assert(make_indicator_called);
        assert_visibilities();

        let apply_markdown_called = false;
        $("#compose-textarea").val("foobarfoobar");
        setup_visibilities();
        setup_mock_markdown_contains_backend_only_syntax("foobarfoobar", false);
        setup_mock_markdown_is_status_message("foobarfoobar", false);
        mock_channel_post("foobarfoobar");
        markdown.apply_markdown = function (msg) {
            assert.equal(msg.raw_content, "foobarfoobar");
            apply_markdown_called = true;
            return msg;
        };

        handler(event);

        assert(apply_markdown_called);
        assert_visibilities();
        assert.equal($("#preview_content").html(), "Server: foobarfoobar");
    })();

    (function test_undo_markdown_preview_clicked() {
        const handler = $("#compose").get_on_handler("click", "#undo_markdown_preview");

        $("#compose-textarea").hide();
        $("#undo_markdown_preview").show();
        $("#preview_message_area").show();
        $("#markdown_preview").hide();

        const event = {
            preventDefault: noop,
        };

        handler(event);

        assert($("#compose-textarea").visible());
        assert(!$("#undo_markdown_preview").visible());
        assert(!$("#preview_message_area").visible());
        assert($("#markdown_preview").visible());
    })();
});

run_test("create_message_object", () => {
    const sub = {
        stream_id: 101,
        name: "social",
        subscribed: true,
    };
    stream_data.add_sub(sub);

    const page = {
        "#stream_message_recipient_stream": "social",
        "#stream_message_recipient_topic": "lunch",
        "#compose-textarea": "burrito",
    };

    set_global("$", (selector) => ({
        val() {
            return page[selector];
        },
    }));

    compose_state.get_message_type = function () {
        return "stream";
    };

    let message = compose.create_message_object();
    assert.equal(message.to, sub.stream_id);
    assert.equal(message.topic, "lunch");
    assert.equal(message.content, "burrito");

    blueslip.expect("error", "Trying to send message with bad stream name: BOGUS STREAM");

    page["#stream_message_recipient_stream"] = "BOGUS STREAM";
    message = compose.create_message_object();
    assert.equal(message.to, "BOGUS STREAM");
    assert.equal(message.topic, "lunch");
    assert.equal(message.content, "burrito");

    compose_state.get_message_type = function () {
        return "private";
    };
    compose_state.private_message_recipient = function () {
        return "alice@example.com, bob@example.com";
    };

    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.user_id, bob.user_id]);
    assert.equal(message.to_user_ids, "31,32");
    assert.equal(message.content, "burrito");

    const {email_list_to_user_ids_string} = people;
    people.email_list_to_user_ids_string = () => undefined;
    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.email, bob.email]);
    people.email_list_to_user_ids_string = email_list_to_user_ids_string;
});

run_test("nonexistent_stream_reply_error", () => {
    set_global("$", make_zjquery());

    const actions = [];
    $("#nonexistent_stream_reply_error").show = () => {
        actions.push("show");
    };
    $("#nonexistent_stream_reply_error").hide = () => {
        actions.push("hide");
    };

    compose.nonexistent_stream_reply_error();
    assert.equal($("#compose-reply-error-msg").html(), "There are no messages to reply to yet.");
    assert.deepEqual(actions, ["show", "hide"]);
});

run_test("narrow_button_titles", () => {
    util.is_mobile = () => false;

    compose.update_closed_compose_buttons_for_private();
    assert.equal($("#left_bar_compose_stream_button_big").text(), i18n.t("New stream message"));
    assert.equal($("#left_bar_compose_private_button_big").text(), i18n.t("New private message"));

    compose.update_closed_compose_buttons_for_stream();
    assert.equal($("#left_bar_compose_stream_button_big").text(), i18n.t("New topic"));
    assert.equal($("#left_bar_compose_private_button_big").text(), i18n.t("New private message"));
});

run_test("test_video_chat_button_toggle", () => {
    reset_jquery();
    stub_out_video_calls();

    page_params.realm_video_chat_provider =
        page_params.realm_available_video_chat_providers.disabled.id;
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), false);

    reset_jquery();
    stub_out_video_calls();
    page_params.realm_video_chat_provider =
        page_params.realm_available_video_chat_providers.jitsi_meet.id;
    page_params.jitsi_server_url = null;
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), false);

    reset_jquery();
    stub_out_video_calls();
    page_params.realm_video_chat_provider =
        page_params.realm_available_video_chat_providers.jitsi_meet.id;
    page_params.jitsi_server_url = "https://meet.jit.si";
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), true);
});

MockDate.reset();
