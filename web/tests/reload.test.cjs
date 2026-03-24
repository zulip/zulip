"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel");
mock_esm("../src/popup_banners", {
    open_reloading_application_banner: noop,
});

// override file-level function call in reload.ts
window.addEventListener = noop;
const reload = zrequire("reload");
const reload_state = zrequire("reload_state");

set_global("window", {
    to_$: () => $("window-stub"),
    location: {
        reload: noop,
        replace: noop,
    },
});

run_test("old_metadata_string_is_stale", () => {
    assert.ok(reload.is_stale_refresh_token({reload_data: {hash: ""}}, Date.now()), true);
});

run_test("recent_token_is_not_stale ", () => {
    assert.ok(
        !reload.is_stale_refresh_token(
            {
                hash: "",
                timestamp: Date.parse("21 Jan 2022 00:00:00 GMT"),
            },
            Date.parse("23 Jan 2022 00:00:00 GMT"),
        ),
    );
});

run_test("old_token_is_stale ", () => {
    assert.ok(
        reload.is_stale_refresh_token(
            {
                hash: "",
                timestamp: Date.parse("13 Jan 2022 00:00:00 GMT"),
            },
            Date.parse("23 Jan 2022 00:00:00 GMT"),
        ),
    );
});

run_test("reload", () => {
    channel.get = (opts) => {
        assert.equal(opts.url, "/compatibility");
        opts.success();
    };

    // No reload has been initiated so "maybe_reload_*" shouldn't
    // do anything
    reload.maybe_reset_pending_reload_timeout("compose_start");
    assert.equal(reload.reset_reload_timeout, undefined);

    reload.maybe_reset_pending_reload_timeout("compose_end");
    assert.equal(reload.reset_reload_timeout, undefined);

    // Initiate reload should create a new timeout and creates
    // reset_reload_timeout
    reload.initiate({});
    assert.equal(typeof reload.reset_reload_timeout, "function");

    reload.maybe_reset_pending_reload_timeout("compose_start");

    reload.maybe_reset_pending_reload_timeout("compose_end");
});

run_test("immediate_reload_skips_compatibility_check", () => {
    reload_state.clear_for_testing();

    // do_reload_app should run synchronously without the /compatibility
    // check, so channel.get should not be called. Setting it to
    // undefined ensures a clear error if it is called unexpectedly.
    channel.get = undefined;

    reload.initiate({immediate: true, save_compose: true});

    assert.ok(reload_state.is_in_progress());
});
