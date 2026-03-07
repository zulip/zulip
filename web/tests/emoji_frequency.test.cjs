"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// ---------------------------------------------------------------------------
// Constants matching emoji_frequency.ts
// ---------------------------------------------------------------------------
const DAY_MS = 24 * 60 * 60 * 1000;
const CURRENT_USER_ID = 5;
const OTHER_USER_ID = 9;

// ---------------------------------------------------------------------------
// Mutable registry shared across tests — mutated per test scenario
// ---------------------------------------------------------------------------
const fake_realm_emojis = {};

// ---------------------------------------------------------------------------
// ESM mocks — must be declared BEFORE zrequire of the module under test so
// that the mock is in place when emoji_frequency.ts's imports are resolved.
// ---------------------------------------------------------------------------
mock_esm("../src/emoji", {
    get_server_realm_emoji_data: () => fake_realm_emojis,
});

// message_store.get is overridden per test via the fake_msg_source closure.
let fake_msg_source = (_id) => undefined;
mock_esm("../src/message_store", {
    get: (id) => fake_msg_source(id),
});

mock_esm("../src/reactions", {
    // Use the same id format that the real helper produces
    get_local_reaction_id: (event) => `${event.reaction_type}:${event.emoji_code}`,
});

mock_esm("../src/emoji_picker", {
    rebuild_catalog: () => {},
});

mock_esm("../src/typeahead", {
    get_popular_emojis: () => [],
    set_frequently_used_emojis: () => {},
});

// ---------------------------------------------------------------------------
// Module under test
// ---------------------------------------------------------------------------
const emoji_frequency = zrequire("emoji_frequency");
const {set_current_user} = zrequire("state_data");

// Set the current user for all tests in this file.
set_current_user({user_id: CURRENT_USER_ID});

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/** Clear tracked reaction state between tests. */
function reset() {
    emoji_frequency.reaction_data.clear();
    fake_msg_source = (_id) => undefined;
    // Clear the fake registry
    for (const key of Object.keys(fake_realm_emojis)) {
        delete fake_realm_emojis[key];
    }
}

/** Returns a unix-epoch ms timestamp N days in the past. */
function days_ago_ms(n) {
    return Date.now() - n * DAY_MS;
}

/**
 * Build a minimal synthetic message object for `message_store.get`.
 * The `clean_reactions` Map must contain an entry with `emoji_id` as the key
 * so that `update_emoji_frequency_on_add_reaction_event` can find the
 * clean_reaction_object.
 */
function make_message(message_id, emoji_id, emoji_code, reaction_type) {
    return {
        id: message_id,
        clean_reactions: new Map([
            [
                emoji_id,
                {emoji_code, reaction_type, local_id: emoji_id},
            ],
        ]),
    };
}

/**
 * Fires `update_emoji_frequency_on_add_reaction_event` with a synthetic event
 * and returns the resulting ReactionUsage entry from reaction_data.
 */
function fire_add({message_id, emoji_code, reaction_type, user_id}) {
    const emoji_id = `${reaction_type}:${emoji_code}`;
    const message = make_message(message_id, emoji_id, emoji_code, reaction_type);
    fake_msg_source = (id) => (id === message_id ? message : undefined);
    emoji_frequency.update_emoji_frequency_on_add_reaction_event({
        message_id,
        emoji_code,
        reaction_type,
        user_id,
    });
    return emoji_frequency.reaction_data.get(emoji_id);
}

/**
 * Fires `update_emoji_frequency_on_remove_reaction_event` with a synthetic event.
 * Returns the updated ReactionUsage (may be undefined if the entry was removed).
 */
function fire_remove({message_id, emoji_code, reaction_type, user_id}) {
    const emoji_id = `${reaction_type}:${emoji_code}`;
    // The remove path uses message.id for current_user_reacted_message_ids.delete
    fake_msg_source = (id) => (id === message_id ? {id: message_id} : undefined);
    emoji_frequency.update_emoji_frequency_on_remove_reaction_event({
        message_id,
        emoji_code,
        reaction_type,
        user_id,
    });
    return emoji_frequency.reaction_data.get(emoji_id);
}

// ===========================================================================
// Tests: get_emoji_reaction_weight
// (private function — exercised indirectly through the add-reaction event)
// ===========================================================================

