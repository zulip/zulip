"use strict";

const assert = require("node:assert/strict");

const MockDate = require("mockdate");

const {mock_banners} = require("./lib/compose_banner.cjs");
const {FakeComposeBox} = require("./lib/compose_helpers.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const user_groups = zrequire("user_groups");

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

const autosize = noop;
autosize.update = noop;
mock_esm("autosize", {default: autosize});

const channel = mock_esm("../src/channel");
const compose_actions = mock_esm("../src/compose_actions", {
    register_compose_cancel_hook: noop,
    register_compose_box_clear_hook: noop,
});
const compose_fade = mock_esm("../src/compose_fade");
const compose_notifications = mock_esm("../src/compose_notifications");
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
const onboarding_steps = mock_esm("../src/onboarding_steps");
mock_esm("../src/settings_data", {
    user_has_permission_for_group_setting: () => true,
    user_can_access_all_other_users: () => true,
});

const compose_ui = zrequire("compose_ui");
const compose_banner = zrequire("compose_banner");
const compose_closed_ui = zrequire("compose_closed_ui");
const compose_recipient = zrequire("compose_recipient");
const compose_state = zrequire("compose_state");
const compose = zrequire("compose");
const compose_setup = zrequire("compose_setup");
const drafts = zrequire("drafts");
const echo = zrequire("echo");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const compose_validate = zrequire("compose_validate");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const user_settings = {};
initialize_user_settings({user_settings});

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
    can_send_message_group: 2,
};
stream_data.add_sub(social);

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
    members: new Set([30, 101]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};

user_groups.initialize({realm_user_groups: [nobody, everyone]});

function test_ui(label, f) {
    // TODO: initialize data more aggressively.
    run_test(label, f);
}

function initialize_handlers({override}) {
    override(realm, "realm_available_video_chat_providers", {disabled: {id: 0}});
    override(realm, "realm_video_chat_provider", 0);
    override(resize, "watch_manual_resize", noop);
    compose_setup.initialize();
}

function disable_document_triggers(override) {
    override(document, "to_$", () => $("document-stub"));
}

function on_compose_finished_trigger_do(f) {
    $(document).on("compose_finished.zulip", f);
}

function simulate_draft_ui_interactions() {
    // Simulate DOM relationships so that code can execute,
    // but we won't actually examine these values.
    $(".top_left_drafts").set_find_results(".unread_count", $.create("draft-unread-count-stub"));
}

function assert_compose_send_button_attr_is_undefined() {
    assert.equal($("#compose-send-button").attr(), undefined);
}

test_ui("send_message_success", ({override, override_rewire}) => {
    mock_banners();

    const fake_compose_box = new FakeComposeBox();

    let draft_deleted;
    let reify_message_id_checked;

    function reset() {
        fake_compose_box.reset();
        draft_deleted = false;
        reify_message_id_checked = false;
    }

    reset();

    const draft_model = drafts.draft_model;
    override(draft_model, "deleteDraft", (draft_id) => {
        assert.equal(draft_id, 100);
        draft_deleted = true;
    });
    override_rewire(echo, "reify_message_id", (local_id, message_id) => {
        assert.equal(local_id, "1001");
        assert.equal(message_id, 12);
        reify_message_id_checked = true;
    });

    override(
        onboarding_steps,
        "ONE_TIME_NOTICES_TO_DISPLAY",
        new Set(["visibility_policy_banner"]),
    );

    override(compose_notifications, "notify_automatic_new_visibility_policy", (message, data) => {
        assert.equal(message.type, "stream");
        assert.equal(message.stream_id, 1);
        assert.equal(message.topic, "test");
        assert.equal(data.id, 12);
        assert.equal(data.automatic_new_visibility_policy, 2);
    });

    let request = {
        locally_echoed: false,
        local_id: "1001",
        draft_id: 100,
        type: "stream",
        stream_id: 1,
        topic: "test",
    };
    let data = {id: 12, automatic_new_visibility_policy: 2};
    compose.send_message_success(request, data);

    assert.equal(fake_compose_box.textarea_val(), "");
    assert.ok(fake_compose_box.is_textarea_focused());
    assert.ok(!fake_compose_box.is_submit_button_spinner_visible());
    assert.ok(reify_message_id_checked);
    assert.ok(draft_deleted);

    reset();

    override(compose_notifications, "get_muted_narrow", (message) => {
        assert.equal(message.type, "stream");
        assert.equal(message.stream_id, 2);
        assert.equal(message.topic, "test");
    });

    request = {
        locally_echoed: false,
        local_id: "1001",
        draft_id: 100,
        type: "stream",
        stream_id: 2,
        topic: "test",
    };
    data = {id: 12};
    compose.send_message_success(request, data);

    assert.equal(fake_compose_box.textarea_val(), "");
    assert.ok(fake_compose_box.is_textarea_focused());
    assert.ok(!fake_compose_box.is_submit_button_spinner_visible());
    assert.ok(reify_message_id_checked);
    assert.ok(draft_deleted);
});

