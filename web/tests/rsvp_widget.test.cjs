"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

mock_esm("../src/rendered_markdown", {
    update_elements: () => {},
});

const people = zrequire("people");
const {RsvpData} = zrequire("rsvp_data");
const rsvp_widget = zrequire("rsvp_widget");
const {set_realm} = zrequire("state_data");

set_realm(make_realm());

global.realm = {
    realm_enable_guest_user_indicator: false,
};

// ---------------------------------------------------------------------------
// Test users
// ---------------------------------------------------------------------------

const me = make_user({
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 99,
});
const alice = make_user({
    email: "alice@zulip.com",
    full_name: "Alice Lee",
    user_id: 100,
});
const bob = make_user({
    email: "bob@zulip.com",
    full_name: "Bob Smith",
    user_id: 101,
});

people.add_active_user(me);
people.add_active_user(alice);
people.add_active_user(bob);
people.initialize_current_user(me.user_id);

// ---------------------------------------------------------------------------
// Helper to build a widget elem with all find results pre-registered
// ---------------------------------------------------------------------------

function make_widget_elem() {
    const $elem = $("<div>").addClass("widget-content");
    const $vote_btns = $.create(".rsvp-vote-btn");
    const $invitees_list = $.create(".rsvp-invitees-list");
    const $user_mention = $.create(`.user-mention[data-user-id="${me.user_id}"]`);
    $elem.set_find_results(".rsvp-vote-btn", $vote_btns);
    $elem.set_find_results(".rsvp-invitees-list", $invitees_list);
    $elem.set_find_results(`.user-mention[data-user-id="${me.user_id}"]`, $user_mention);
    return {$elem, $vote_btns, $invitees_list, $user_mention};
}

// ---------------------------------------------------------------------------
// activate
// ---------------------------------------------------------------------------

run_test("activate stores correct widget_data", () => {
    const {widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [alice.user_id, bob.user_id],
            },
        },
    });

    assert.equal(widget_data.widget_type, "rsvp");
    const data = widget_data.data.get_widget_data();
    assert.equal(data.topic, "Team sync");
    assert.deepEqual(data.invitees, [alice.user_id, bob.user_id]);
    assert.deepEqual(data.buckets, {accept: [], tentative: [], decline: []});
});

run_test("activate inbound_events_handler updates buckets", () => {
    const {inbound_events_handler, widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [alice.user_id],
            },
        },
    });

    inbound_events_handler([
        {sender_id: alice.user_id, data: {type: "vote", status: "accept"}},
    ]);

    const data = widget_data.data.get_widget_data();
    assert.deepEqual(data.buckets.accept, [alice.user_id]);
});

run_test("activate inbound_events_handler ignores invalid events", () => {
    const {inbound_events_handler, widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [],
            },
        },
    });

    inbound_events_handler([
        {sender_id: alice.user_id, data: {type: "unknown", status: "accept"}},
    ]);

    const data = widget_data.data.get_widget_data();
    assert.deepEqual(data.buckets, {accept: [], tentative: [], decline: []});
});

run_test("activate handles multiple inbound events", () => {
    const {inbound_events_handler, widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [alice.user_id, bob.user_id],
            },
        },
    });

    inbound_events_handler([
        {sender_id: alice.user_id, data: {type: "vote", status: "accept"}},
        {sender_id: bob.user_id,   data: {type: "vote", status: "decline"}},
    ]);

    const data = widget_data.data.get_widget_data();
    assert.deepEqual(data.buckets.accept,    [alice.user_id]);
    assert.deepEqual(data.buckets.decline,   [bob.user_id]);
    assert.deepEqual(data.buckets.tentative, []);
});

// ---------------------------------------------------------------------------
// render — html structure
// ---------------------------------------------------------------------------

run_test("render sets html on elem", () => {
    const {$elem} = make_widget_elem();

    const {widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [alice.user_id],
            },
        },
    });

    rsvp_widget.render({
        $elem,
        callback: () => {},
        widget_data,
        message: {sender_id: alice.user_id},
        rerender: false,
    });

    const html = $elem.html();
    assert.ok(html.includes("Team sync"));
    assert.ok(html.includes("rsvp-widget"));
    assert.ok(html.includes("Accept"));
    assert.ok(html.includes("Tentative"));
    assert.ok(html.includes("Decline"));
});

run_test("render marks current user mention with user-mention-me", () => {
    const {$elem, $user_mention} = make_widget_elem();

    const {widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [me.user_id, alice.user_id],
            },
        },
    });

    rsvp_widget.render({
        $elem,
        callback: () => {},
        widget_data,
        message: {sender_id: alice.user_id},
        rerender: false,
    });

    assert.ok($user_mention.hasClass("user-mention-me"));
});

run_test("render shows rsvp-active class for current user response", () => {
    const {$elem} = make_widget_elem();

    const {inbound_events_handler, widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [me.user_id],
            },
        },
    });

    inbound_events_handler([
        {sender_id: me.user_id, data: {type: "vote", status: "accept"}},
    ]);

    rsvp_widget.render({
        $elem,
        callback: () => {},
        widget_data,
        message: {sender_id: alice.user_id},
        rerender: false,
    });

    assert.ok($elem.html().includes("rsvp-active"));
});

run_test("render shows responder names next to voted button", () => {
    const {$elem} = make_widget_elem();

    const {inbound_events_handler, widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [alice.user_id],
            },
        },
    });

    inbound_events_handler([
        {sender_id: alice.user_id, data: {type: "vote", status: "tentative"}},
    ]);

    rsvp_widget.render({
        $elem,
        callback: () => {},
        widget_data,
        message: {sender_id: alice.user_id},
        rerender: false,
    });

    assert.ok($elem.html().includes("Alice Lee"));
});

// ---------------------------------------------------------------------------
// render — vote_event shape
// ---------------------------------------------------------------------------

run_test("vote_event produces correct shape for each status", () => {
    const {widget_data} = rsvp_widget.activate({
        message: {sender_id: alice.user_id},
        any_data: {
            widget_type: "rsvp",
            extra_data: {
                topic: "Team sync",
                datetime: "2026-03-24T14:30",
                invitees: [],
            },
        },
    });

    assert.deepEqual(widget_data.data.vote_event("accept"),    {type: "vote", status: "accept"});
    assert.deepEqual(widget_data.data.vote_event("tentative"), {type: "vote", status: "tentative"});
    assert.deepEqual(widget_data.data.vote_event("decline"),   {type: "vote", status: "decline"});
});
