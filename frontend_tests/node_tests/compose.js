"use strict";

const {strict: assert} = require("assert");

const MockDate = require("mockdate");

const {$t, $t_html} = require("../zjsunit/i18n");
const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");
const {page_params, user_settings} = require("../zjsunit/zpage_params");

const noop = () => {};

set_global("document", {
    querySelector: () => {},
});
set_global("navigator", {});
// eslint-disable-next-line prefer-arrow-callback
set_global("ResizeObserver", function () {
    return {
        observe: () => {},
    };
});

const fake_now = 555;

const channel = mock_esm("../../static/js/channel");
const compose_actions = mock_esm("../../static/js/compose_actions");
const loading = mock_esm("../../static/js/loading");
const markdown = mock_esm("../../static/js/markdown");
const notifications = mock_esm("../../static/js/notifications");
const reminder = mock_esm("../../static/js/reminder");
const rendered_markdown = mock_esm("../../static/js/rendered_markdown");
const resize = mock_esm("../../static/js/resize");
const sent_messages = mock_esm("../../static/js/sent_messages");
const server_events = mock_esm("../../static/js/server_events");
const stream_settings_ui = mock_esm("../../static/js/stream_settings_ui");
const stream_subscribers_ui = mock_esm("../../static/js/stream_subscribers_ui");
const transmit = mock_esm("../../static/js/transmit");

const compose_closed_ui = zrequire("compose_closed_ui");
const compose_fade = zrequire("compose_fade");
const compose_pm_pill = zrequire("compose_pm_pill");
const compose_state = zrequire("compose_state");
const compose = zrequire("compose");
const echo = zrequire("echo");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const upload = zrequire("upload");

function reset_jquery() {
    // Avoid leaks.
    $.clear_all_elements();
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

const social = {
    stream_id: 101,
    name: "social",
    subscribed: true,
};
stream_data.add_sub(social);

function test_ui(label, f) {
    // TODO: initialize data more aggressively.
    run_test(label, f);
}

function initialize_handlers({override, override_rewire}) {
    override_rewire(compose, "compute_show_video_chat_button", () => false);
    override_rewire(upload, "setup_upload", () => undefined);
    override(resize, "watch_manual_resize", () => {});
    compose.initialize();
}

test_ui("send_message_success", ({override_rewire}) => {
    $("#compose-textarea").val("foobarfoobar");
    $("#compose-textarea").trigger("blur");
    $("#compose-send-status").show();
    $("#compose-send-button .loader").show();

    let reify_message_id_checked;
    override_rewire(echo, "reify_message_id", (local_id, message_id) => {
        assert.equal(local_id, "1001");
        assert.equal(message_id, 12);
        reify_message_id_checked = true;
    });

    compose.send_message_success("1001", 12, false);

    assert.equal($("#compose-textarea").val(), "");
    assert.ok($("#compose-textarea").is_focused());
    assert.ok(!$("#compose-send-status").visible());
    assert.ok(!$("#compose-send-button .loader").visible());

    assert.ok(reify_message_id_checked);
});

test_ui("send_message", ({override, override_rewire}) => {
    MockDate.set(new Date(fake_now * 1000));

    override(sent_messages, "start_tracking_message", () => {});

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

    override(server_events, "assert_get_events_running", () => {
        stub_state.get_events_running_called += 1;
    });

    // Tests start here.
    (function test_message_send_success_codepath() {
        stub_state = initialize_state_stub_dict();
        compose_state.topic("");
        compose_state.set_message_type("private");
        page_params.user_id = new_user.user_id;
        override_rewire(compose_state, "private_message_recipient", () => "alice@example.com");

        const server_message_id = 127;
        override_rewire(echo, "insert_message", (message) => {
            assert.equal(message.timestamp, fake_now);
        });

        override(markdown, "apply_markdown", () => {});
        override(markdown, "add_topic_links", () => {});

        override_rewire(echo, "try_deliver_locally", (message_request) => {
            const local_id_float = 123.04;
            return echo.insert_local_message(message_request, local_id_float);
        });

        override(transmit, "send_message", (payload, success) => {
            const single_msg = {
                type: "private",
                content: "[foobar](/user_uploads/123456)",
                sender_id: new_user.user_id,
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
        });

        override_rewire(echo, "reify_message_id", (local_id, message_id) => {
            assert.equal(typeof local_id, "string");
            assert.equal(typeof message_id, "number");
            assert.equal(message_id, server_message_id);
            stub_state.reify_message_id_checked += 1;
        });

        $("#compose-textarea").val("[foobar](/user_uploads/123456)");
        $("#compose-textarea").trigger("blur");
        $("#compose-send-status").show();
        $("#compose-send-button .loader").show();

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 1,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert.equal($("#compose-textarea").val(), "");
        assert.ok($("#compose-textarea").is_focused());
        assert.ok(!$("#compose-send-status").visible());
        assert.ok(!$("#compose-send-button .loader").visible());
    })();

    // This is the additional setup which is common to both the tests below.
    override(transmit, "send_message", (payload, success, error) => {
        stub_state.send_msg_called += 1;
        error("Error sending message: Server says 408");
    });

    let echo_error_msg_checked;

    override_rewire(echo, "message_send_error", (local_id, error_response) => {
        assert.equal(local_id, 123.04);
        assert.equal(error_response, "Error sending message: Server says 408");
        echo_error_msg_checked = true;
    });

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
        assert.ok(echo_error_msg_checked);
    })();

    (function test_error_codepath_local_id_undefined() {
        stub_state = initialize_state_stub_dict();
        $("#compose-textarea").val("foobarfoobar");
        $("#compose-textarea").trigger("blur");
        $("#compose-send-status").show();
        $("#compose-send-button .loader").show();
        $("#compose-textarea").off("select");
        echo_error_msg_checked = false;
        override_rewire(echo, "try_deliver_locally", () => {});

        override(sent_messages, "get_new_local_id", () => "loc-55");

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 0,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert.ok(!echo_error_msg_checked);
        assert.equal($("#compose-error-msg").html(), "Error sending message: Server says 408");
        assert.equal($("#compose-textarea").val(), "foobarfoobar");
        assert.ok($("#compose-textarea").is_focused());
        assert.ok($("#compose-send-status").visible());
        assert.ok(!$("#compose-send-button .loader").visible());
    })();
});