test_ui("send_message", ({override, override_rewire, mock_template}) => {
    mock_banners();
    MockDate.set(new Date(fake_now * 1000));
    override_rewire(drafts, "sync_count", noop);

    const fake_compose_box = new FakeComposeBox();

    // Draft UI side-effects are out of the scope of this test,
    // but we need the code to not fail.
    // TODO: probably mock at a higher level.
    simulate_draft_ui_interactions();

    // This is the common setup stuff for all of the four tests.
    let stub_state;
    function initialize_state_stub_dict() {
        stub_state = {};
        stub_state.send_msg_called = 0;
        stub_state.get_events_running_called = 0;
        stub_state.reify_message_id_checked = 0;
        return stub_state;
    }

    override_rewire(drafts, "update_compose_draft_count", noop);

    override(server_events, "assert_get_events_running", () => {
        stub_state.get_events_running_called += 1;
    });

    override_rewire(drafts, "update_draft", () => 100);
    override(drafts.draft_model, "getDraft", (draft_id) => {
        assert.equal(draft_id, 100);
        return {};
    });

    // Tests start here.
    (function test_message_send_success_codepath() {
        stub_state = initialize_state_stub_dict();
        compose_state.topic("");
        compose_state.set_message_type("private");
        override(current_user, "user_id", new_user.user_id);
        override(compose_pm_pill, "get_emails", () => "alice@example.com");

        const server_message_id = 127;
        override(markdown, "render", noop);

        override_rewire(echo, "try_deliver_locally", (message_request) => {
            const local_id_float = 123.04;
            return echo.insert_local_message(message_request, local_id_float, (messages) => {
                assert.equal(messages[0].timestamp, fake_now);
                return messages;
            });
        });

        override(transmit, "send_message", (payload, success) => {
            const single_msg = {
                type: "private",
                content: "[foobar](/user_uploads/123456)",
                sender_id: new_user.user_id,
                queue_id: undefined,
                resend: false,
                stream_id: undefined,
                topic: "",
                to: `[${alice.user_id}]`,
                reply_to: "alice@example.com",
                private_message_recipient: "alice@example.com",
                to_user_ids: "31",
                draft_id: 100,
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

        fake_compose_box.set_textarea_val("[foobar](/user_uploads/123456)");
        fake_compose_box.blur_textarea();
        fake_compose_box.show_submit_button_spinner();

        compose.send_message();

        const state = {
            get_events_running_called: 1,
            reify_message_id_checked: 1,
            send_msg_called: 1,
        };
        assert.deepEqual(stub_state, state);
        assert.equal(fake_compose_box.textarea_val(), "");
        assert.ok(fake_compose_box.is_textarea_focused());
        assert.ok(!fake_compose_box.is_submit_button_spinner_visible());
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
            return "<banner-stub>";
        });
        stub_state = initialize_state_stub_dict();
        fake_compose_box.reset();
        echo_error_msg_checked = false;
        override_rewire(echo, "try_deliver_locally", noop);

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
        assert.equal(fake_compose_box.textarea_val(), "default message");
        assert.ok(fake_compose_box.is_textarea_focused());
        assert.ok(!fake_compose_box.is_submit_button_spinner_visible());
    })();
});

test_ui("handle_enter_key_with_preview_open", ({override, override_rewire}) => {
    mock_banners();
    override_rewire(compose_banner, "clear_message_sent_banners", noop);

    disable_document_triggers(override);

    let show_button_spinner_called = false;

    const fake_compose_box = new FakeComposeBox();

    override(loading, "show_button_spinner", ($spinner) => {
        assert.equal($spinner.selector, fake_compose_box.compose_spinner_selector());
        show_button_spinner_called = true;
    });

    override(current_user, "user_id", new_user.user_id);

    // Test sending a message with content.
    compose_state.set_message_type("stream");
    compose_state.set_stream_id(social.stream_id);

    fake_compose_box.set_textarea_val("message me");
    fake_compose_box.show_message_preview();

    override(user_settings, "enter_sends", true);
    let send_message_called = false;
    override_rewire(compose, "send_message", () => {
        send_message_called = true;
    });

    compose.handle_enter_key_with_preview_open();
    fake_compose_box.assert_preview_mode_is_off();

    assert.ok(send_message_called);
    assert.ok(show_button_spinner_called);

    override(user_settings, "enter_sends", false);
    fake_compose_box.blur_textarea();
    compose.handle_enter_key_with_preview_open();
    assert.ok(fake_compose_box.is_textarea_focused());

    // Test sending a message without content.
    fake_compose_box.set_textarea_val("");
    fake_compose_box.show_message_preview();
    override(user_settings, "enter_sends", true);

    compose.handle_enter_key_with_preview_open();
});

test_ui("finish", ({override, override_rewire}) => {
    mock_banners();
    disable_document_triggers(override);

    const fake_compose_box = new FakeComposeBox();

    override_rewire(compose_banner, "clear_message_sent_banners", noop);

    let show_button_spinner_called = false;
    override(loading, "show_button_spinner", ($spinner) => {
        assert.equal($spinner.selector, fake_compose_box.compose_spinner_selector());
        show_button_spinner_called = true;
    });

    (function test_when_compose_validation_fails() {
        // To trigger the empty banner error instead of other errors
        // set as per the priority.
        override(current_user, "user_id", new_user.user_id);
        compose_state.set_stream_id(social.stream_id);
        fake_compose_box.set_topic_val("lunch");
        fake_compose_box.set_textarea_val("burrito");
        compose_state.set_message_type("stream");

        fake_compose_box.set_textarea_toggle_class_function((classname, value) => {
            assert.equal(classname, "invalid");
            assert.equal(value, true);
        });

        fake_compose_box.set_textarea_val("");

        override_rewire(compose_ui, "compose_spinner_visible", false);
        const res = compose.finish();
        assert.equal(res, false);

        assert.ok(!fake_compose_box.is_recipient_not_subscribed_banner_visible());
        assert.ok(!fake_compose_box.is_submit_button_spinner_visible());

        assert.ok(show_button_spinner_called);
    })();

    (function test_when_compose_validation_succeed() {
        // Testing successfully sending of a message.
        fake_compose_box.show_message_preview();
        fake_compose_box.set_textarea_val("default message");

        override_rewire(compose_ui, "compose_spinner_visible", false);
        compose_state.set_message_type("private");
        override(compose_pm_pill, "get_emails", () => bob.email);
        override(compose_pm_pill, "get_user_ids", () => [bob.user_id]);
        override(realm, "realm_direct_message_permission_group", everyone.id);
        override(realm, "realm_direct_message_initiator_group", everyone.id);

        let compose_finished_event_checked = false;

        on_compose_finished_trigger_do(() => {
            compose_finished_event_checked = true;
        });

        let send_message_called = false;
        override_rewire(compose, "send_message", () => {
            send_message_called = true;
        });

        assert.ok(compose.finish());

        fake_compose_box.assert_preview_mode_is_off();
        assert.ok(send_message_called);
        assert.ok(compose_finished_event_checked);
    })();
});

test_ui("initialize", ({override}) => {
    let compose_actions_expected_opts;
    let compose_actions_start_checked;

    override(compose_actions, "start", (opts) => {
        assert.deepEqual(opts, compose_actions_expected_opts);
        compose_actions_start_checked = true;
    });

    // In this test we mostly do the setup stuff in addition to testing the
    // normal workflow of the function. All the tests for the on functions are
    // done in subsequent tests directly below this test.

    override(realm, "realm_available_video_chat_providers", {disabled: {id: 0}});
    override(realm, "realm_video_chat_provider", 0);

    let resize_watch_manual_resize_checked = false;
    override(resize, "watch_manual_resize", (elem) => {
        assert.equal("#compose-textarea", elem);
        resize_watch_manual_resize_checked = true;
    });

    override(realm, "max_file_upload_size_mib", 512);

    let uppy_cancel_all_called = false;
    override(upload, "compose_upload_cancel", () => {
        uppy_cancel_all_called = true;
    });

    compose_setup.initialize();

    assert.ok(resize_watch_manual_resize_checked);

    function set_up_compose_start_mock(expected_opts) {
        compose_actions_start_checked = false;
        compose_actions_expected_opts = {
            ...expected_opts,
            message_type: "stream",
        };
    }

    (function test_page_params_narrow_path() {
        page_params.narrow = true;

        reset_jquery();
        set_up_compose_start_mock({});

        compose_setup.initialize();

        assert.ok(compose_actions_start_checked);
    })();

    (function test_page_params_narrow_topic() {
        page_params.narrow_topic = "testing";

        reset_jquery();
        set_up_compose_start_mock({topic: "testing"});

        compose_setup.initialize();

        assert.ok(compose_actions_start_checked);
    })();

    (function test_abort_xhr() {
        reset_jquery();
        compose_setup.initialize();

        compose_setup.abort_xhr();

        // I'm not sure this proves anything interesting.
        assert_compose_send_button_attr_is_undefined();
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
    override_rewire(compose_validate, "validate_and_update_send_button_status", noop);
    override_rewire(drafts, "update_compose_draft_count", noop);
    override(compose_pm_pill, "get_user_ids", () => []);

    compose_state.set_message_type(undefined);
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

    override_rewire(compose, "finish", () => {
        compose_finish_checked = true;
    });

    new FakeComposeBox().trigger_submit_handler_on_compose_form({
        preventDefault() {
            prevent_default_checked = true;
        },
    });

    assert.ok(prevent_default_checked);
    assert.ok(compose_finish_checked);
});

test_ui("on_events", ({override, override_rewire}) => {
    initialize_handlers({override});

    override(rendered_markdown, "update_elements", noop);

    const fake_compose_box = new FakeComposeBox();

    (function test_attach_files_compose_clicked() {
        let compose_file_input_clicked = false;

        // For some reason clicking on the attachment icon
        // triggers a click handler on #compose .file_input
        // as part of our upload code, and we verify this
        // codepath.
        fake_compose_box.set_click_handler_for_upload_file_input_element(() => {
            compose_file_input_clicked = true;
        });

        fake_compose_box.click_on_upload_attachment_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.ok(compose_file_input_clicked);
    })();

    (function test_markdown_preview_compose_clicked() {
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
                msg: "",
                result: "success",
                rendered: "Server: default message",
            };
            success_callback(resp);

            assert.equal(fake_compose_box.preview_content_html(), "Server: default message");
        }

        function test_post_error(error_callback) {
            error_callback();
            assert.equal(
                fake_compose_box.preview_content_html(),
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
                    assert.equal($spinner.selector, fake_compose_box.markdown_spinner_selector());
                    destroy_indicator_called = true;
                });
                setup_mock_markdown_contains_backend_only_syntax(current_message, true);

                func(param);

                assert.ok(destroy_indicator_called);
            }

            test(test_post_error, payload.error);
            test(test_post_success, payload.success);
        });

        // Tests start here
        fake_compose_box.set_textarea_val("");
        fake_compose_box.hide_message_preview();

        fake_compose_box.click_on_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.equal(
            fake_compose_box.preview_content_html(),
            "translated HTML: Nothing to preview",
        );
        fake_compose_box.assert_preview_mode_is_on();

        let make_indicator_called = false;

        fake_compose_box.set_textarea_val("```default message```");
        fake_compose_box.hide_message_preview();
        setup_mock_markdown_contains_backend_only_syntax("```default message```", true);
        setup_mock_markdown_is_status_message("```default message```", false);

        override(loading, "make_indicator", ($spinner) => {
            assert.equal($spinner.selector, fake_compose_box.markdown_spinner_selector());
            make_indicator_called = true;
        });

        current_message = "```default message```";

        fake_compose_box.click_on_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.ok(make_indicator_called);
        fake_compose_box.assert_preview_mode_is_on();

        let render_called = false;
        fake_compose_box.set_textarea_val("default message");
        fake_compose_box.hide_message_preview();
        setup_mock_markdown_contains_backend_only_syntax("default message", false);
        setup_mock_markdown_is_status_message("default message", false);

        current_message = "default message";

        override(markdown, "render", (raw_content) => {
            assert.equal(raw_content, "default message");
            render_called = true;
        });

        fake_compose_box.click_on_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.ok(render_called);
        fake_compose_box.assert_preview_mode_is_on();
        assert.equal(fake_compose_box.preview_content_html(), "Server: default message");
    })();

    (function test_undo_markdown_preview_clicked() {
        fake_compose_box.show_message_preview();

        override_rewire(compose_recipient, "update_compose_area_placeholder_text", noop);
        override(compose_fade, "do_update_all", noop);
        override(narrow_state, "narrowed_by_reply", () => true);
        override(
            compose_notifications,
            "maybe_show_one_time_non_interleaved_view_messages_fading_banner",
            noop,
        );

        fake_compose_box.click_on_undo_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        fake_compose_box.assert_preview_mode_is_off();
    })();
});

test_ui("create_message_object", ({override, override_rewire}) => {
    mock_banners();

    const fake_compose_box = new FakeComposeBox();

    compose_state.set_stream_id(social.stream_id);

    fake_compose_box.set_topic_val("lunch");
    fake_compose_box.set_textarea_val("burrito");

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
    override(realm, "realm_direct_message_permission_group", nobody.id);
    override(realm, "realm_direct_message_initiator_group", everyone.id);
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

run_test("reset MockDate", () => {
    MockDate.reset();
});
