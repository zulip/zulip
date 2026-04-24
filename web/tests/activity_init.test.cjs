"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const _document = {
    hasFocus() {
        return true;
    },
};
set_global("document", _document);

mock_esm("../src/electron_bridge", {
    electron_bridge: {},
});

const activity = zrequire("activity");

run_test("activity.initialize", ({override}) => {
    /*
        VERSION THAT WAS ORIGINALLY TESTED:
        export function initialize(): void {
            $(document).on("mousemove", () => {
                set_new_user_input(true);
            });

            $(window).on(
                "focus keydown mousedown mousemove touchmove touchstart wheel",
                mark_client_active,
            );
            if (client_is_active) {
                mark_client_idle_later();
            }
        }
    */
    const $document_stub = $("document-stub");
    const $window_stub = $("window-stub");

    override(window, "to_$", () => $window_stub);
    override(document, "to_$", () => $document_stub);

    activity.set_new_user_input(false);
    assert.equal(activity.new_user_input, false);

    activity.initialize();

    assert.equal(
        $window_stub.get_on_handler("focus keydown mousedown mousemove touchmove touchstart wheel"),
        activity.mark_client_active,
    );
    $document_stub.trigger("mousemove"); // should be set_new_user_input(true)
    assert.equal(activity.new_user_input, true);
});

run_test("mark_client_active and mark_client_idle", ({override_rewire}) => {
    // See the activity.initialize test above to verify
    // how these helper functions are reliably wired to
    // onActive and onIdle handlers on the browser window
    // object.
    let server_calls = 0;
    override_rewire(activity, "send_presence_to_server", () => {
        server_calls += 1;
    });

    // Use this to put us into an effective idle state, but then
    // after this, the code does whatever mark_client_active and
    // mark_client_idle tell it to do.
    activity.clear_for_testing();
    assert.equal(activity.compute_active_status(), "idle");

    // This is a pretty simple API.

    activity.mark_client_active();
    assert.equal(activity.compute_active_status(), "active");
    assert.equal(server_calls, 1);

    activity.mark_client_idle();
    assert.equal(activity.compute_active_status(), "idle");
    assert.equal(server_calls, 1);

    activity.mark_client_active();
    assert.equal(activity.compute_active_status(), "active");
    assert.equal(server_calls, 2);

    activity.mark_client_idle();
    assert.equal(activity.compute_active_status(), "idle");
    assert.equal(server_calls, 2);
});