test_ui("enter_with_preview_open", ({override, override_rewire}) => {
    override(notifications, "clear_compose_notifications", () => {});
    override(reminder, "is_deferred_delivery", () => false);
    override(document, "to_$", () => $("document-stub"));
    let show_button_spinner_called = false;
    override(loading, "show_button_spinner", (spinner) => {
        assert.equal(spinner.selector, "#compose-send-button .loader");
        show_button_spinner_called = true;
    });

    page_params.user_id = new_user.user_id;

    // Test sending a message with content.
    compose_state.set_message_type("stream");
    compose_state.stream_name("social");

    $("#compose-textarea").val("message me");
    $("#compose-textarea").hide();
    $("#compose .undo_markdown_preview").show();
    $("#compose .preview_message_area").show();
    $("#compose .markdown_preview").hide();
    user_settings.enter_sends = true;
    let send_message_called = false;
    override_rewire(compose, "send_message", () => {
        send_message_called = true;
    });
    compose.enter_with_preview_open();
    assert.ok($("#compose-textarea").visible());
    assert.ok(!$("#compose .undo_markdown_preview").visible());
    assert.ok(!$("#compose .preview_message_area").visible());
    assert.ok($("#compose .markdown_preview").visible());
    assert.ok(send_message_called);
    assert.ok(show_button_spinner_called);

    user_settings.enter_sends = false;
    $("#compose-textarea").trigger("blur");
    compose.enter_with_preview_open();
    assert.ok($("#compose-textarea").is_focused());

    // Test sending a message without content.
    $("#compose-textarea").val("");
    $("#compose .preview_message_area").show();
    user_settings.enter_sends = true;

    compose.enter_with_preview_open();
    assert.equal($("#compose-error-msg").html(), "never-been-set");
});