run_test("weight — unicode emoji, current user → 5", () => {
    reset();
    const usage = fire_add({
        message_id: 100,
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 5);
    assert.equal(usage.message_add_weights.get(100), 5);
});

run_test("weight — unicode emoji, other user → 1", () => {
    reset();
    const usage = fire_add({
        message_id: 101,
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
        user_id: OTHER_USER_ID,
    });
    assert.equal(usage.score, 1);
    assert.equal(usage.message_add_weights.get(101), 1);
});

run_test("weight — new realm emoji (3 days old), uploaded by current user → 30", () => {
    reset();
    fake_realm_emojis["201"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(3),
    };
    const usage = fire_add({
        message_id: 200,
        emoji_code: "201",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 30);
    assert.equal(usage.message_add_weights.get(200), 30);
});

run_test("weight — new realm emoji (3 days old), uploaded by other user, current user reacts → 10", () => {
    reset();
    fake_realm_emojis["202"] = {
        author_id: OTHER_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(3),
    };
    const usage = fire_add({
        message_id: 210,
        emoji_code: "202",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 10);
    assert.equal(usage.message_add_weights.get(210), 10);
});

run_test("weight — new realm emoji (1 day old), uploaded by other user, other user reacts → 10", () => {
    reset();
    fake_realm_emojis["203"] = {
        author_id: OTHER_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(1),
    };
    const usage = fire_add({
        message_id: 211,
        emoji_code: "203",
        reaction_type: "realm_emoji",
        user_id: OTHER_USER_ID,
    });
    // Bonus is determined by authorship, not by who reacted.
    // 'other' reacted to 'other's' new emoji → still 10 (not 30)
    assert.equal(usage.score, 10);
});

run_test("weight — old realm emoji (10 days), current user → 5", () => {
    reset();
    fake_realm_emojis["204"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(10),
    };
    const usage = fire_add({
        message_id: 220,
        emoji_code: "204",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 5);
});

run_test("weight — old realm emoji (8 days), other user → 1", () => {
    reset();
    fake_realm_emojis["205"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(8),
    };
    const usage = fire_add({
        message_id: 221,
        emoji_code: "205",
        reaction_type: "realm_emoji",
        user_id: OTHER_USER_ID,
    });
    assert.equal(usage.score, 1);
});

run_test("weight — pre-migration emoji (created_at = 0, epoch sentinel), current user → 5", () => {
    // Emoji with created_at=0 (Unix epoch ms) should be treated as ancient (~56 years old).
    // This also validates the !emoji_data.created_at → === undefined fix:
    // !0 === true but 0 !== undefined, so the epoch path correctly falls through to the
    // age-check where the age (>>7 days) disqualifies the bonus.
    reset();
    fake_realm_emojis["206"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: 0, // epoch
    };
    const usage = fire_add({
        message_id: 230,
        emoji_code: "206",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 5); // old → normal weight, no bonus
});

run_test("weight — pre-migration emoji (created_at = 0, epoch sentinel), other user → 1", () => {
    reset();
    fake_realm_emojis["206"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: 0,
    };
    const usage = fire_add({
        message_id: 231,
        emoji_code: "206",
        reaction_type: "realm_emoji",
        user_id: OTHER_USER_ID,
    });
    assert.equal(usage.score, 1);
});

run_test("weight — missing emoji data (unknown emoji_code) → fallback 5/1", () => {
    reset();
    // Code "999" has no entry in fake_realm_emojis
    const usage = fire_add({
        message_id: 240,
        emoji_code: "999",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 5);
});

run_test("weight — deactivated new emoji → no bonus; current user → 5", () => {
    // A recently-uploaded emoji that was subsequently deactivated should NOT
    // receive the bonus, even though it is within the 7-day window.
    reset();
    fake_realm_emojis["207"] = {
        author_id: CURRENT_USER_ID,
        deactivated: true, // deactivated!
        created_at: days_ago_ms(1),
    };
    const usage = fire_add({
        message_id: 250,
        emoji_code: "207",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 5); // deactivated → normal weight
});

run_test("weight — null author_id treated as other-uploaded → 10", () => {
    // Emoji uploaded before author-tracking was added have author_id = null.
    // null === CURRENT_USER_ID is always false, so they fall to the 10-point path.
    reset();
    fake_realm_emojis["208"] = {
        author_id: null,
        deactivated: false,
        created_at: days_ago_ms(2),
    };
    const usage = fire_add({
        message_id: 260,
        emoji_code: "208",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(usage.score, 10); // null author → treat as "someone else's"
});

// ===========================================================================
// Integration: symmetric add / remove
// ===========================================================================

run_test("integration — add then remove leaves score at 0 (normal emoji)", () => {
    reset();
    fire_add({
        message_id: 300,
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
        user_id: CURRENT_USER_ID,
    });
    const after_add = emoji_frequency.reaction_data.get("unicode_emoji:1f604");
    assert.equal(after_add.score, 5);

    fire_remove({
        message_id: 300,
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
        user_id: CURRENT_USER_ID,
    });
    const after_remove = emoji_frequency.reaction_data.get("unicode_emoji:1f604");
    assert.equal(after_remove.score, 0);
    assert.equal(after_remove.message_ids.size, 0);
});

run_test("integration — add (weight 30), emoji ages out, remove deducts stored 30 not recalculated 5", () => {
    // This is the key phantom-score prevention test.
    // 1. React while emoji is new → score += 30
    // 2. Simulate aging out by moving created_at into the past
    // 3. Remove reaction → score must decrease by 30 (stored), not 5 (current recalc)
    reset();
    fake_realm_emojis["301"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(1), // new emoji
    };

    fire_add({
        message_id: 310,
        emoji_code: "301",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    const usage = emoji_frequency.reaction_data.get("realm_emoji:301");
    assert.equal(usage.score, 30);
    assert.equal(usage.message_add_weights.get(310), 30);

    // Age the emoji out mid-session
    fake_realm_emojis["301"].created_at = days_ago_ms(10);

    fire_remove({
        message_id: 310,
        emoji_code: "301",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    // Must be 0, not 25 (which would happen if remove recalculated weight as 5)
    assert.equal(usage.score, 0);
});

run_test("integration — duplicate add for same message_id is ignored", () => {
    // The same message should only be counted once, regardless of how many
    // users react with the same emoji.
    reset();
    fake_realm_emojis["302"] = {
        author_id: OTHER_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(1),
    };

    // First add (CURRENT_USER_ID)
    fire_add({
        message_id: 400,
        emoji_code: "302",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(emoji_frequency.reaction_data.get("realm_emoji:302").score, 10);

    // Second add for same message_id (OTHER_USER_ID) — should be ignored since
    // message_ids already contains 400.
    fire_add({
        message_id: 400,
        emoji_code: "302",
        reaction_type: "realm_emoji",
        user_id: OTHER_USER_ID,
    });
    const usage = emoji_frequency.reaction_data.get("realm_emoji:302");
    assert.equal(usage.score, 10); // no double-count
    assert.equal(usage.message_ids.size, 1);
});

run_test("integration — message deletion removes score using stored weight", () => {
    // Messages being deleted should reduce score by the same weight that was
    // used when scoring, not a freshly recalculated weight.
    reset();
    fake_realm_emojis["303"] = {
        author_id: CURRENT_USER_ID,
        deactivated: false,
        created_at: days_ago_ms(2),
    };

    fire_add({
        message_id: 500,
        emoji_code: "303",
        reaction_type: "realm_emoji",
        user_id: CURRENT_USER_ID,
    });
    const usage = emoji_frequency.reaction_data.get("realm_emoji:303");
    assert.equal(usage.score, 30);

    // Age the emoji out before deletion arrives
    fake_realm_emojis["303"].created_at = days_ago_ms(10);

    // Build a message with clean_reactions.values() returning the emoji entry
    const emoji_id = "realm_emoji:303";
    const deletion_message = {
        id: 500,
        clean_reactions: new Map([
            [emoji_id, {emoji_code: "303", reaction_type: "realm_emoji", local_id: emoji_id}],
        ]),
    };
    fake_msg_source = (id) => (id === 500 ? deletion_message : undefined);

    emoji_frequency.update_emoji_frequency_on_messages_deletion([500]);
    assert.equal(usage.score, 0); // deducted 30 (stored), not 5 (current recalc)
    assert.equal(usage.message_ids.size, 0);
    assert.equal(usage.message_add_weights.size, 0);
});

run_test("integration — add returns undefined when message_store.get returns undefined", () => {
    // If the message is not in message_store (e.g. not yet loaded), the add
    // event is silently ignored (no crash, reaction_data unchanged).
    reset();
    fake_msg_source = (_id) => undefined;
    emoji_frequency.update_emoji_frequency_on_add_reaction_event({
        message_id: 600,
        emoji_code: "1f604",
        reaction_type: "unicode_emoji",
        user_id: CURRENT_USER_ID,
    });
    assert.equal(emoji_frequency.reaction_data.size, 0);
});
