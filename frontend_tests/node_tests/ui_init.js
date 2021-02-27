"use strict";

const rewiremock = require("rewiremock/node");

const {stub_templates} = require("../zjsunit/handlebars");
const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

/*
    This test suite is designed to find errors
    in our initialization sequence.  It doesn't
    really validate any behavior, other than just
    making sure things don't fail.  For more
    directed testing of individual modules, you
    should create dedicated test suites.

    Also, we stub a lot of initialization here that
    is tricky to test due to dependencies on things
    like jQuery.  A good project is to work through
    ignore_modules and try to make this test more
    complete.

    Also, it's good to be alert here for things
    that can be cleaned up in the code--for example,
    not everything needs to happen in `initialization`--
    some things can happen later in a `launch` method.

*/

set_global("document", {
    location: {
        protocol: "http",
    },
});

set_global("csrf_token", "whatever");

const resize = set_global("resize", {
    handler: () => {},
});
const page_params = set_global("page_params", {});

page_params.realm_default_streams = [];
page_params.subscriptions = [];
page_params.unsubscribed = [];
page_params.never_subscribed = [];
page_params.realm_notifications_stream_id = -1;
page_params.unread_msgs = {
    huddles: [],
    pms: [],
    streams: [],
    mentions: [],
};
page_params.recent_private_conversations = [];
page_params.user_status = {};
page_params.realm_emoji = {};
page_params.realm_users = [];
page_params.realm_non_active_users = [];
page_params.cross_realm_bots = [];
page_params.muted_topics = [];
page_params.realm_user_groups = [];
page_params.realm_bots = [];
page_params.realm_filters = [];
page_params.starred_messages = [];
page_params.presences = [];

set_global("activity", {initialize() {}});
set_global("click_handlers", {initialize() {}});
rewiremock("../../static/js/compose_pm_pill").with({initialize() {}});
rewiremock("../../static/js/drafts").with({initialize() {}});
set_global("emoji_picker", {initialize() {}});
set_global("gear_menu", {initialize() {}});
set_global("hashchange", {initialize() {}});
set_global("hotspots", {initialize() {}});
// Accesses home_msg_list, which is a lot of complexity to set up
set_global("message_fetch", {initialize() {}});
set_global("message_scroll", {initialize() {}});
const message_viewport = {
    __esModule: true,
    initialize() {},
};
rewiremock("../../static/js/message_viewport").with(message_viewport);
set_global("panels", {initialize() {}});
set_global("popovers", {initialize() {}});
rewiremock("../../static/js/reload").with({initialize() {}});
set_global("scroll_bar", {initialize() {}});
const server_events = set_global("server_events", {initialize() {}});
set_global("settings_sections", {initialize() {}});
set_global("settings_panel_menu", {initialize() {}});
set_global("settings_toggle", {initialize() {}});
set_global("subs", {initialize() {}});
set_global("timerender", {initialize() {}});
const ui = set_global("ui", {initialize() {}});
rewiremock("../../static/js/unread_ui").with({initialize() {}});

server_events.home_view_loaded = () => true;

resize.watch_manual_resize = () => {};

rewiremock("../../static/js/favicon").with({});
rewiremock("../../static/js/emojisets").with({
    initialize: () => {},
});

rewiremock.enable();

const util = zrequire("util");

zrequire("hash_util");
zrequire("stream_color");
zrequire("stream_edit");
zrequire("color_data");
zrequire("stream_data");
zrequire("condense");
zrequire("lightbox");
zrequire("overlays");
zrequire("message_view_header");
zrequire("presence");
zrequire("search_pill_widget");
zrequire("unread");
zrequire("bot_data");
const upload = zrequire("upload");
const compose = zrequire("compose");
zrequire("composebox_typeahead");
zrequire("narrow");
zrequire("search_suggestion");
zrequire("search");
zrequire("notifications");
zrequire("stream_list");
zrequire("sent_messages");
zrequire("starred_messages");
zrequire("recent_topics");

run_test("initialize_everything", () => {
    util.is_mobile = () => false;
    stub_templates(() => "some-html");
    ui.get_scroll_element = (element) => element;

    const document_stub = $.create("document-stub");
    document.to_$ = () => document_stub;
    document_stub.idle = () => {};

    const window_stub = $.create("window-stub");
    set_global("to_$", () => window_stub);
    window_stub.idle = () => {};
    window_stub.on = () => window_stub;

    message_viewport.message_pane = $(".app");

    const $message_view_header = $.create("#message_view_header");
    $message_view_header.append = () => {};
    upload.setup_upload = () => {};

    $("#stream_message_recipient_stream").typeahead = () => {};
    $("#stream_message_recipient_topic").typeahead = () => {};
    $("#private_message_recipient").typeahead = () => {};
    $("#compose-textarea").typeahead = () => {};
    $("#search_query").typeahead = () => {};

    const value_stub = $.create("value");
    const count_stub = $.create("count");
    count_stub.set_find_results(".value", value_stub);
    $(".top_left_starred_messages").set_find_results(".count", count_stub);

    $("#message_view_header .stream").length = 0;

    // set find results doesn't work here since we call .empty() in the code.
    $message_view_header.find = () => false;

    compose.compute_show_video_chat_button = () => {};
    $("#below-compose-content .video_link").toggle = () => {};

    $("<audio>")[0] = "stub";

    zrequire("ui_init");
});

rewiremock.disable();