test_ui("finish", ({override, override_rewire}) => {
    override(notifications, "clear_compose_notifications", () => {});
    override(reminder, "is_deferred_delivery", () => false);
    override(document, "to_$", () => $("document-stub"));
    let show_button_spinner_called = false;
    override(loading, "show_button_spinner", (spinner) => {
        assert.equal(spinner.selector, "#compose-send-button .loader");
        show_button_spinner_called = true;
    });

    (function test_when_compose_validation_fails() {
        $("#compose_invite_users").show();
        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $("#compose-send-button .loader").hide();
        $("#compose-textarea").off("select");
        $("#compose-textarea").val("");
        const res = compose.finish();
        assert.equal(res, false);
        assert.ok(!$("#compose_invite_users").visible());
        assert.ok(!$("#compose-send-button .loader").visible());
        assert.equal(
            $("#compose-error-msg").html(),
            $t_html({defaultMessage: "You have nothing to send!"}),
        );
        assert.ok(show_button_spinner_called);
    })();

    (function test_when_compose_validation_succeed() {
        // Testing successfully sending of a message.
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();
        $("#compose .markdown_preview").hide();
        $("#compose-textarea").val("foobarfoobar");
        compose_state.set_message_type("private");
        override_rewire(compose_state, "private_message_recipient", () => "bob@example.com");
        override_rewire(compose_pm_pill, "get_user_ids", () => []);

        let compose_finished_event_checked = false;
        $(document).on("compose_finished.zulip", () => {
            compose_finished_event_checked = true;
        });
        let send_message_called = false;
        override_rewire(compose, "send_message", () => {
            send_message_called = true;
        });
        assert.ok(compose.finish());
        assert.ok($("#compose-textarea").visible());
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok(!$("#compose .preview_message_area").visible());
        assert.ok($("#compose .markdown_preview").visible());
        assert.ok(send_message_called);
        assert.ok(compose_finished_event_checked);

        // Testing successful scheduling of message.
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();
        $("#compose .markdown_preview").hide();
        $("#compose-textarea").val("foobarfoobar");
        compose_state.set_message_type("stream");
        override_rewire(compose_state, "stream_name", () => "social");
        override_rewire(people, "get_by_user_id", () => []);
        compose_finished_event_checked = false;
        let schedule_message = false;
        override(reminder, "schedule_message", () => {
            schedule_message = true;
        });
        reminder.is_deferred_delivery = () => true;
        assert.ok(compose.finish());
        assert.ok($("#compose-textarea").visible());
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok(!$("#compose .preview_message_area").visible());
        assert.ok($("#compose .markdown_preview").visible());
        assert.ok(schedule_message);
        assert.ok(compose_finished_event_checked);
    })();
});

test_ui("initialize", ({override, override_rewire}) => {
    let compose_actions_expected_opts;
    let compose_actions_start_checked;

    override(compose_actions, "start", (msg_type, opts) => {
        assert.equal(msg_type, "stream");
        assert.deepEqual(opts, compose_actions_expected_opts);
        compose_actions_start_checked = true;
    });

    // In this test we mostly do the setup stuff in addition to testing the
    // normal workflow of the function. All the tests for the on functions are
    // done in subsequent tests directly below this test.

    override_rewire(compose, "compute_show_video_chat_button", () => false);

    let resize_watch_manual_resize_checked = false;
    override(resize, "watch_manual_resize", (elem) => {
        assert.equal("#compose-textarea", elem);
        resize_watch_manual_resize_checked = true;
    });

    let xmlhttprequest_checked = false;
    set_global("XMLHttpRequest", function () {
        this.upload = true;
        xmlhttprequest_checked = true;
    });
    $("#compose .compose_upload_file").addClass("notdisplayed");

    page_params.max_file_upload_size_mib = 512;

    let setup_upload_called = false;
    let uppy_cancel_all_called = false;
    override_rewire(upload, "setup_upload", (config) => {
        assert.equal(config.mode, "compose");
        setup_upload_called = true;
        return {
            cancelAll: () => {
                uppy_cancel_all_called = true;
            },
        };
    });

    compose.initialize();

    assert.ok(resize_watch_manual_resize_checked);
    assert.ok(xmlhttprequest_checked);
    assert.ok(!$("#compose .compose_upload_file").hasClass("notdisplayed"));
    assert.ok(setup_upload_called);

    function set_up_compose_start_mock(expected_opts) {
        compose_actions_start_checked = false;
        compose_actions_expected_opts = expected_opts;
    }

    (function test_page_params_narrow_path() {
        page_params.narrow = true;

        reset_jquery();
        set_up_compose_start_mock({});

        compose.initialize();

        assert.ok(compose_actions_start_checked);
    })();

    (function test_page_params_narrow_topic() {
        page_params.narrow_topic = "testing";

        reset_jquery();
        set_up_compose_start_mock({topic: "testing"});

        compose.initialize();

        assert.ok(compose_actions_start_checked);
    })();

    (function test_abort_xhr() {
        reset_jquery();
        compose.initialize();

        compose.abort_xhr();

        assert.equal($("#compose-send-button").attr(), undefined);
        assert.ok(uppy_cancel_all_called);
    })();
});

