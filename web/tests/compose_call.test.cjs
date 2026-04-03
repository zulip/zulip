"use strict";

const assert = require("node:assert/strict");

const events = require("./lib/events.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
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

const realm = make_realm();
set_realm(realm);
const current_user = {};
set_current_user(current_user);

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
    constructor_groups: {
        id: 6,
        name: "Constructor Groups",
    },
    nextcloud_talk: {
        id: 7,
        name: "Nextcloud Talk",
    },
    webex: {
        id: 8,
        name: "Webex",
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
    override(window, "to_$", () => $("window-stub"));

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
        handler.call($textarea, ev);
        // video link ids consist of 15 random digits
        let video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/server.example.com\/\d{15}#config.startWithVideoMuted=false\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        override(realm, "realm_jitsi_server_url", "https://realm.example.com");
        override(realm, "server_jitsi_server_url", null);
        handler.call($textarea, ev);
        video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/realm.example.com\/\d{15}#config.startWithVideoMuted=false\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        override(realm, "realm_jitsi_server_url", "https://realm.example.com");
        override(realm, "server_jitsi_server_url", "https://server.example.com");
        handler.call($textarea, ev);
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
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
            success_callback = undefined;
        });

        override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.zoom.id);
        override(current_user, "has_zoom_token", false);

        window.open = (url) => {
            assert.ok(url.endsWith("/calls/zoom/register"));

            // The event here has value=true.  We keep it in events.js to
            // allow our tooling to verify its schema.
            server_events_dispatch.dispatch_normal_event(events.fixtures.has_zoom_token);
        };

        let success_callback;
        const xhr_object = {abort() {}};
        channel.post = (payload) => {
            assert.equal(payload.url, "/json/calls/zoom/create");
            success_callback = payload.success;
            return xhr_object;
        };

        function call_success_callback() {
            assert.ok(success_callback !== undefined);
            success_callback({
                result: "success",
                msg: "",
                url: "example.zoom.com",
            });
        }

        $("textarea#compose-textarea").val("");
        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler.call($textarea, ev);
        call_success_callback();
        const video_link_regex = /\[translated: Join video call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        $("textarea#compose-textarea").val("");
        const audio_handler = $("body").get_on_handler("click", ".audio_link");
        audio_handler.call($textarea, ev);
        call_success_callback();
        const audio_link_regex = /\[translated: Join voice call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, audio_link_regex);
    })();

    (function test_webex_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("webex-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
            success_callback = undefined;
        });

        override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.webex.id);
        override(current_user, "has_webex_token", false);

        window.open = (url) => {
            assert.ok(url.endsWith("/calls/webex/register"));

            // The event here has value=true.  We keep it in events.js to
            // allow our tooling to verify its schema.
            server_events_dispatch.dispatch_normal_event(events.fixtures.has_webex_token);
        };

        let success_callback;
        const xhr_object = {abort() {}};
        channel.post = (payload) => {
            assert.equal(payload.url, "/json/calls/webex/create");
            success_callback = payload.success;
            return xhr_object;
        };

        function call_success_callback() {
            assert.ok(success_callback !== undefined);
            success_callback({
                result: "success",
                msg: "",
                url: "example.webex.com",
            });
        }

        $("textarea#compose-textarea").val("");
        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler.call($textarea, ev);
        call_success_callback();
        const video_link_regex = /\[translated: Join video call\.]\(example\.webex\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_bbb_audio_and_video_links_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("bbb-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
            success_callback = undefined;
            url = undefined;
        });

        $("textarea#compose-textarea").val("");

        override(
            realm,
            "realm_video_chat_provider",
            realm_available_video_chat_providers.big_blue_button.id,
        );

        override(compose_closed_ui, "get_recipient_label", () => ({label_text: "a"}));

        let success_callback;
        const xhr_object = {abort() {}};
        let url;
        channel.get = (options) => {
            assert.equal(options.url, "/json/calls/bigbluebutton/create");
            assert.equal(options.data.meeting_name, "a meeting");
            success_callback = options.success;
            url =
                "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=" +
                options.data.voice_only +
                "&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22";
            return xhr_object;
        };

        function call_success_callback() {
            assert.ok(success_callback !== undefined);
            success_callback({
                result: "success",
                msg: "",
                url,
            });
        }

        $("textarea#compose-textarea").val("");

        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler.call($textarea, ev);
        call_success_callback();
        const video_link_regex =
            /\[translated: Join video call\.]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=false&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        const audio_handler = $("body").get_on_handler("click", ".audio_link");
        audio_handler.call($textarea, ev);
        call_success_callback();
        const audio_link_regex =
            /\[translated: Join voice call\.]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&moderator=%22AAAAAAAAAA%22&lock_settings_disable_cam=true&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, audio_link_regex);
    })();

    (function test_constructor_groups_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("constructor-groups-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
            success_callback = undefined;
        });

        override(
            realm,
            "realm_video_chat_provider",
            realm_available_video_chat_providers.constructor_groups.id,
        );

        let success_callback;
        function call_success_callback() {
            success_callback({
                result: "success",
                msg: "",
                url: "https://example.constructor.app/groups/room/room-123",
            });
        }

        channel.post = (payload) => {
            assert.equal(payload.url, "/json/calls/constructorgroups/create");
            assert.deepEqual(payload.data, {}); // Empty data object
            success_callback = payload.success;
            return {abort() {}};
        };

        $("textarea#compose-textarea").val("");
        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler.call($textarea, ev);
        call_success_callback();
        const video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/example\.constructor\.app\/groups\/room\/room-123\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_nextcloud_talk_audio_and_video_links_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const $textarea = $.create("nextcloud-target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        override(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
            success_callback = undefined;
        });

        $("textarea#compose-textarea").val("");

        override(
            realm,
            "realm_video_chat_provider",
            realm_available_video_chat_providers.nextcloud_talk.id,
        );

        override(compose_closed_ui, "get_recipient_label", () => ({label_text: "general"}));
        let success_callback;
        function call_success_callback() {
            assert.ok(success_callback !== undefined);
            success_callback({
                result: "success",
                msg: "",
                url: "https://nextcloud.example.com/index.php/call/abc123token",
            });
        }

        const xhr_object = {abort() {}};
        channel.post = (options) => {
            assert.equal(options.url, "/json/calls/nextcloud_talk/create");
            assert.equal(options.data.room_name, "general conversation");
            success_callback = options.success;
            return xhr_object;
        };

        $("textarea#compose-textarea").val("");

        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler.call($textarea, ev);
        call_success_callback();
        const video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/nextcloud\.example\.com\/index\.php\/call\/abc123token\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();
});

test("test_video_chat_button_toggle disabled", ({override}) => {
    override(realm, "realm_video_chat_provider", realm_available_video_chat_providers.disabled.id);
    override(window, "to_$", () => $("window-stub"));
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), false);
});

test("test_video_chat_button_toggle no url", ({override}) => {
    override(
        realm,
        "realm_video_chat_provider",
        realm_available_video_chat_providers.jitsi_meet.id,
    );
    override(window, "to_$", () => $("window-stub"));
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
    override(window, "to_$", () => $("window-stub"));
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), true);
});

test("test_constructor_groups_video_chat_button_toggle enabled", ({override}) => {
    override(
        realm,
        "realm_video_chat_provider",
        realm_available_video_chat_providers.constructor_groups.id,
    );
    override(window, "to_$", () => $("window-stub"));
    compose_setup.initialize();
    assert.equal($(".compose-control-buttons-container .video_link").visible(), true);
});
