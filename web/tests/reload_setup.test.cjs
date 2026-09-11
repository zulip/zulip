"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const compose_actions = mock_esm("../src/compose_actions");
const drafts = mock_esm("../src/drafts", {draft_model: {}});
mock_esm("../src/activity", {set_new_user_input: noop});
mock_esm("../src/message_fetch", {set_initial_pointer_and_offset: noop});
mock_esm("../src/message_view", {changehash: noop});

// override file-level function call in reload.ts
window.addEventListener = noop;
const {localstorage} = zrequire("localstorage");
const reload_setup = zrequire("reload_setup");

run_test("restored compose keeps its draft_id", ({override}) => {
    const draft_id = "1234abcd-5678";
    const draft = {
        type: "stream",
        stream_id: 1,
        topic: "reload",
        content: "unsent message",
        updatedAt: 1,
        is_sending_saving: false,
        drafts_version: 1,
    };
    override(drafts.draft_model, "getDraft", (id) => {
        assert.equal(id, draft_id);
        return draft;
    });

    const ls = localstorage();
    ls.set("reload:42", {
        hash: "#feed",
        timestamp: 1,
        compose_active_draft_id: draft_id,
    });
    window.location.hash = "#reload:42";

    let start_opts;
    override(compose_actions, "start", (opts) => {
        start_opts = opts;
    });

    reload_setup.initialize();

    // The restored compose box must be associated with the draft that
    // was saved before the reload, so that subsequent saves update it
    // instead of adding a duplicate.
    assert.deepEqual(start_opts, {...draft, message_type: "stream", draft_id});
    assert.equal(ls.get("reload:42"), undefined);
});
