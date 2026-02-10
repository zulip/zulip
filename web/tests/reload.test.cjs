"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");

// override file-level function call in reload.ts
window.addEventListener = noop;
const reload = zrequire("reload");

set_global("document", {});

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

run_test("reload", ({override}) => {
    let idle_timeout_created = false;
    let idle_timeout_canceled = false;
    override(document, "to_$", () => ({
        idle() {
            idle_timeout_created = true;
            return {
                cancel() {
                    idle_timeout_canceled = true;
                },
            };
        },
    }));
    channel.get = (opts) => {
        assert.equal(opts.url, "/compatibility");
        opts.success();
    };

    // No reload has been initiated so "maybe_reload_*" shouldn't
    // do anything
    reload.maybe_reset_pending_reload_timeout("compose_start");
    assert.equal(idle_timeout_created, false);
    assert.equal(idle_timeout_canceled, false);
    assert.equal(reload.reset_reload_timeout, undefined);

    reload.maybe_reset_pending_reload_timeout("compose_end");
    assert.equal(idle_timeout_created, false);
    assert.equal(idle_timeout_canceled, false);
    assert.equal(reload.reset_reload_timeout, undefined);

    // Initiate reload should create a new timeout and creates
    // reset_reload_timeout
    reload.initiate({});
    assert.equal(idle_timeout_created, true);
    assert.equal(idle_timeout_canceled, false);
    assert.equal(typeof reload.reset_reload_timeout, "function");

    idle_timeout_created = false;

    reload.maybe_reset_pending_reload_timeout("compose_start");
    assert.equal(idle_timeout_canceled, true);
    assert.equal(idle_timeout_created, true);

    idle_timeout_created = false;
    idle_timeout_canceled = false;

    reload.maybe_reset_pending_reload_timeout("compose_end");
    assert.equal(idle_timeout_canceled, true);
    assert.equal(idle_timeout_created, true);
});
