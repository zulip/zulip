"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire, set_global} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

const events = require("./lib/events");

const channel = mock_esm("../../static/js/channel");
const upload = mock_esm("../../static/js/upload");
mock_esm("../../static/js/resize", {
    watch_manual_resize() {},
});
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

const server_events_dispatch = zrequire("server_events_dispatch");
const compose_ui = zrequire("compose_ui");
const compose = zrequire("compose");
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
    run_test(label, ({override, override_rewire}) => {
        page_params.realm_available_video_chat_providers = realm_available_video_chat_providers;
        f({override, override_rewire});
    });
}

test("videos", ({override, override_rewire}) => {
    page_params.realm_video_chat_provider = realm_available_video_chat_providers.disabled.id;

    override(upload, "setup_upload", () => {});
    override(upload, "feature_check", () => {});

    stub_out_video_calls();

    compose.initialize();

    (function test_no_provider_video_link_compose_clicked() {
        let called = false;

        const textarea = $.create("target-stub");
        textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault: () => {},
            stopPropagation: () => {},
            target: {
                to_$: () => textarea,
            },
        };

        override_rewire(compose_ui, "insert_syntax_and_focus", () => {
            called = true;
        });

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        handler(ev);
        assert.ok(!called);
    })();

    (function test_jitsi_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("jitsi-target-stub");
        textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault: () => {},
            stopPropagation: () => {},
            target: {
                to_$: () => textarea,
            },
        };

        override_rewire(compose_ui, "insert_syntax_and_focus", (syntax) => {
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
            /\[translated: Click to join video call]\(https:\/\/meet.jit.si\/\d{15}\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_zoom_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("zoom-target-stub");
        textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault: () => {},
            stopPropagation: () => {},
            target: {
                to_$: () => textarea,
            },
        };

        override_rewire(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
        });

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

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
            return {abort: () => {}};
        };

        handler(ev);
        const video_link_regex = /\[translated: Click to join video call]\(example\.zoom\.com\)/;
        assert.ok(called);
        assert.match(syntax_to_insert, video_link_regex);
    })();

    (function test_bbb_video_link_compose_clicked() {
        let syntax_to_insert;
        let called = false;

        const textarea = $.create("bbb-target-stub");
        textarea.set_parents_result(".message_edit_form", []);

        const ev = {
            preventDefault: () => {},
            stopPropagation: () => {},
            target: {
                to_$: () => textarea,
            },
        };

        override_rewire(compose_ui, "insert_syntax_and_focus", (syntax) => {
            syntax_to_insert = syntax;
            called = true;
        });

        const handler = $("body").get_on_handler("click", ".video_link");
        $("#compose-textarea").val("");

        page_params.realm_video_chat_provider =
            realm_available_video_chat_providers.big_blue_button.id;

        channel.get = (options) => {
            assert.equal(options.url, "/json/calls/bigbluebutton/create");
            options.success({
                url: "/calls/bigbluebutton/join?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22",
            });
        };

        handler(ev);
        const video_link_regex =
            /\[translated: Click to join video call]\(\/calls\/bigbluebutton\/join\?meeting_id=%22zulip-1%22&password=%22AAAAAAAAAA%22&checksum=%2232702220bff2a22a44aee72e96cfdb4c4091752e%22\)/;
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
