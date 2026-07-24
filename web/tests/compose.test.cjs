"use strict";

const assert = require("node:assert/strict");

const {mock_banners} = require("./lib/compose_banner.cjs");
const {FakeComposeBox} = require("./lib/compose_helpers.cjs");
const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_bot, make_user} = require("./lib/example_user.cjs");
const {clock, mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
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
const resize = mock_esm("../src/resize");
const sent_messages = mock_esm("../src/sent_messages");
const server_events_state = mock_esm("../src/server_events_state");
const transmit = mock_esm("../src/transmit");
const upload = mock_esm("../src/upload");
const onboarding_steps = mock_esm("../src/onboarding_steps", {
    ONE_TIME_NOTICES_TO_DISPLAY: new Set(),
});
mock_esm("../src/settings_data", {
    user_has_permission_for_group_setting: () => true,
});

mock_esm("../src/compose_textarea", {
    get_code_block_ranges: () => [],
    save_compose_cursor: noop,
    restore_compose_cursor: noop,
    initialize: noop,
});
mock_esm("../src/rendered_markdown", {update_elements: noop});

const compose_ui = zrequire("compose_ui");
const compose_banner_module = zrequire("compose_banner");
const compose_closed_ui = zrequire("compose_closed_ui");
const compose_recipient = zrequire("compose_recipient");
const compose_split_messages = zrequire("compose_split_messages");
const compose_state = zrequire("compose_state");
const compose = zrequire("compose");
const compose_setup = zrequire("compose_setup");
const drafts = zrequire("drafts");
const echo = zrequire("echo");
const people = zrequire("people");
const scheduled_messages = zrequire("scheduled_messages");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const compose_validate = zrequire("compose_validate");
const {initialize_user_settings} = zrequire("user_settings");

const realm = make_realm({realm_topics_policy: "allow_empty_topic"});
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const user_settings = {};
initialize_user_settings({user_settings});

function reset_jquery() {
    // Avoid leaks.
    $.clear_all_elements();
}

const new_user = make_user({
    email: "new_user@example.com",
    user_id: 101,
    full_name: "New User",
    date_joined: new Date(),
});

const me = make_user({
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
    date_joined: new Date(),
});

const alice = make_user({
    email: "alice@example.com",
    user_id: 31,
    full_name: "Alice",
});

const bob = make_user({
    email: "bob@example.com",
    user_id: 32,
    full_name: "Bob",
});

const bot = make_bot({
    email: "bot@example.com",
    user_id: 33,
    full_name: "Bot",
});

people.add_active_user(new_user);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(bot);

const social = make_stream({
    stream_id: 101,
    name: "social",
    subscribed: true,
    can_send_message_group: 2,
    topics_policy: "inherit",
});
stream_data.add_sub_for_tests(social);

const nobody = make_user_group({
    name: "role:nobody",
    id: 1,
    members: new Set(),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});
const everyone = make_user_group({
    name: "role:everyone",
    id: 2,
    members: new Set([30, 101]),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});

user_groups.initialize({realm_user_groups: [nobody, everyone]});

function test_ui(label, f) {
    // TODO: initialize data more aggressively.
    run_test(label, f);
}

function initialize_handlers({override}) {
    override(realm, "realm_available_video_chat_providers", {disabled: {id: 0}});
    override(realm, "realm_video_chat_provider", 0);
    override(resize, "watch_manual_resize", noop);
    disable_window_triggers(override);
    compose_setup.initialize();
}

function disable_window_triggers(override) {
    override(window, "to_$", () => $("window-stub"));
}

function simulate_draft_ui_interactions() {
    // Simulate DOM relationships so that code can execute,
    // but we won't actually examine these values.
    $(".top_left_drafts").set_find_results(".unread_count", $.create("draft-unread-count-stub"));
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
    override(draft_model, "deleteDrafts", (draft_ids) => {
        assert.deepEqual(draft_ids, [100]);
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

test_ui(
    "send_message_success_partial_visibility_policy",
    ({override, override_rewire, disallow}) => {
        override_rewire(echo, "reify_message_id", noop);
        override(
            onboarding_steps,
            "ONE_TIME_NOTICES_TO_DISPLAY",
            new Set(["visibility_policy_banner"]),
        );
        disallow(drafts.draft_model, "deleteDrafts");

        let notified = false;
        override(
            compose_notifications,
            "notify_automatic_new_visibility_policy",
            (_message, data) => {
                notified = true;
                assert.equal(data.automatic_new_visibility_policy, 2);
            },
        );

        const request = {
            locally_echoed: false,
            local_id: "loc-split-1",
            draft_id: 100,
            type: "stream",
            stream_id: 1,
            topic: "test",
        };
        compose.send_message_success(request, {id: 12, automatic_new_visibility_policy: 2}, true);
        assert.ok(notified);
    },
);

test_ui("send_message", ({override, override_rewire, mock_template}) => {
    mock_banners();
    clock.setSystemTime(new Date(fake_now * 1000));

    const fake_compose_box = new FakeComposeBox();

    // Draft UI side-effects are out of the scope of this test,
    // but we need the code to not fail.
    // TODO: probably mock at a higher level.
    simulate_draft_ui_interactions();

    // This is the common setup stuff for all of the four tests.
    let stub_state;
    function initialize_state_stub_dict() {
        stub_state = {
            send_msg_called: 0,
            get_events_running_called: 0,
            reify_message_id_checked: 0,
        };
        return stub_state;
    }

    override_rewire(drafts, "update_compose_draft_count", noop);

    override(server_events_state, "assert_get_events_running", () => {
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
        override(compose_pm_pill, "get_user_ids", () => [alice.user_id]);

        const server_message_id = 127;
        override(markdown, "render", noop);
        override(markdown, "get_topic_links", () => []);

        override_rewire(echo, "try_deliver_locally", (message_request) => {
            const local_id_float = 123.04;
            return echo.insert_local_message(message_request, local_id_float, (messages_data) => {
                assert.equal(messages_data.type, "local_message");
                assert.equal(messages_data.raw_messages[0].timestamp, fake_now);
                return messages_data.raw_messages;
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

test_ui("split_message_send_multi_part", ({override, override_rewire, disallow_rewire}) => {
    mock_banners();
    clock.setSystemTime(new Date(fake_now * 1000));
    simulate_draft_ui_interactions();

    const fake_compose_box = new FakeComposeBox();

    let update_draft_count = 0;
    override_rewire(drafts, "update_draft", () => {
        update_draft_count += 1;
        return 100;
    });
    const deleted_draft_ids = [];
    override(drafts.draft_model, "deleteDrafts", (ids) => deleted_draft_ids.push(...ids));
    override(server_events_state, "assert_get_events_running", noop);
    override_rewire(echo, "reify_message_id", noop);
    disallow_rewire(echo, "try_deliver_locally");
    override(sent_messages, "get_new_local_id", () => "loc-split-1");
    override(compose_notifications, "get_muted_narrow", () => undefined);

    compose_split_messages.set_split_messages_enabled(true);

    compose_state.set_message_type("stream");
    compose_state.set_stream_id(social.stream_id);
    override(current_user, "user_id", new_user.user_id);

    const sent_contents = [];
    override(transmit, "send_message", (payload, success) => {
        sent_contents.push(payload.content);
        if (sent_contents.length === 1) {
            // Success fires synchronously — compose box must still be intact
            // between parts, not cleared until the final part lands, and it's
            // read-only so edits mid-send can't be silently discarded.
            assert.ok(fake_compose_box.textarea_val() !== "");
            assert.ok(fake_compose_box.is_textarea_readonly());
        }
        success({id: sent_contents.length * 100});
    });

    fake_compose_box.set_textarea_val("part1\n\n\npart2");
    compose.send_message();

    assert.deepEqual(sent_contents, ["part1", "part2"]);
    assert.equal(fake_compose_box.textarea_val(), "");
    // The box is editable again once the final part clears it.
    assert.ok(!fake_compose_box.is_textarea_readonly());
    assert.equal(update_draft_count, 1);
    assert.deepEqual(deleted_draft_ids, [100]);

    compose_split_messages.set_split_messages_enabled(false);
});

test_ui(
    "split_message_send_rewrites_draft_to_remainder",
    ({override, override_rewire, disallow_rewire}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        override_rewire(drafts, "update_draft", () => 100);
        // The in-flight draft starts life holding the full, unsplit message.
        const stored_draft = {content: "part1\n\n\npart2\n\n\npart3", is_sending_saving: true};
        override(drafts.draft_model, "getDraft", () => stored_draft);
        const draft_content_after_edit = [];
        override(drafts.draft_model, "editDraft", (_id, draft) => {
            draft_content_after_edit.push(draft.content);
            return true;
        });
        const deleted_draft_ids = [];
        override(drafts.draft_model, "deleteDrafts", (ids) => deleted_draft_ids.push(...ids));
        override(server_events_state, "assert_get_events_running", noop);
        override_rewire(echo, "reify_message_id", noop);
        disallow_rewire(echo, "try_deliver_locally");
        override(sent_messages, "get_new_local_id", () => "loc-split-3");
        override(compose_notifications, "get_muted_narrow", () => undefined);

        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);
        override(current_user, "user_id", new_user.user_id);

        override(transmit, "send_message", (_payload, success) => {
            success({id: 100});
        });

        fake_compose_box.set_textarea_val("part1\n\n\npart2\n\n\npart3");
        compose.send_message();

        // As each part is delivered, the draft is rewritten to only the still-unsent
        // remainder, so a reload mid-split can't re-send already-delivered parts.
        // The final part deletes the draft entirely.
        assert.deepEqual(draft_content_after_edit, ["part2\n\n\npart3", "part3"]);
        assert.deepEqual(deleted_draft_ids, [100]);

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui(
    "split_message_send_error_recovery",
    ({override, override_rewire, disallow, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        const update_draft_opts = [];
        override_rewire(drafts, "update_draft", (opts = {}) => {
            update_draft_opts.push(opts);
            return 100;
        });
        disallow(drafts.draft_model, "deleteDrafts");
        override(server_events_state, "assert_get_events_running", noop);
        override_rewire(echo, "reify_message_id", noop);
        override(sent_messages, "get_new_local_id", () => "loc-split-2");
        override_rewire(compose_ui, "autosize_textarea", noop);

        compose_split_messages.set_split_messages_enabled(true);

        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);
        override(current_user, "user_id", new_user.user_id);

        let send_call_count = 0;
        override(transmit, "send_message", (_payload, success, error) => {
            send_call_count += 1;
            if (send_call_count === 1) {
                success({id: 101});
            } else {
                error("Server error", "");
            }
        });

        let partial_failure_banner_shown = false;
        mock_template("compose_banner/compose_banner.hbs", false, (data) => {
            if (data.classname === compose_banner_module.CLASSNAMES.generic_compose_error) {
                partial_failure_banner_shown = true;
            }
            return "<banner-stub>";
        });

        fake_compose_box.set_textarea_val("part1\n\n\npart2\n\n\npart3");
        compose.send_message();

        assert.equal(send_call_count, 2);
        // Must report exactly 1 shipped part — not 0 (unfired) or 2 (both failed).
        assert.ok(partial_failure_banner_shown);
        // Part 1 is gone; only unsent content restored to the box.
        assert.equal(fake_compose_box.textarea_val(), "part2\n\n\npart3");
        assert.equal(update_draft_opts.at(-1).is_sending_saving, false);

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui("split_message_send_recipient_race", ({override, override_rewire, disallow_rewire}) => {
    mock_banners();
    clock.setSystemTime(new Date(fake_now * 1000));
    simulate_draft_ui_interactions();

    const fake_compose_box = new FakeComposeBox();

    override_rewire(drafts, "update_draft", () => 100);
    override(drafts.draft_model, "deleteDrafts", noop);
    override(server_events_state, "assert_get_events_running", noop);
    override_rewire(echo, "reify_message_id", noop);
    disallow_rewire(echo, "try_deliver_locally");
    override(sent_messages, "get_new_local_id", () => "loc-split-3");
    override(compose_notifications, "get_muted_narrow", () => undefined);

    compose_split_messages.set_split_messages_enabled(true);

    const original_stream_id = social.stream_id;
    const original_topic = "original-topic";
    const different_stream_id = 999;

    compose_state.set_message_type("stream");
    compose_state.set_stream_id(original_stream_id);
    $("input#stream_message_recipient_topic").val(original_topic);
    override(current_user, "user_id", new_user.user_id);

    const sent_stream_ids = [];
    const sent_topics = [];

    override(transmit, "send_message", (payload, success) => {
        sent_stream_ids.push(payload.stream_id);
        sent_topics.push(payload.topic);

        if (sent_stream_ids.length === 1) {
            // Change recipient mid-flight — part 2 must ignore this and use
            // the captured recipient from the start of send_message().
            compose_state.set_stream_id(different_stream_id);
            $("input#stream_message_recipient_topic").val("different-topic");
        }

        success({id: sent_stream_ids.length * 100});
    });

    fake_compose_box.set_textarea_val("part1\n\n\npart2");
    compose.send_message();

    assert.equal(sent_stream_ids[0], original_stream_id);
    assert.equal(sent_stream_ids[1], original_stream_id);
    assert.equal(sent_topics[0], original_topic);
    assert.equal(sent_topics[1], original_topic);
    // Confirm the race actually happened — state really did change mid-flight.
    assert.equal(compose_state.stream_id(), different_stream_id);

    // Restore so we don't pollute subsequent tests.
    compose_state.set_stream_id(social.stream_id);
    $("input#stream_message_recipient_topic").val("");
    compose_split_messages.set_split_messages_enabled(false);
});

test_ui(
    "split_message_send_refuses_too_many_parts",
    ({disallow, disallow_rewire, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        disallow_rewire(echo, "try_deliver_locally");
        // The refusal happens before the draft is saved or anything is
        // dispatched to the server, so neither may be reached.
        disallow(transmit, "send_message");
        mock_template("compose_banner/compose_banner.hbs", false, () => "<banner-stub>");

        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);

        const parts = [];
        for (let i = 0; i <= compose_split_messages.MAX_SPLIT_PARTS; i += 1) {
            parts.push(`p${i}`);
        }
        fake_compose_box.set_textarea_val(parts.join("\n\n\n"));

        // Too many parts: send_message refuses before dispatching and returns
        // false, so finish() returns false and skips its post-send side effects.
        const dispatched = compose.send_message();

        assert.equal(dispatched, false);

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui(
    "schedule_split_message_multi_part",
    ({override, override_rewire, disallow_rewire, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        let update_draft_count = 0;
        override_rewire(drafts, "update_draft", () => {
            update_draft_count += 1;
            return 100;
        });
        const deleted_draft_ids = [];
        override(drafts.draft_model, "deleteDrafts", (ids) => deleted_draft_ids.push(...ids));
        disallow_rewire(echo, "try_deliver_locally");
        mock_template(
            "compose_banner/success_split_messages_scheduled_banner.hbs",
            false,
            () => "<banner-stub>",
        );

        const base_ts = fake_now + 600;
        scheduled_messages.set_selected_schedule_timestamp(base_ts);

        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);

        const posted = [];
        override(channel, "post", (payload) => {
            assert.equal(payload.url, "/json/scheduled_messages");
            posted.push(payload.data);
            if (posted.length === 1) {
                // The box stays intact and read-only between parts, until the
                // final part clears it.
                assert.ok(fake_compose_box.textarea_val() !== "");
                assert.ok(fake_compose_box.is_textarea_readonly());
            }
            payload.success({scheduled_message_id: posted.length});
        });

        fake_compose_box.set_textarea_val("part1\n\n\npart2\n\n\npart3");
        const scheduled = compose.schedule_message_to_custom_date();

        assert.ok(scheduled);
        assert.deepEqual(
            posted.map((data) => data.content),
            ["part1", "part2", "part3"],
        );
        // All parts share one timestamp; delivery order is guaranteed by the
        // ascending scheduled-message ids that sequential posting produces.
        assert.deepEqual(
            posted.map((data) => data.scheduled_delivery_timestamp),
            [base_ts, base_ts, base_ts],
        );
        assert.equal(update_draft_count, 1);
        assert.deepEqual(deleted_draft_ids, [100]);
        assert.equal(fake_compose_box.textarea_val(), "");
        assert.ok(!fake_compose_box.is_textarea_readonly());

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui(
    "schedule_split_message_rewrites_draft_to_remainder",
    ({override, override_rewire, disallow_rewire, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        override_rewire(drafts, "update_draft", () => 100);
        const stored_draft = {content: "part1\n\n\npart2\n\n\npart3", is_sending_saving: true};
        override(drafts.draft_model, "getDraft", () => stored_draft);
        const draft_content_after_edit = [];
        override(drafts.draft_model, "editDraft", (_id, draft) => {
            draft_content_after_edit.push(draft.content);
            return true;
        });
        const deleted_draft_ids = [];
        override(drafts.draft_model, "deleteDrafts", (ids) => deleted_draft_ids.push(...ids));
        disallow_rewire(echo, "try_deliver_locally");
        mock_template(
            "compose_banner/success_split_messages_scheduled_banner.hbs",
            false,
            () => "<banner-stub>",
        );

        scheduled_messages.set_selected_schedule_timestamp(fake_now + 600);
        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);

        override(channel, "post", (payload) => payload.success({scheduled_message_id: 1}));

        fake_compose_box.set_textarea_val("part1\n\n\npart2\n\n\npart3");
        compose.schedule_message_to_custom_date();

        // Each scheduled part rewrites the draft to only the still-unscheduled
        // remainder; the final part deletes it.
        assert.deepEqual(draft_content_after_edit, ["part2\n\n\npart3", "part3"]);
        assert.deepEqual(deleted_draft_ids, [100]);

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui(
    "schedule_split_message_error_recovery",
    ({override, override_rewire, disallow, disallow_rewire, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        const update_draft_opts = [];
        override_rewire(drafts, "update_draft", (opts = {}) => {
            update_draft_opts.push(opts);
            return 100;
        });
        disallow(drafts.draft_model, "deleteDrafts");
        disallow_rewire(echo, "try_deliver_locally");
        override_rewire(compose_ui, "autosize_textarea", noop);
        override(channel, "xhr_error_message", () => "translated: Error");

        scheduled_messages.set_selected_schedule_timestamp(fake_now + 600);
        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);

        let post_count = 0;
        override(channel, "post", (payload) => {
            post_count += 1;
            if (post_count === 1) {
                payload.success({scheduled_message_id: 1});
            } else {
                payload.error({});
            }
        });

        const banner_texts = [];
        mock_template("compose_banner/compose_banner.hbs", false, (data) => {
            if (data.classname === compose_banner_module.CLASSNAMES.generic_compose_error) {
                banner_texts.push(data.banner_text);
            }
            return "<banner-stub>";
        });

        fake_compose_box.set_textarea_val("part1\n\n\npart2\n\n\npart3");
        compose.schedule_message_to_custom_date();

        assert.equal(post_count, 2);
        // Part 1 is scheduled; only the unscheduled remainder is restored.
        assert.equal(fake_compose_box.textarea_val(), "part2\n\n\npart3");
        assert.equal(update_draft_opts.at(-1).is_sending_saving, false);
        // The partial-schedule-failure banner reports the one shipped part.
        assert.ok(banner_texts.some((text) => text.includes("already scheduled")));

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui(
    "schedule_split_message_refuses_too_many_parts",
    ({disallow, disallow_rewire, mock_template}) => {
        mock_banners();
        clock.setSystemTime(new Date(fake_now * 1000));
        simulate_draft_ui_interactions();

        const fake_compose_box = new FakeComposeBox();

        disallow_rewire(echo, "try_deliver_locally");
        // Too many parts must be refused before anything is scheduled.
        disallow(channel, "post");
        mock_template("compose_banner/compose_banner.hbs", false, () => "<banner-stub>");

        scheduled_messages.set_selected_schedule_timestamp(fake_now + 600);
        compose_split_messages.set_split_messages_enabled(true);
        compose_state.set_message_type("stream");
        compose_state.set_stream_id(social.stream_id);

        const parts = [];
        for (let i = 0; i <= compose_split_messages.MAX_SPLIT_PARTS; i += 1) {
            parts.push(`p${i}`);
        }
        fake_compose_box.set_textarea_val(parts.join("\n\n\n"));

        const scheduled = compose.schedule_message_to_custom_date();

        assert.equal(scheduled, false);

        compose_split_messages.set_split_messages_enabled(false);
    },
);

test_ui("schedule_single_message_unchanged", ({override, override_rewire, mock_template}) => {
    mock_banners();
    clock.setSystemTime(new Date(fake_now * 1000));
    simulate_draft_ui_interactions();

    const fake_compose_box = new FakeComposeBox();

    override_rewire(drafts, "update_draft", () => 100);
    const deleted_draft_ids = [];
    override(drafts.draft_model, "deleteDrafts", (ids) => deleted_draft_ids.push(...ids));
    let banner_context;
    mock_template("compose_banner/success_message_scheduled_banner.hbs", false, (data) => {
        banner_context = data;
        return "<banner-stub>";
    });

    scheduled_messages.set_selected_schedule_timestamp(fake_now + 600);
    // Splitting disabled: a single scheduled message, keeping the existing
    // Undo banner.
    compose_state.set_message_type("stream");
    compose_state.set_stream_id(social.stream_id);

    const posted = [];
    override(channel, "post", (payload) => {
        posted.push(payload.data);
        payload.success({scheduled_message_id: 77});
    });

    fake_compose_box.set_textarea_val("just one message");
    const scheduled = compose.schedule_message_to_custom_date();

    assert.ok(scheduled);
    assert.equal(posted.length, 1);
    assert.equal(posted[0].content, "just one message");
    assert.equal(banner_context.scheduled_message_id, 77);
    assert.deepEqual(deleted_draft_ids, [100]);
    assert.equal(fake_compose_box.textarea_val(), "");
});

test_ui("split_message_preview_enumerated", ({override, mock_template}) => {
    mock_banners();
    initialize_handlers({override});

    const fake_compose_box = new FakeComposeBox();

    compose_split_messages.set_split_messages_enabled(true);

    // All parts are plain text: rendered locally, enumerated as Message N.
    override(markdown, "contains_backend_only_syntax", () => false);
    override(markdown, "is_status_message", () => false);
    override(markdown, "render", (raw_content) => ({content: "R:" + raw_content}));

    // Capture each enumerated part instead of asserting on accumulated DOM.
    const enumerated_calls = [];
    mock_template("enumerated_split_message_part.hbs", false, (data) => {
        enumerated_calls.push({
            message_number: data.message_number,
            rendered_preview_html: data.rendered_preview_html,
        });
        return `<div class="split_message_fragment">${data.rendered_preview_html}</div>`;
    });

    // Each part also fires a server render; leave it unresolved so we test
    // the synchronous local-render path. The async rebuild never runs.
    override(channel, "post", () => {});

    fake_compose_box.set_textarea_val("part1\n\n\npart2");
    fake_compose_box.hide_message_preview();

    fake_compose_box.click_on_markdown_preview_icon({
        preventDefault: noop,
        stopPropagation: noop,
    });

    fake_compose_box.assert_preview_mode_is_on();

    // Two parts, enumerated 1 and 2, each carrying its locally-rendered content.
    assert.equal(enumerated_calls.length, 2);
    assert.equal(enumerated_calls[0].message_number, 1);
    assert.equal(enumerated_calls[0].rendered_preview_html, "R:part1");
    assert.equal(enumerated_calls[1].message_number, 2);
    assert.equal(enumerated_calls[1].rendered_preview_html, "R:part2");

    compose_split_messages.set_split_messages_enabled(false);
});

test_ui("handle_enter_key_with_preview_open", ({override, override_rewire}) => {
    mock_banners();
    window.addEventListener = noop;

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
        return true;
    });
    override(realm, "realm_topics_policy", "allow_empty_topic");

    compose.handle_enter_key_with_preview_open();
    // Preview mode should remain on after finish() returns, because
    // clear_preview_area() is now called inside clear_compose_box(),
    // which only runs when the server confirms the send.
    fake_compose_box.assert_preview_mode_is_on();

    assert.ok(send_message_called);
    assert.ok(show_button_spinner_called);

    // Verify that preview mode is cleared when the compose box is
    // cleared, as would happen asynchronously on send success.
    compose.clear_compose_box();
    fake_compose_box.assert_preview_mode_is_off();

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

    const fake_compose_box = new FakeComposeBox();

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

        assert.ok(!fake_compose_box.$content_textarea.hasClass("invalid"));
        fake_compose_box.set_textarea_val("");

        override_rewire(compose_ui, "compose_spinner_visible", false);
        const res = compose.finish();
        assert.equal(res, false);

        assert.ok(fake_compose_box.$content_textarea.hasClass("invalid"));
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
        override(compose_pm_pill, "get_user_ids", () => [bob.user_id]);
        override(realm, "realm_direct_message_permission_group", everyone.id);
        override(realm, "realm_direct_message_initiator_group", everyone.id);

        let send_message_called = false;
        override_rewire(compose, "send_message", () => {
            send_message_called = true;
            return true;
        });

        assert.ok(compose.finish());

        // Preview mode should remain on after finish() returns, because
        // clear_preview_area() is now called inside clear_compose_box(),
        // which only runs when the server confirms the send.
        fake_compose_box.assert_preview_mode_is_on();
        assert.ok(send_message_called);

        // Verify that preview mode is cleared when the compose box is
        // cleared, as would happen asynchronously on send success.
        compose.clear_compose_box();
        fake_compose_box.assert_preview_mode_is_off();
    })();
});

test_ui("initialize", ({override}) => {
    disable_window_triggers(override);

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

        assert.ok(uppy_cancel_all_called);
    })();
});

test_ui("update_draft_if_composing", ({override_rewire}) => {
    let update_draft_call_count = 0;
    override_rewire(drafts, "update_draft", (opts) => {
        assert.deepEqual(opts, {no_notify: true});
        update_draft_call_count += 1;
        return "draft-id";
    });

    // Autosave does nothing once the compose box has closed, so a
    // delayed call can't resurrect a draft the user is done with.
    compose_state.set_message_type(undefined);
    assert.ok(!compose_state.composing());
    compose_setup.update_draft_if_composing();
    assert.equal(update_draft_call_count, 0);

    // While the user is still composing, autosave persists the draft.
    compose_state.set_message_type("stream");
    assert.ok(compose_state.composing());
    compose_setup.update_draft_if_composing();
    assert.equal(update_draft_call_count, 1);
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
        $("#compose .preview_content").set_find_results(
            ".image-loading-placeholder",
            $.create("no-images", {elements: []}),
        );

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

        let current_message;

        override(channel, "post", (payload) => {
            assert.equal(payload.url, "/json/messages/render");
            assert.ok(payload.data);
            assert.deepEqual(payload.data.content, current_message);

            payload.error();
        });

        // Tests start here
        fake_compose_box.set_textarea_val("");
        fake_compose_box.hide_message_preview();

        fake_compose_box.click_on_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.equal(fake_compose_box.preview_content_html(), "translated: Nothing to preview");
        fake_compose_box.assert_preview_mode_is_on();

        let make_indicator_called = false;

        fake_compose_box.set_textarea_val("```default message```");
        fake_compose_box.hide_message_preview();
        setup_mock_markdown_contains_backend_only_syntax("```default message```", true);

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
            return {content: "Local: default message"};
        });

        fake_compose_box.click_on_markdown_preview_icon({
            preventDefault: noop,
            stopPropagation: noop,
        });

        assert.ok(render_called);
        fake_compose_box.assert_preview_mode_is_on();
        assert.equal(fake_compose_box.preview_content_html(), "Local: default message");
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

test_ui("DM policy disabled", ({override}) => {
    // Disable sending direct messages in the organisation
    override(realm, "realm_direct_message_permission_group", nobody.id);
    override(realm, "realm_direct_message_initiator_group", everyone.id);
    // For single bot recipient, Bot, the "Message X" button is not disabled
    let reply_disabled =
        compose_closed_ui.should_disable_compose_reply_button_for_direct_message("33");
    assert.ok(!reply_disabled);
    // For human user, Alice, the "Message X" button is disabled
    reply_disabled = compose_closed_ui.should_disable_compose_reply_button_for_direct_message("31");
    assert.ok(reply_disabled);
    // For human user and bot user, the "Message X" button is disabled
    reply_disabled =
        compose_closed_ui.should_disable_compose_reply_button_for_direct_message("31,33");
    assert.ok(reply_disabled);
});
