"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const emoji_frequency = mock_esm("../src/emoji_frequency");
const left_sidebar_navigation_area = mock_esm("../src/left_sidebar_navigation_area", {
    update_my_reactions_row() {},
});
const message_events = mock_esm("../src/message_events");
const reaction_notifications = mock_esm("../src/reaction_notifications", {
    reaction_notifications_enabled: () => false,
    remove_reaction_notification() {},
});
const reactions = mock_esm("../src/reactions", {
    get_reaction_event_key: (event) => `${event.message_id}:${event.user_id}`,
    // Stops a retracted reaction counting towards the left sidebar's count.
    decrement_new_reaction_count() {},
});

const reaction_events = zrequire("reaction_events");
const {set_current_user} = zrequire("state_data");

const current_user = {user_id: 1};
set_current_user(current_user);

function reaction_event(op) {
    // A reaction by another user to a message not sent by the current
    // user, so that applying it is all that happens.
    return {
        op,
        message_id: 128,
        message_sender_id: 2,
        user_id: 3,
        reaction_type: "unicode_emoji",
        emoji_name: "airplane",
        emoji_code: "2708",
    };
}

run_test("reactions are applied to their messages", ({override}) => {
    const calls = [];
    override(reactions, "add_reaction", (event) => {
        calls.push(["add_reaction", event]);
    });
    override(emoji_frequency, "update_emoji_frequency_on_add_reaction_event", (event) => {
        calls.push(["add_frequency", event]);
    });
    override(reactions, "remove_reaction", (event) => {
        calls.push(["remove_reaction", event]);
    });
    override(emoji_frequency, "update_emoji_frequency_on_remove_reaction_event", (event) => {
        calls.push(["remove_frequency", event]);
    });
    override(message_events, "update_views_filtered_on_message_property", (ids, prop, value) => {
        calls.push(["views", ids, prop, value]);
    });

    const added = reaction_event("add");
    const removed = reaction_event("remove");
    reaction_events.received_reactions([added, removed]);
    assert.deepEqual(calls, [
        ["add_reaction", added],
        ["add_frequency", added],
        ["views", [added.message_id], "has-reaction", true],
        ["remove_reaction", removed],
        ["remove_frequency", removed],
        ["views", [removed.message_id], "has-reaction", false],
    ]);
});

run_test("an unexpected op is reported and otherwise ignored", ({disallow}) => {
    disallow(reactions, "add_reaction");
    disallow(reactions, "remove_reaction");
    disallow(message_events, "update_views_filtered_on_message_property");
    disallow(reaction_notifications, "remove_reaction_notification");

    blueslip.expect("error", "Unexpected event type reaction/other");
    reaction_events.received_reactions([reaction_event("other")]);
});

run_test("a reaction that fails to apply does not stop the rest", ({override}) => {
    const applied = [];
    override(reactions, "add_reaction", (event) => {
        if (event.message_id === 1) {
            throw new Error("Cannot find realm emoji");
        }
        applied.push(event.message_id);
    });
    override(emoji_frequency, "update_emoji_frequency_on_add_reaction_event", noop);
    override(message_events, "update_views_filtered_on_message_property", noop);

    blueslip.expect("error", "Failed to apply a reaction event");
    reaction_events.received_reactions([
        {...reaction_event("add"), message_id: 1},
        {...reaction_event("add"), message_id: 2},
    ]);
    assert.deepEqual(applied, [2]);
});

run_test("every reaction is applied before any is acted on", ({override}) => {
    const calls = [];
    override(reactions, "add_reaction", () => {
        calls.push("add_reaction");
    });
    override(reactions, "remove_reaction", () => {
        calls.push("remove_reaction");
    });
    override(emoji_frequency, "update_emoji_frequency_on_add_reaction_event", noop);
    override(emoji_frequency, "update_emoji_frequency_on_remove_reaction_event", noop);
    override(message_events, "update_views_filtered_on_message_property", noop);
    override(reaction_notifications, "remove_reaction_notification", () => {
        calls.push("remove_reaction_notification");
    });
    override(left_sidebar_navigation_area, "update_my_reactions_row", () => {
        calls.push("update_my_reactions_row");
    });

    reaction_events.received_reactions([reaction_event("remove"), reaction_event("add")]);
    assert.deepEqual(calls, [
        "remove_reaction",
        "add_reaction",
        "remove_reaction_notification",
        "update_my_reactions_row",
    ]);
});
