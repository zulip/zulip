"use strict";

const {strict: assert} = require("assert");

const events = require("./lib/events");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const channel = mock_esm("../src/channel");
const compose_closed_ui = mock_esm("../src/compose_closed_ui");
const compose_ui = mock_esm("../src/compose_ui");
const upload = mock_esm("../src/upload");
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
const compose = zrequire("compose");
function stub_out_video_calls() {
    const $elem = $("#below-compose-content .video_link");
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
        page_params.realm_available_video_chat_providers = realm_available_video_chat_providers;
        f(helpers);
    });
}

test("videos", ({override}) => {
    page_params.realm_video_chat_provider = realm_available_video_chat_providers.disabled.id;

    override(upload, "setup_upload", () => {});
    override(upload, "feature_check", () => {});

    stub_out_video_calls();

    compose.initialize();

    (function test_no_provider_video_link_compose_clicked() {
        const $textarea = $.create("target-stub");
        $textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault() {},
            stopPropagation() {},
        };

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

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
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider = realm_available_video_chat_providers.jitsi_meet.id;

        page_params.jitsi_server_url = null;
        handler(ev);
        assert.ok(!called);

        page_params.jitsi_server_url = "https://meet.jit.si";
        handler(ev);
        // video link ids consist of 15 random digits
        const video_link_regex =
            /\[translated: Join video call\.]\(https:\/\/meet.jit.si\/\d{15}#config.startWithVideoMuted=false\)/;
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

        page_params.realm_video_chat_provider = realm_available_video_chat_providers.zoom.id;
        page_params.has_zoom_token = false;

        window.open = (url) => {
            assert.ok(url.endsWith("/calls/zoom/register"));

            // The event here has value=true.  We keep it in events.js to
            // allow our tooling to verify its schema.
            server_events_dispatch.dispatch_normal_event(events.fixtures.has_zoom_token);
        };

        channel.post = (payload) => {
            assert.equal(payload.url, "/json/calls/zoom/create");
            payload.success({url: "example.zoom.com"});
            return {abort() {}};
        };

        $("#compose-textarea").val("");
        const video_handler = $("body").get_on_handler("click", ".video_link");
        video_handler(ev);
        const video_link_regex = /\[translated: Join video call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);

        $("#compose-textarea").val("");
        const audio_handler = $("body").get_on_handler("click", ".audio_link");
        audio_handler(ev);
        const audio_link_regex = /\[translated: Join audio call\.]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, audio_link_regex);
    })();

    (function test_bbb_video_link_compose_clicked() {
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

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider =
            realm_available_video_chat_providers.big_blue_button.id;

        override(compose_closed_ui, "get_recipient_label", () => "a");

        channel.get = (options) => {
            assert.equal(options.url, "/json/calls/bigbluebutton/create");
            assert.equal(options.data.meeting_name, "a meeting");
            options.success({
                url: "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22",
            });
        };

        handler(ev);
        const video_link_regex =
            /\[translated: Join video call\.]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();
});

test("test_video_chat_button_toggle disabled", ({override}) => {
    override(upload, "setup_upload", () => {});
    override(upload, "feature_check", () => {});

    page_params.realm_video_chat_provider = realm_available_video_chat_providers.disabled.id;
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), false);
});

test("test_video_chat_button_toggle no url", ({override}) => {
    override(upload, "setup_upload", () => {});
    override(upload, "feature_check", () => {});

    page_params.realm_video_chat_provider = realm_available_video_chat_providers.jitsi_meet.id;
    page_params.jitsi_server_url = null;
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), false);
});

test("test_video_chat_button_toggle enabled", ({override}) => {
    override(upload, "setup_upload", () => {});
    override(upload, "feature_check", () => {});

    page_params.realm_video_chat_provider = realm_available_video_chat_providers.jitsi_meet.id;
    page_params.jitsi_server_url = "https://meet.jit.si";
    compose.initialize();
    assert.equal($("#below-compose-content .video_link").visible(), true);
});