test_ui("update_fade", ({override, override_rewire}) => {
    initialize_handlers({override, override_rewire});

    const selector =
        "#stream_message_recipient_stream,#stream_message_recipient_topic,#private_message_recipient";
    const keyup_handler_func = $(selector).get_on_handler("keyup");

    let set_focused_recipient_checked = false;
    let update_all_called = false;

    override_rewire(compose_fade, "set_focused_recipient", (msg_type) => {
        assert.equal(msg_type, "private");
        set_focused_recipient_checked = true;
    });

    override_rewire(compose_fade, "update_all", () => {
        update_all_called = true;
    });

    compose_state.set_message_type(false);
    keyup_handler_func();
    assert.ok(!set_focused_recipient_checked);
    assert.ok(!update_all_called);

    compose_state.set_message_type("private");
    keyup_handler_func();
    assert.ok(set_focused_recipient_checked);
    assert.ok(update_all_called);
});

test_ui("trigger_submit_compose_form", ({override, override_rewire}) => {
    initialize_handlers({override, override_rewire});

    let prevent_default_checked = false;
    let compose_finish_checked = false;
    const e = {
        preventDefault() {
            prevent_default_checked = true;
        },
    };
    override_rewire(compose, "finish", () => {
        compose_finish_checked = true;
    });

    const submit_handler = $("#compose form").get_on_handler("submit");

    submit_handler(e);

    assert.ok(prevent_default_checked);
    assert.ok(compose_finish_checked);
});

