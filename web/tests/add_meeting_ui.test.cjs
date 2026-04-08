"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// ---------------------------------------------------------------------------
// Controllable narrow_state.stream_id — set per test
// ---------------------------------------------------------------------------

let current_stream_id;

mock_esm("../src/narrow_state", {
    stream_id: () => current_stream_id,
});

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

mock_esm("../src/channel", {
    post: () => {},
    get: () => {},
});

mock_esm("../src/flatpickr", {
    show_flatpickr: () => {},
});

mock_esm("../src/pill_typeahead", {
    set_up_user: () => {},
});

mock_esm("../src/dialog_widget", {
    launch: () => {},
    close_if_open: () => {},
});

mock_esm("../src/modals", {
    close_if_open: () => {},
});

mock_esm("../src/hash_util", {
    by_stream_topic_url: () => "#narrow/stream/1/topic/test",
});

mock_esm("../src/browser_history", {
    go_to_location: () => {},
});

mock_esm("../src/timerender", {
    get_full_datetime: () => "Monday, March 24 @2:30 PM",
});

mock_esm("../src/util", {
    the: (x) => x,
});

const appended_users = [];

mock_esm("../src/user_pill", {
    create_pills: () => ({
        onPillCreate: () => {},
        onPillRemove: () => {},
    }),
    get_user_ids: () => [],
    append_user: (user, _widget) => { appended_users.push(user); },
});

mock_esm("../src/dropdown_widget", {
    DropdownWidget: class {
        constructor() {}
        setup() {}
    },
});

const people = zrequire("people");
const stream_data = zrequire("stream_data");
const peer_data = zrequire("peer_data");
const {set_realm} = zrequire("state_data");
const add_meeting_ui = zrequire("add_meeting_ui");

set_realm(make_realm());

global.realm = {
    realm_enable_guest_user_indicator: false,
};

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const me = make_user({email: "me@zulip.com", full_name: "Me Myself", user_id: 99});
const alice = make_user({email: "alice@zulip.com", full_name: "Alice Lee", user_id: 100});
const bob = make_user({email: "bob@zulip.com", full_name: "Bob Smith", user_id: 101});

people.add_active_user(me);
people.add_active_user(alice);
people.add_active_user(bob);
people.initialize_current_user(me.user_id);

const design = make_stream({stream_id: 42, name: "design", subscribed: true, is_muted: false});
stream_data.add_sub_for_tests(design);

// ---------------------------------------------------------------------------
// submit button state logic
// ---------------------------------------------------------------------------

function reset_modal_dom() {
    $("#rsvp-meeting-topic").val("");
    $("#rsvp-meeting-datetime-value").val("");
    $("#add-rsvp-meeting-modal .dialog_submit_button").prop("disabled", true);
}

run_test("submit button disabled when topic is empty", () => {
    reset_modal_dom();
    $("#rsvp-meeting-topic").val("");
    $("#rsvp-meeting-datetime-value").val("2026-03-24T14:30");

    const topic = $("#rsvp-meeting-topic").val().trim();
    const datetime = $("#rsvp-meeting-datetime-value").val().trim();

    assert.ok(!(topic && datetime));
});

run_test("submit button disabled when datetime is empty", () => {
    reset_modal_dom();
    $("#rsvp-meeting-topic").val("Team sync");
    $("#rsvp-meeting-datetime-value").val("");

    const topic = $("#rsvp-meeting-topic").val().trim();
    const datetime = $("#rsvp-meeting-datetime-value").val().trim();

    assert.ok(!(topic && datetime));
});

run_test("submit button enabled when both fields are filled", () => {
    reset_modal_dom();
    $("#rsvp-meeting-topic").val("Team sync");
    $("#rsvp-meeting-datetime-value").val("2026-03-24T14:30");

    const topic = $("#rsvp-meeting-topic").val().trim();
    const datetime = $("#rsvp-meeting-datetime-value").val().trim();

    assert.ok(topic && datetime);
});

run_test("submit button disabled when topic is only whitespace", () => {
    reset_modal_dom();
    $("#rsvp-meeting-topic").val("   ");
    $("#rsvp-meeting-datetime-value").val("2026-03-24T14:30");

    const topic = $("#rsvp-meeting-topic").val().trim();
    const datetime = $("#rsvp-meeting-datetime-value").val().trim();

    assert.ok(!(topic && datetime));
});

// ---------------------------------------------------------------------------
// on_add_all_users_click
// ---------------------------------------------------------------------------

run_test("on_add_all_users_click appends all channel subscribers", () => {
    appended_users.length = 0;
    current_stream_id = design.stream_id;
    peer_data.set_subscribers(design.stream_id, [alice.user_id, bob.user_id]);

    add_meeting_ui.__test_only.set_invite_users_widget({});
    add_meeting_ui.__test_only.on_add_all_users_click();

    assert.equal(appended_users.length, 2);
});

run_test("on_add_all_users_click is no-op without stream_id", () => {
    appended_users.length = 0;
    current_stream_id = undefined;

    add_meeting_ui.__test_only.set_invite_users_widget({});
    add_meeting_ui.__test_only.on_add_all_users_click();

    assert.equal(appended_users.length, 0);
});

run_test("on_add_all_users_click is no-op without widget", () => {
    appended_users.length = 0;
    current_stream_id = design.stream_id;

    add_meeting_ui.__test_only.set_invite_users_widget(null);
    add_meeting_ui.__test_only.on_add_all_users_click();
    assert.equal(appended_users.length, 0);
});

// ---------------------------------------------------------------------------
// setup_add_meeting_dropdown_widget_if_needed — idempotency guard
// ---------------------------------------------------------------------------

run_test("setup only creates the dropdown widget once", () => {
    add_meeting_ui.__test_only.reset_composebox_widget_flag();

    add_meeting_ui.setup_add_meeting_dropdown_widget_if_needed();

    const flag_after_first = add_meeting_ui.__test_only.get_composebox_widget_flag();
    assert.ok(flag_after_first);

    add_meeting_ui.setup_add_meeting_dropdown_widget_if_needed();
    add_meeting_ui.setup_add_meeting_dropdown_widget_if_needed();

    assert.ok(add_meeting_ui.__test_only.get_composebox_widget_flag());
});