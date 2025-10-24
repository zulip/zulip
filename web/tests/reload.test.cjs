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
    assert.ok(reload.is_stale_refresh_token("#reload:234234235234", Date.now()), true);
});

run_test("recent_token_is_not_stale ", () => {
    assert.ok(
        !reload.is_stale_refresh_token(
            {
                url: "#reload:234234235234",
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
                url: "#reload:234234235234",
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

    reload.initiate({});
    assert.equal(idle_timeout_created, true);
    assert.equal(idle_timeout_canceled, false);

    idle_timeout_created = false;

    reload.maybe_reload_after_compose_end();
    assert.equal(idle_timeout_canceled, true);
    assert.equal(idle_timeout_created, true);
});
