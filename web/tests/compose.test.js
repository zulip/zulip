"use strict";

const {strict: assert} = require("assert");

const MockDate = require("mockdate");

const {mock_stream_header_colorblock} = require("./lib/compose");
const {mock_banners} = require("./lib/compose_banner");
const {$t} = require("./lib/i18n");
const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params, user_settings} = require("./lib/zpage_params");

const settings_config = zrequire("settings_config");

const noop = () => {};

set_global("document", {
    querySelector() {},
});
set_global("navigator", {});
set_global(
    "ResizeObserver",
    class ResizeObserver {
        observe() {}
    },
);

const fake_now = 555;

const autosize = () => {};
autosize.update = () => {};
mock_esm("autosize", {default: autosize});

const channel = mock_esm("../src/channel");
const compose_actions = mock_esm("../src/compose_actions", {
    register_compose_cancel_hook: noop,
    register_compose_box_clear_hook: noop,
});
const compose_fade = mock_esm("../src/compose_fade");
const compose_pm_pill = mock_esm("../src/compose_pm_pill");
const loading = mock_esm("../src/loading");
const markdown = mock_esm("../src/markdown");
const narrow_state = mock_esm("../src/narrow_state");
const rendered_markdown = mock_esm("../src/rendered_markdown");
const resize = mock_esm("../src/resize");
const sent_messages = mock_esm("../src/sent_messages");
const server_events = mock_esm("../src/server_events");
const transmit = mock_esm("../src/transmit");
const upload = mock_esm("../src/upload");

const compose_ui = zrequire("compose_ui");
const compose_banner = zrequire("compose_banner");
const compose_closed_ui = zrequire("compose_closed_ui");
const compose_recipient = zrequire("compose_recipient");
const compose_state = zrequire("compose_state");
const compose = zrequire("compose");
const echo = zrequire("echo");
const people = zrequire("people");
const stream_data = zrequire("stream_data");

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
    is_bot: false,
};

const bob = {
    email: "bob@example.com",
    user_id: 32,
    full_name: "Bob",
};

const bot = {
    email: "bot@example.com",
    user_id: 33,
    full_name: "Bot",
    is_bot: true,
};

people.add_active_user(new_user);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(bot);

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

function initialize_handlers({override}) {
    override(page_params, "realm_available_video_chat_providers", {disabled: {id: 0}});
    override(page_params, "realm_video_chat_provider", 0);
    override(upload, "setup_upload", () => undefined);
    override(upload, "feature_check", () => {});
    override(resize, "watch_manual_resize", () => {});
    compose.initialize();
}

test_ui("send_message_success", ({override_rewire}) => {
    mock_banners();
    $("#compose-textarea").val("foobarfoobar");
    $("#compose-textarea").trigger("blur");
    $(".compose-submit-button .loader").show();

    let reify_message_id_checked;
    override_rewire(echo, "reify_message_id", (local_id, message_id) => {
        assert.equal(local_id, "1001");
        assert.equal(message_id, 12);
        reify_message_id_checked = true;
    });

    compose.send_message_success("1001", 12, false);

    assert.equal($("#compose-textarea").val(), "");
    assert.ok($("#compose-textarea").is_focused());
    assert.ok(!$(".compose-submit-button .loader").visible());

    assert.ok(reify_message_id_checked);
});