test_ui("on_events", ({override, override_rewire}) => {
    initialize_handlers({override, override_rewire});

    override(rendered_markdown, "update_elements", () => {});

    function setup_parents_and_mock_remove(container_sel, target_sel, parent) {
        const container = $.create("fake " + container_sel);
        let container_removed = false;

        container.remove = () => {
            container_removed = true;
        };

        const target = $.create("fake click target (" + target_sel + ")");

        target.set_parents_result(parent, container);

        const event = {
            preventDefault: noop,
            stopPropagation: noop,
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
        override_rewire(compose, "finish", () => {
            compose_finish_checked = true;
        });

        handler(helper.event);

        assert.ok(helper.container_was_removed());
        assert.ok(compose_finish_checked);
        assert.ok(!$("#compose-all-everyone").visible());
        assert.ok(!$("#compose-send-status").visible());
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
        override(stream_subscribers_ui, "invite_user_to_stream", (user_ids, sub, success) => {
            invite_user_to_stream_called = true;
            assert.deepEqual(user_ids, [mentioned.user_id]);
            assert.equal(sub, subscription);
            success(); // This will check success callback path.
        });

        const helper = setup_parents_and_mock_remove(
            "compose_invite_users",
            "compose_invite_link",
            ".compose_invite_user",
        );

        helper.container.data = (field) => {
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
        $("#compose_invite_users").children = () => {
            all_invite_children_called = true;
            return [];
        };
        $("#compose_invite_users").show();

        handler(helper.event);

        assert.ok(helper.container_was_removed());
        assert.ok(!$("#compose_invite_users").visible());
        assert.ok(invite_user_to_stream_called);
        assert.ok(all_invite_children_called);
    })();

    (function test_compose_invite_close_clicked() {
        const handler = $("#compose_invite_users").get_on_handler("click", ".compose_invite_close");

        const helper = setup_parents_and_mock_remove(
            "compose_invite_users_close",
            "compose_invite_close",
            ".compose_invite_user",
        );

        let all_invite_children_called = false;
        $("#compose_invite_users").children = () => {
            all_invite_children_called = true;
            return [];
        };
        $("#compose_invite_users").show();

        handler(helper.event);

        assert.ok(helper.container_was_removed());
        assert.ok(all_invite_children_called);
        assert.ok(!$("#compose_invite_users").visible());
    })();

    (function test_compose_not_subscribed_clicked() {
        const handler = $("#compose-send-status").get_on_handler("click", ".sub_unsub_button");
        const subscription = {
            stream_id: 102,
            name: "test",
            subscribed: false,
        };
        let compose_not_subscribed_called = false;
        stream_settings_ui.sub_or_unsub = () => {
            compose_not_subscribed_called = true;
        };

        const helper = setup_parents_and_mock_remove(
            "compose-send-status",
            "sub_unsub_button",
            ".compose_not_subscribed",
        );

        handler(helper.event);

        assert.ok(compose_not_subscribed_called);

        stream_data.add_sub(subscription);
        $("#stream_message_recipient_stream").val("test");
        $("#compose-send-status").show();

        handler(helper.event);

        assert.ok(!$("#compose-send-status").visible());
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

        assert.ok(!$("#compose-send-status").visible());
    })();

    (function test_attach_files_compose_clicked() {
        const handler = $("#compose").get_on_handler("click", ".compose_upload_file");
        $("#compose .file_input").clone = (param) => {
            assert.ok(param);
        };
        let compose_file_input_clicked = false;
        $("#compose .file_input").on("click", () => {
            compose_file_input_clicked = true;
        });

        const event = {
            preventDefault: noop,
            stopPropagation: noop,
        };

        handler(event);
        assert.ok(compose_file_input_clicked);
    })();

    (function test_markdown_preview_compose_clicked() {
        let reset_compose_message_max_height_called = false;
        override(resize, "reset_compose_message_max_height", () => {
            reset_compose_message_max_height_called = true;
        });

        // Tests setup
        function setup_visibilities() {
            $("#compose-textarea").show();
            $("#compose .markdown_preview").show();
            $("#compose .undo_markdown_preview").hide();
            $("#compose .preview_message_area").hide();
        }

        function assert_visibilities() {
            assert.ok(!$("#compose-textarea").visible());
            assert.ok(!$("#compose .markdown_preview").visible());
            assert.ok($("#compose .undo_markdown_preview").visible());
            assert.ok($("#compose .preview_message_area").visible());
        }

        function setup_mock_markdown_contains_backend_only_syntax(msg_content, return_val) {
            override(markdown, "contains_backend_only_syntax", (msg) => {
                assert.equal(msg, msg_content);
                return return_val;
            });
        }

        function setup_mock_markdown_is_status_message(msg_content, return_val) {
            override(markdown, "is_status_message", (content) => {
                assert.equal(content, msg_content);
                return return_val;
            });
        }

        function test_post_success(success_callback) {
            const resp = {
                rendered: "Server: foobarfoobar",
            };
            success_callback(resp);
            assert.equal($("#compose .preview_content").html(), "Server: foobarfoobar");
        }

        function test_post_error(error_callback) {
            error_callback();
            assert.equal(
                $("#compose .preview_content").html(),
                "translated HTML: Failed to generate preview",
            );
        }

        let current_message;

        override(channel, "post", (payload) => {
            assert.equal(payload.url, "/json/messages/render");
            assert.ok(payload.idempotent);
            assert.ok(payload.data);
            assert.deepEqual(payload.data.content, current_message);

            function test(func, param) {
                let destroy_indicator_called = false;
                override(loading, "destroy_indicator", (spinner) => {
                    assert.equal(spinner, $("#compose .markdown_preview_spinner"));
                    destroy_indicator_called = true;
                });
                setup_mock_markdown_contains_backend_only_syntax(current_message, true);

                func(param);

                assert.ok(destroy_indicator_called);
            }

            test(test_post_error, payload.error);
            test(test_post_success, payload.success);
        });

        const handler = $("#compose").get_on_handler("click", ".markdown_preview");

        // Tests start here
        $("#compose-textarea").val("");
        setup_visibilities();

        const event = {
            preventDefault: noop,
            stopPropagation: noop,
        };

        handler(event);

        assert.equal($("#compose .preview_content").html(), "translated HTML: Nothing to preview");
        assert_visibilities();
        assert.ok(reset_compose_message_max_height_called);

        let make_indicator_called = false;
        $("#compose-textarea").val("```foobarfoobar```");
        setup_visibilities();
        setup_mock_markdown_contains_backend_only_syntax("```foobarfoobar```", true);
        setup_mock_markdown_is_status_message("```foobarfoobar```", false);

        override(loading, "make_indicator", (spinner) => {
            assert.equal(spinner.selector, "#compose .markdown_preview_spinner");
            make_indicator_called = true;
        });

        current_message = "```foobarfoobar```";

        handler(event);

        assert.ok(make_indicator_called);
        assert_visibilities();

        let apply_markdown_called = false;
        $("#compose-textarea").val("foobarfoobar");
        setup_visibilities();
        setup_mock_markdown_contains_backend_only_syntax("foobarfoobar", false);
        setup_mock_markdown_is_status_message("foobarfoobar", false);

        current_message = "foobarfoobar";

        override(markdown, "apply_markdown", (msg) => {
            assert.equal(msg.raw_content, "foobarfoobar");
            apply_markdown_called = true;
            return msg;
        });

        handler(event);

        assert.ok(apply_markdown_called);
        assert_visibilities();
        assert.equal($("#compose .preview_content").html(), "Server: foobarfoobar");
    })();

    (function test_undo_markdown_preview_clicked() {
        const handler = $("#compose").get_on_handler("click", ".undo_markdown_preview");

        $("#compose-textarea").hide();
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();
        $("#compose .markdown_preview").hide();

        const event = {
            preventDefault: noop,
            stopPropagation: noop,
        };

        handler(event);

        assert.ok($("#compose-textarea").visible());
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok(!$("#compose .preview_message_area").visible());
        assert.ok($("#compose .markdown_preview").visible());
    })();
});

test_ui("create_message_object", ({override_rewire}) => {
    $("#stream_message_recipient_stream").val("social");
    $("#stream_message_recipient_topic").val("lunch");
    $("#compose-textarea").val("burrito");

    override_rewire(compose_state, "get_message_type", () => "stream");

    let message = compose.create_message_object();
    assert.equal(message.to, social.stream_id);
    assert.equal(message.topic, "lunch");
    assert.equal(message.content, "burrito");

    blueslip.expect("error", "Trying to send message with bad stream name: BOGUS STREAM");

    $("#stream_message_recipient_stream").val("BOGUS STREAM");
    message = compose.create_message_object();
    assert.equal(message.to, "BOGUS STREAM");
    assert.equal(message.topic, "lunch");
    assert.equal(message.content, "burrito");

    override_rewire(compose_state, "get_message_type", () => "private");
    compose_state.__Rewire__(
        "private_message_recipient",
        () => "alice@example.com, bob@example.com",
    );

    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.user_id, bob.user_id]);
    assert.equal(message.to_user_ids, "31,32");
    assert.equal(message.content, "burrito");

    const {email_list_to_user_ids_string} = people;
    override_rewire(people, "email_list_to_user_ids_string", () => undefined);
    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.email, bob.email]);
    people.email_list_to_user_ids_string = email_list_to_user_ids_string;
});

test_ui("narrow_button_titles", () => {
    compose_closed_ui.update_buttons_for_private();
    assert.equal(
        $("#left_bar_compose_stream_button_big").text(),
        $t({defaultMessage: "New stream message"}),
    );
    assert.equal(
        $("#left_bar_compose_private_button_big").text(),
        $t({defaultMessage: "New private message"}),
    );

    compose_closed_ui.update_buttons_for_stream();
    assert.equal(
        $("#left_bar_compose_stream_button_big").text(),
        $t({defaultMessage: "New topic"}),
    );
    assert.equal(
        $("#left_bar_compose_private_button_big").text(),
        $t({defaultMessage: "New private message"}),
    );
});

MockDate.reset();
