"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");

const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const pm_conversations_util = zrequire("pm_conversations_util");

const alice = make_user({email: "alice@example.com", user_id: 4, full_name: "Alice"});
const me = make_user({email: "me@example.com", user_id: 15, full_name: "Me"});
people.add_active_user(alice);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, (helpers) => {
        pm_conversations.clear_for_testing();
        f(helpers);
    });
}

test("re-adds the conversation when the server reports a remaining message", () => {
    let dom_updated = false;

    channel.get = (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.deepEqual(JSON.parse(opts.data.narrow), [{operator: "dm", operand: [4]}]);
        assert.equal(opts.data.anchor, "newest");
        assert.equal(opts.data.num_before, 1);
        assert.equal(opts.data.num_after, 0);
        opts.success({messages: [{id: 555}]});
    };

    assert.ok(!pm_conversations.recent.has_conversation("4"));
    pm_conversations_util.update_dm_last_message_id("4", () => {
        dom_updated = true;
    });

    assert.ok(pm_conversations.recent.has_conversation("4"));
    assert.equal(pm_conversations.recent.get()[0].max_message_id, 555);
    assert.ok(dom_updated);
});

test("leaves the conversation removed when the server reports it is empty", () => {
    channel.get = (opts) => {
        opts.success({messages: []});
    };

    // The conversation isn't re-added, so the dom-update callback (noop) is
    // never invoked.
    pm_conversations_util.update_dm_last_message_id("4", noop);

    assert.ok(!pm_conversations.recent.has_conversation("4"));
});

test("ignores errors", () => {
    channel.get = (opts) => {
        opts.error();
    };

    // Should not throw.
    pm_conversations_util.update_dm_last_message_id("4", noop);
    assert.ok(!pm_conversations.recent.has_conversation("4"));
});
