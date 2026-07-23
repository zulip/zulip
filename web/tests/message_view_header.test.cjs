"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

// message_view_header pulls in a number of peripheral modules that are
// irrelevant to the DM avatar context logic we exercise here.
mock_esm("../src/hash_util");
mock_esm("../src/inbox_util");
mock_esm("../src/narrow_state");
mock_esm("../src/peer_data");
mock_esm("../src/recent_view_util");
mock_esm("../src/rendered_markdown", {update_elements: noop});
mock_esm("../src/search", {
    open_search_bar_and_close_narrow_description: noop,
    close_search: noop,
});
mock_esm("../src/stream_data");

const muted_users = zrequire("muted_users");
const people = zrequire("people");
const presence = zrequire("presence");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");
const message_view_header = zrequire("message_view_header");

const user_settings = {presence_enabled: true};
initialize_user_settings({user_settings});
set_realm({});
set_current_user({});

const me = make_user({user_id: 1, full_name: "Myself", email: "me@example.com"});
const alice = make_user({user_id: 2, full_name: "Alice", email: "alice@example.com"});
const bob = make_user({user_id: 3, full_name: "Bob", email: "bob@example.com"});
const cordelia = make_user({user_id: 4, full_name: "Cordelia", email: "cordelia@example.com"});
const desdemona = make_user({user_id: 5, full_name: "Desdemona", email: "desdemona@example.com"});

function test(label, f) {
    run_test(label, (helpers) => {
        page_params.is_spectator = false;
        people.init();
        presence.presence_info.clear();
        for (const user of [me, alice, bob, cordelia, desdemona]) {
            people.add_active_user(user);
        }
        people.initialize_current_user(me.user_id);
        muted_users.set_muted_users([]);
        f(helpers);
    });
}

test("one_on_one_dm shows a single avatar and flags 1:1", () => {
    const context = message_view_header.get_dm_avatars_context([alice.user_id]);
    assert.equal(context.is_dm_narrow, true);
    assert.equal(context.is_one_on_one_dm, true);
    assert.deepEqual(
        context.dm_users.map((u) => u.user_id),
        [alice.user_id],
    );
    assert.equal(context.dm_users[0].name, "Alice");
    assert.equal(context.dm_users[0].is_muted, false);
    assert.equal(context.dm_users[0].avatar_url, `/avatar/${alice.user_id}`);
});

test("self dm is treated as a 1:1 conversation", () => {
    const context = message_view_header.get_dm_avatars_context([me.user_id]);
    assert.equal(context.is_one_on_one_dm, true);
    assert.deepEqual(
        context.dm_users.map((u) => u.user_id),
        [me.user_id],
    );
});

test("group dm returns every participant, ordered by display name", () => {
    // Pass user ids out of name order to confirm they get sorted. Every
    // participant is returned; how many render is decided responsively at
    // layout time, not here.
    const context = message_view_header.get_dm_avatars_context([
        desdemona.user_id,
        cordelia.user_id,
        alice.user_id,
        bob.user_id,
    ]);
    assert.equal(context.is_one_on_one_dm, false);
    assert.deepEqual(
        context.dm_users.map((u) => u.name),
        ["Alice", "Bob", "Cordelia", "Desdemona"],
    );
});

test("muted users are flagged and sorted as 'Muted user'", () => {
    muted_users.set_muted_users([{id: alice.user_id, timestamp: 0}]);
    const context = message_view_header.get_dm_avatars_context([alice.user_id, bob.user_id]);
    // "Bob" sorts before "Muted user", so the muted Alice comes second.
    // ("translated:" is the prefix added by the test i18n stub.)
    assert.deepEqual(
        context.dm_users.map((u) => ({name: u.name, is_muted: u.is_muted})),
        [
            {name: "Bob", is_muted: false},
            {name: "translated: Muted user", is_muted: true},
        ],
    );
});

test("presence determines the user circle class", () => {
    presence.presence_info.set(alice.user_id, {status: "active"});
    presence.presence_info.set(bob.user_id, {status: "idle"});
    // cordelia has no presence info, so she is offline.
    const context = message_view_header.get_dm_avatars_context([
        alice.user_id,
        bob.user_id,
        cordelia.user_id,
    ]);
    const class_by_name = new Map(context.dm_users.map((u) => [u.name, u.user_circle_class]));
    assert.equal(class_by_name.get("Alice"), "user-circle-active");
    assert.equal(class_by_name.get("Bob"), "user-circle-idle");
    assert.equal(class_by_name.get("Cordelia"), "user-circle-offline");
});
