"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_call_session = zrequire("compose_call_session");

run_test("ComposeCallSession", () => {
    const session_manager = compose_call_session.compose_call_session_manager;
    const session = session_manager.get_compose_call_session("key");
    const session_returned = session_manager.get_compose_call_session("key");
    assert.equal(session, session_returned);

    const xhr1 = {};
    const xhr2 = {};

    session.append_pending_xhr(xhr1);
    session.append_pending_xhr(xhr2);

    let callback_ran = false;
    const callback = () => {
        callback_ran = true;
    };

    session.maybe_run_xhr_callback(xhr1, callback);
    assert.ok(callback_ran);

    /* istanbul ignore next */
    session.maybe_run_xhr_callback(xhr1, () => {
        throw new Error("XHR callback should only run once");
    });

    session.abort_pending_xhr(xhr2);
    /* istanbul ignore next */
    session.maybe_run_xhr_callback(xhr2, () => {
        throw new Error("Callbacks shouldn't run for aborted XHRs.");
    });

    // Token callbacks for a provider.
    let callback_ran_for_zoom_token1 = false;
    let callback_ran_for_zoom_token2 = false;

    const session1 = session_manager.get_compose_call_session("key1");
    const session2 = session_manager.get_compose_call_session("key2");
    const zoom_token_callback1 = () => {
        callback_ran_for_zoom_token1 = true;
    };
    const zoom_token_callback2 = () => {
        callback_ran_for_zoom_token2 = true;
    };
    session1.add_oauth_token_callback("zoom", zoom_token_callback1);
    session2.add_oauth_token_callback("zoom", zoom_token_callback2);

    session_manager.run_and_clear_callbacks_for_provider("zoom");
    assert.ok(callback_ran_for_zoom_token1);
    assert.ok(callback_ran_for_zoom_token2);

    // All callbacks associated with a session be abandoned on calling
    // ComposeCallSession.abandon_everything.
    const session3 = session_manager.get_compose_call_session("key3");
    const xhr_obj = {};
    /* istanbul ignore next */
    session3.add_oauth_token_callback("zoom", () => {
        throw new Error("Token callbacks shouldn't run after abandon_everything");
    });

    /* istanbul ignore next */
    session3.append_pending_xhr(xhr_obj, () => {
        throw new Error("XHR callbacks shouldn't run after abandon_everything");
    });
    session_manager.abandon_session("key3");

    session3.maybe_run_xhr_callback(xhr_obj);
    session3.run_and_delete_callback_for_provider("zoom");

    /* istanbul ignore next */
    session3.maybe_run_xhr_callback(undefined, () => {
        throw new Error("callbacks shouldn't run for undefined XHR objects");
    });
});