test_ui("send_message", ({override, override_rewire, mock_template}) => {
    mock_banners();
    MockDate.set(new Date(fake_now * 1000));

    // This is the common setup stuff for all of the four tests.
    let stub_state;
    function initialize_state_stub_dict() {
        stub_state = {};
        stub_state.send_msg_called = 0;
        stub_state.get_events_running_called = 0;
        stub_state.reify_message_id_checked = 0;
        return stub_state;
    }

    const $container = $(".top_left_drafts");
    const $child = $(".unread_count");
    $container.set_find_results(".unread_count", $child);

    override(server_events, "assert_get_events_running", () => {
        stub_state.get_events_running_called += 1;
    });

    // Tests start here.
    (function test_message_send_success_codepath() {
        stub_state = initialize_state_stub_dict();
        compose_state.topic("");
        compose_state.set_message_type("private");
        page_params.user_id = new_user.user_id;
        override(compose_pm_pill, "get_emails", () => "alice@example.com");

        const server_message_id = 127;
        override(markdown, "apply_markdown", () => {});
        override(markdown, "add_topic_links", () => {});

        override_rewire(echo, "try_deliver_locally", (message_request) => {
            const local_id_float = 123.04;
            return echo.insert_local_message(message_request, local_id_float, (messages) =>
                assert.equal(messages[0].timestamp, fake_now),
            );
        });

        override(transmit, "send_message", (payload, success) => {
            const single_msg = {
                type: "private",
                content: "[foobar](/user_uploads/123456)",
                sender_id: new_user.user_id,
                queue_id: undefined,
                resend: false,
                stream_id: "",
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
        $(".compose-submit-button .loader").show();

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 1,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert.equal($("#compose-textarea").val(), "");
        assert.ok($("#compose-textarea").is_focused());
        assert.ok(!$(".compose-submit-button .loader").visible());
    })();

    // This is the additional setup which is common to both the tests below.
    override(transmit, "send_message", (_payload, _success, error) => {
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
        let banner_rendered = false;
        mock_template("compose_banner/compose_banner.hbs", false, (data) => {
            assert.equal(data.classname, "generic_compose_error");
            assert.equal(data.banner_text, "Error sending message: Server says 408");
            banner_rendered = true;
        });
        stub_state = initialize_state_stub_dict();
        $("#compose-textarea").val("foobarfoobar");
        $("#compose-textarea").trigger("blur");
        $(".compose-submit-button .loader").show();
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
        assert.ok(banner_rendered);
        assert.equal($("#compose-textarea").val(), "foobarfoobar");
        assert.ok($("#compose-textarea").is_focused());
        assert.ok(!$(".compose-submit-button .loader").visible());
    })();
});

test_ui("enter_with_preview_open", ({override, override_rewire}) => {
    mock_banners();
    $("#compose-textarea").toggleClass = noop;
    mock_stream_header_colorblock();
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);
    override_rewire(compose_banner, "clear_message_sent_banners", () => {});
    override(document, "to_$", () => $("document-stub"));
    let show_button_spinner_called = false;
    override(loading, "show_button_spinner", ($spinner) => {
        assert.equal($spinner.selector, ".compose-submit-button .loader");
        show_button_spinner_called = true;
    });

    page_params.user_id = new_user.user_id;

    // Test sending a message with content.
    compose_state.set_message_type("stream");
    compose_state.set_stream_id(social.stream_id);

    $("#compose-textarea").val("message me");
    $("#compose-textarea").hide();
    $("#compose .undo_markdown_preview").show();
    $("#compose .preview_message_area").show();
    $("#compose .markdown_preview").hide();
    $("#compose").addClass("preview_mode");
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
    assert.ok(!$("#compose").hasClass("preview_mode"));
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
});

test_ui("finish", ({override, override_rewire}) => {
    mock_banners();
    mock_stream_header_colorblock();

    override_rewire(compose_banner, "clear_message_sent_banners", () => {});
    override(document, "to_$", () => $("document-stub"));
    let show_button_spinner_called = false;
    override(loading, "show_button_spinner", ($spinner) => {
        assert.equal($spinner.selector, ".compose-submit-button .loader");
        show_button_spinner_called = true;
    });

    (function test_when_compose_validation_fails() {
        $("#compose-textarea").toggleClass = (classname, value) => {
            assert.equal(classname, "invalid");
            assert.equal(value, true);
        };
        $("#compose_invite_users").show();
        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-button").trigger("focus");
        $(".compose-submit-button .loader").hide();
        $("#compose-textarea").off("select");
        $("#compose-textarea").val("");
        override_rewire(compose_ui, "compose_spinner_visible", false);
        const res = compose.finish();
        assert.equal(res, false);
        assert.ok(!$("#compose_banners .recipient_not_subscribed").visible());
        assert.ok(!$(".compose-submit-button .loader").visible());
        assert.ok(show_button_spinner_called);
    })();

    (function test_when_compose_validation_succeed() {
        // Testing successfully sending of a message.
        $("#compose .undo_markdown_preview").show();
        $("#compose .preview_message_area").show();
        $("#compose .markdown_preview").hide();
        $("#compsoe").addClass("preview_mode");
        $("#compose-textarea").val("foobarfoobar");
        override_rewire(compose_ui, "compose_spinner_visible", false);
        compose_state.set_message_type("private");
        override(compose_pm_pill, "get_emails", () => "bob@example.com");
        override(compose_pm_pill, "get_user_ids", () => []);

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
        assert.ok(!$("#compose").hasClass("preview_mode"));
        assert.ok(send_message_called);
        assert.ok(compose_finished_event_checked);
    })();
});

test_ui("initialize", ({override}) => {
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

    override(page_params, "realm_available_video_chat_providers", {disabled: {id: 0}});
    override(page_params, "realm_video_chat_provider", 0);

    let resize_watch_manual_resize_checked = false;
    override(resize, "watch_manual_resize", (elem) => {
        assert.equal("#compose-textarea", elem);
        resize_watch_manual_resize_checked = true;
    });

    page_params.max_file_upload_size_mib = 512;

    let setup_upload_called = false;
    let uppy_cancel_all_called = false;
    override(upload, "setup_upload", (config) => {
        assert.equal(config.mode, "compose");
        setup_upload_called = true;
        return {
            cancelAll() {
                uppy_cancel_all_called = true;
            },
        };
    });
    override(upload, "feature_check", () => {});

    compose.initialize();

    assert.ok(resize_watch_manual_resize_checked);
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
    mock_banners();
    initialize_handlers({override});

    let set_focused_recipient_checked = false;
    let update_all_called = false;
    let update_narrow_to_recipient_visibility_called = false;

    override(compose_fade, "set_focused_recipient", (msg_type) => {
        assert.equal(msg_type, "private");
        set_focused_recipient_checked = true;
    });

    override(compose_fade, "update_all", () => {
        update_all_called = true;
    });

    override_rewire(compose_recipient, "update_narrow_to_recipient_visibility", () => {
        update_narrow_to_recipient_visibility_called = true;
    });

    compose_state.set_message_type(false);
    compose_recipient.update_on_recipient_change();
    assert.ok(!set_focused_recipient_checked);
    assert.ok(!update_all_called);
    assert.ok(update_narrow_to_recipient_visibility_called);

    update_narrow_to_recipient_visibility_called = false;

    compose_state.set_message_type("private");
    compose_recipient.update_on_recipient_change();
    assert.ok(set_focused_recipient_checked);
    assert.ok(update_all_called);
    assert.ok(update_narrow_to_recipient_visibility_called);
});

test_ui("trigger_submit_compose_form", ({override, override_rewire}) => {
    initialize_handlers({override});

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
    mock_stream_header_colorblock();

    initialize_handlers({override});

    override(rendered_markdown, "update_elements", () => {});

    (function test_attach_files_compose_clicked() {
        const handler = $("#compose").get_on_handler("click", ".compose_upload_file");
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
        // Tests setup
        function setup_visibilities() {
            $("#compose-textarea").show();
            $("#compose .markdown_preview").show();
            $("#compose .undo_markdown_preview").hide();
            $("#compose .preview_message_area").hide();
            $("#compose").removeClass("preview_mode");
        }

        function assert_visibilities() {
            assert.ok(!$("#compose-textarea").visible());
            assert.ok(!$("#compose .markdown_preview").visible());
            assert.ok($("#compose .undo_markdown_preview").visible());
            assert.ok($("#compose .preview_message_area").visible());
            assert.ok($("#compose").hasClass("preview_mode"));
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
            assert.ok(payload.data);
            assert.deepEqual(payload.data.content, current_message);

            function test(func, param) {
                let destroy_indicator_called = false;
                override(loading, "destroy_indicator", ($spinner) => {
                    assert.equal($spinner, $("#compose .markdown_preview_spinner"));
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

        let make_indicator_called = false;
        $("#compose-textarea").val("```foobarfoobar```");
        setup_visibilities();
        setup_mock_markdown_contains_backend_only_syntax("```foobarfoobar```", true);
        setup_mock_markdown_is_status_message("```foobarfoobar```", false);

        override(loading, "make_indicator", ($spinner) => {
            assert.equal($spinner.selector, "#compose .markdown_preview_spinner");
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
        $("#compose").removeClass("preview_mode");

        const event = {
            preventDefault: noop,
            stopPropagation: noop,
        };

        override_rewire(compose_recipient, "update_placeholder_text", noop);

        handler(event);

        assert.ok($("#compose-textarea").visible());
        assert.ok(!$("#compose .undo_markdown_preview").visible());
        assert.ok(!$("#compose .preview_message_area").visible());
        assert.ok($("#compose .markdown_preview").visible());
        assert.ok(!$("#compose").hasClass("preview_mode"));
    })();
});

test_ui("create_message_object", ({override, override_rewire}) => {
    mock_stream_header_colorblock();
    mock_banners();
    override_rewire(compose_recipient, "on_compose_select_recipient_update", noop);

    compose_state.set_stream_id(social.stream_id);
    $("#stream_message_recipient_topic").val("lunch");
    $("#compose-textarea").val("burrito");

    compose_state.set_message_type("stream");

    let message = compose.create_message_object();
    assert.equal(message.to, social.stream_id);
    assert.equal(message.topic, "lunch");
    assert.equal(message.content, "burrito");

    compose_state.set_message_type("private");
    override(compose_pm_pill, "get_emails", () => "alice@example.com,bob@example.com");

    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.user_id, bob.user_id]);
    assert.equal(message.to_user_ids, "31,32");
    assert.equal(message.content, "burrito");

    override_rewire(people, "email_list_to_user_ids_string", () => undefined);
    message = compose.create_message_object();
    assert.deepEqual(message.to, [alice.email, bob.email]);
});

test_ui("DM policy disabled", ({override, override_rewire}) => {
    // Disable dms in the organisation
    override(
        page_params,
        "realm_private_message_policy",
        settings_config.private_message_policy_values.disabled.code,
    );
    let reply_disabled = false;
    override_rewire(compose_closed_ui, "update_reply_button_state", (disabled = false) => {
        reply_disabled = disabled;
    });
    // For single bot recipient, Bot, the "Message X" button is not disabled
    override(narrow_state, "pm_ids_string", () => "33");
    compose_closed_ui.update_buttons_for_private();
    assert.ok(!reply_disabled);
    // For human user, Alice, the "Message X" button is disabled
    override(narrow_state, "pm_ids_string", () => "31");
    compose_closed_ui.update_buttons_for_private();
    assert.ok(reply_disabled);
});

test_ui("narrow_button_titles", ({override}) => {
    override(narrow_state, "pm_ids_string", () => "31");
    override(narrow_state, "is_message_feed_visible", () => true);
    compose_closed_ui.update_buttons_for_private();
    assert.equal(
        $("#left_bar_compose_stream_button_big").text(),
        $t({defaultMessage: "New stream message"}),
    );
    assert.equal(
        $("#left_bar_compose_private_button_big").text(),
        $t({defaultMessage: "New direct message"}),
    );

    compose_closed_ui.update_buttons_for_stream();
    assert.equal(
        $("#left_bar_compose_stream_button_big").text(),
        $t({defaultMessage: "New topic"}),
    );
    assert.equal(
        $("#left_bar_compose_private_button_big").text(),
        $t({defaultMessage: "New direct message"}),
    );
});

run_test("reset MockDate", () => {
    MockDate.reset();
});
