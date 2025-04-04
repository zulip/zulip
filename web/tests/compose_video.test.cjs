"use strict";

const assert = require("node:assert/strict");

const events = require("./lib/events.cjs");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const channel = mock_esm("../src/channel");
const compose_closed_ui = mock_esm("../src/compose_closed_ui");
const compose_ui = mock_esm("../src/compose_ui");
mock_esm("../src/resize", {
    watch_manual_resize() {},
});
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

const server_events_dispatch = zrequire("server_events_dispatch");
const compose_setup = zrequire("compose_setup");
const {set_current_user, set_realm} = zrequire("state_data");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);

function stub_out_video_calls() {
    const $elem = $(".compose-control-buttons-container .video_link");
    $elem.toggle = (show) => {
        /* istanbul ignore if */
        if (show) {
            $elem.show();
        } else {
            $elem.hide();
        }
    };
}

const realm_available_video_chat_providers = {
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
        name: "BigBlueButton",
    },
};

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(
            realm,
            "realm_available_video_chat_providers",
            realm_available_video_chat_providers,
        );
        f(helpers);
    });
}

test("videos", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.disabled.id);

    stub_out_video_calls();

    compose_setup.initialize();

    (function test_no_provider_video_link_compose_clicked() {
        const $textarea = $.create("target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("textarea#compose-textarea").val("");

        with_overrides(({disallow}) => {
            disallow(compose_ui, "insert_syntax_and_focus");
            handler(ev);
        });
    })();

    (function test_jitsi_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("jitsi-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
            target: {
                to_$: () => $textarea,
            },
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
        });

        const handler = $("body").get_on_handler("click", ".video_link");
        $("textarea#compose-textarea").val("");

        override(
            realm,
            "realm_video_chat_provider",
            realm_available_video_chat_providers.jitsi_meet.id,
        );

        override(realm, "realm_jitsi_server_url", null);
        override(realm, "server_jitsi_server_url", null);
        handler(ev);
        assert.ok(!called);

        override(realm, "realm_jitsi_server_url", null);
        override(realm, "server_jitsi_server_url", "https://server.example.com");
        handler(ev);
        // video link ids consist of 15 random digits
        let video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/server.example.com\/\d{15}#config.startWithVideoMuted=false\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        override(realm, "realm_jitsi_server_url", "https://realm.example.com");
        override(realm, "server_jitsi_server_url", null);
        handler(ev);
        video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/realm.example.com\/\d{15}#config.startWithVideoMuted=false\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        override(realm, "realm_jitsi_server_url", "https://realm.example.com");
        override(realm, "server_jitsi_server_url", "https://server.example.com");
        handler(ev);
        video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/realm.example.com\/\d{15}#config.startWithVideoMuted=false\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_zoom_video_and_audio_links_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("zoom-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
            target: {
                to_$: () => $textarea,
            },
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
        });

        override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.zoom.id);
        override(current_user, "has_zoom_token", false);

        window.open = (url) => {
            assert.ok(url.endsWith("/calls/zoom/register"));

            // The event here has value=true.  We keep it in events.js to
            // allow our tooling to verify its schema.
            server_events_dispatch.dispatch_normal_event(events.fixtures.has_zoom_token);
        };

        channel.post = (payload) => {
            assert.equal(payload.url, "/json/calls/zoom/create");
            payload.success({
                result: "success",
                msg: "",
                url: "example.zoom.com",
            });
            return {abort() {}};
        };

        $("textarea#compose-textarea").val("");
        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler(ev);
        const video_link_regex = /\[translated: Join video call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        $("textarea#compose-textarea").val("");
        const audio_handler = $("body").get_on_handler("click", ".audio_link");
        audio_handler(ev);
        const audio_link_regex = /\[translated: Join voice call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, audio_link_regex);
    })();

    (function test_bbb_audio_and_video_links_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("bbb-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
            target: {
                to_$: () => $textarea,
            },
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
        });

        $("textarea#compose-textarea").val("");

        override(
            realm,
            "realm_video_chat_provider",
            realm_available_video_chat_providers.big_blue_button.id,
        );

        override(compose_closed_ui, "get_recipient_label", () => ({label_text: "a"}));

        channel.get = (options) => {
            assert.equal(options.url, "/json/calls/bigbluebutton/create");
            assert.equal(options.data.meeting_name, "a meeting");
            options.success({
                result: "success",
                msg: "",
                url:
                    "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=" +
                    options.data.voice_only +
                    "&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22",
            });
        };

        $("textarea#compose-textarea").val("");

        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler(ev);
        const video_link_regex =
            /\[translated: Join video call\.]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=false&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        const audio_handler = $("body").get_on_handler("click", ".audio_link");
        audio_handler(ev);
        const audio_link_regex =
            /\[translated: Join voice call\.]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=true&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, audio_link_regex);
    })();
});

test("test_video_chat_button_toggle disabled", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.disabled.id);
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), false);
});

test("test_video_chat_button_toggle no url", ({override}) => {
    override(
        realm,
        "realm_video_chat_provider",
        realm_available_video_chat_providers.jitsi_meet.id,
    );
    page_params.jitsi_server_url = null;
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), false);
});

test("test_video_chat_button_toggle enabled", ({override}) => {
    override(
        realm,
        "realm_video_chat_provider",
        realm_available_video_chat_providers.jitsi_meet.id,
    );
    override(realm, "realm_jitsi_server_url", "https://meet.jit.si");
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), true);
});
