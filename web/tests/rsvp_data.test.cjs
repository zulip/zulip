"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {RsvpData, vote_schema, rsvp_widget_extra_data_schema} = zrequire("rsvp_data");

// ---------------------------------------------------------------------------
// rsvp_widget_extra_data_schema
// ---------------------------------------------------------------------------

run_test("rsvp_widget_extra_data_schema accepts valid data", () => {
    const result = rsvp_widget_extra_data_schema.safeParse({
        topic: "Team sync",
        datetime: "2026-03-24T14:30",
        invitees: [1, 2, 3],
    });
    assert.ok(result.success);
    assert.equal(result.data.topic, "Team sync");
    assert.equal(result.data.datetime, "2026-03-24T14:30");
    assert.deepEqual(result.data.invitees, [1, 2, 3]);
});

run_test("rsvp_widget_extra_data_schema rejects missing topic", () => {
    const result = rsvp_widget_extra_data_schema.safeParse({
        datetime: "2026-03-24T14:30",
        invitees: [],
    });
    assert.ok(!result.success);
});

run_test("rsvp_widget_extra_data_schema rejects non-number invitees", () => {
    const result = rsvp_widget_extra_data_schema.safeParse({
        topic: "Team sync",
        datetime: "2026-03-24T14:30",
        invitees: ["alice", "bob"],
    });
    assert.ok(!result.success);
});

// ---------------------------------------------------------------------------
// vote_schema
// ---------------------------------------------------------------------------

run_test("vote_schema accepts accept status", () => {
    const result = vote_schema.safeParse({type: "vote", status: "accept"});
    assert.ok(result.success);
    assert.equal(result.data.status, "accept");
});

run_test("vote_schema accepts tentative status", () => {
    const result = vote_schema.safeParse({type: "vote", status: "tentative"});
    assert.ok(result.success);
});

run_test("vote_schema accepts decline status", () => {
    const result = vote_schema.safeParse({type: "vote", status: "decline"});
    assert.ok(result.success);
});

run_test("vote_schema rejects unknown status", () => {
    const result = vote_schema.safeParse({type: "vote", status: "maybe"});
    assert.ok(!result.success);
});

run_test("vote_schema rejects wrong type", () => {
    const result = vote_schema.safeParse({type: "question", status: "accept"});
    assert.ok(!result.success);
});

// ---------------------------------------------------------------------------
// RsvpData constructor
// ---------------------------------------------------------------------------

run_test("RsvpData constructor stores all fields", () => {
    const data = new RsvpData({
        topic: "Team sync",
        datetime: "2026-03-24T14:30",
        invitees: [1, 2],
        current_user_id: 99,
    });

    assert.equal(data.topic, "Team sync");
    assert.equal(data.datetime, "2026-03-24T14:30");
    assert.deepEqual(data.invitees, [1, 2]);
    assert.equal(data.me, 99);
    assert.equal(data.responses.size, 0);
});

run_test("RsvpData constructor with empty invitees", () => {
    const data = new RsvpData({
        topic: "Solo",
        datetime: "2026-03-24T14:30",
        invitees: [],
        current_user_id: 1,
    });

    assert.deepEqual(data.invitees, []);
});

// ---------------------------------------------------------------------------
// RsvpData.vote_event
// ---------------------------------------------------------------------------

run_test("vote_event returns correct shape for accept", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [], current_user_id: 1,
    });
    assert.deepEqual(data.vote_event("accept"), {type: "vote", status: "accept"});
});

run_test("vote_event returns correct shape for tentative", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [], current_user_id: 1,
    });
    assert.deepEqual(data.vote_event("tentative"), {type: "vote", status: "tentative"});
});

run_test("vote_event returns correct shape for decline", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [], current_user_id: 1,
    });
    assert.deepEqual(data.vote_event("decline"), {type: "vote", status: "decline"});
});

// ---------------------------------------------------------------------------
// RsvpData.handle_vote_event
// ---------------------------------------------------------------------------

run_test("handle_vote_event records response for a user", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [10], current_user_id: 99,
    });

    data.handle_vote_event(10, {type: "vote", status: "accept"});
    assert.equal(data.responses.get(10), "accept");
});

run_test("handle_vote_event overwrites previous response", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [10], current_user_id: 99,
    });

    data.handle_vote_event(10, {type: "vote", status: "accept"});
    data.handle_vote_event(10, {type: "vote", status: "decline"});

    assert.equal(data.responses.get(10), "decline");
});

run_test("handle_vote_event records responses for multiple users", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [1, 2, 3], current_user_id: 99,
    });

    data.handle_vote_event(1, {type: "vote", status: "accept"});
    data.handle_vote_event(2, {type: "vote", status: "tentative"});
    data.handle_vote_event(3, {type: "vote", status: "decline"});

    assert.equal(data.responses.get(1), "accept");
    assert.equal(data.responses.get(2), "tentative");
    assert.equal(data.responses.get(3), "decline");
});

// ---------------------------------------------------------------------------
// RsvpData.get_widget_data
// ---------------------------------------------------------------------------

run_test("get_widget_data returns empty buckets initially", () => {
    const data = new RsvpData({
        topic: "Team sync",
        datetime: "2026-03-24T14:30",
        invitees: [1, 2],
        current_user_id: 99,
    });

    const widget_data = data.get_widget_data();

    assert.equal(widget_data.topic, "Team sync");
    assert.equal(widget_data.datetime, "2026-03-24T14:30");
    assert.deepEqual(widget_data.invitees, [1, 2]);
    assert.deepEqual(widget_data.buckets, {accept: [], tentative: [], decline: []});
    assert.equal(widget_data.my_response, undefined);
});

run_test("get_widget_data places users in correct buckets", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [1, 2, 3], current_user_id: 99,
    });

    data.handle_vote_event(1, {type: "vote", status: "accept"});
    data.handle_vote_event(2, {type: "vote", status: "decline"});
    data.handle_vote_event(3, {type: "vote", status: "accept"});

    const {buckets} = data.get_widget_data();

    assert.deepEqual(buckets.accept, [1, 3]);
    assert.deepEqual(buckets.tentative, []);
    assert.deepEqual(buckets.decline, [2]);
});

run_test("get_widget_data reflects my_response when current user voted", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [], current_user_id: 99,
    });

    assert.equal(data.get_widget_data().my_response, undefined);

    data.handle_vote_event(99, {type: "vote", status: "tentative"});
    assert.equal(data.get_widget_data().my_response, "tentative");
});

run_test("get_widget_data reflects updated my_response after change", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [], current_user_id: 99,
    });

    data.handle_vote_event(99, {type: "vote", status: "accept"});
    assert.equal(data.get_widget_data().my_response, "accept");

    data.handle_vote_event(99, {type: "vote", status: "decline"});
    assert.equal(data.get_widget_data().my_response, "decline");
});

run_test("get_widget_data does not mutate across calls", () => {
    const data = new RsvpData({
        topic: "x", datetime: "2026-01-01T00:00", invitees: [1], current_user_id: 99,
    });

    data.handle_vote_event(1, {type: "vote", status: "accept"});

    const first = data.get_widget_data();
    data.handle_vote_event(1, {type: "vote", status: "decline"});
    const second = data.get_widget_data();

    // first.buckets should not have been mutated
    assert.deepEqual(first.buckets.accept, [1]);
    assert.deepEqual(second.buckets.decline, [1]);
    assert.deepEqual(second.buckets.accept, []);
});