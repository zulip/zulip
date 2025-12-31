"use strict";

const assert = require("node:assert/strict");

/*
    This module is kind of strange, because we don't
    actually test the electron_bridge code, since that
    code is basically a bunch of type declarations.

    Instead, we test how other modules interact with
    the types.

*/
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const electron_bridge = mock_esm("../src/electron_bridge");

set_global("document", {
    hasFocus() {
        return true;
    },
});

const activity = zrequire("activity");

run_test("electron_bridge", ({override_rewire}) => {
    override_rewire(activity, "send_presence_to_server", noop);

    function with_bridge_idle(bridge_idle, f) {
        with_overrides(({override}) => {
            override(electron_bridge, "electron_bridge", {
                get_idle_on_system: () => bridge_idle,
            });
            return f();
        });
    }

    with_bridge_idle(true, () => {
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "idle");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "idle");
    });

    with_overrides(({override}) => {
        override(electron_bridge, "electron_bridge", undefined);
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "idle");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "active");
    });

    with_bridge_idle(false, () => {
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "active");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "active");
    });

    assert.ok(!activity.received_new_messages);
    activity.set_received_new_messages(true);
    assert.ok(activity.received_new_messages);
});
