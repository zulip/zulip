"use strict";

const {strict: assert} = require("assert");

const {addDays} = require("date-fns");

const {mock_cjs, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_cjs("jquery", $);

const ls_container = new Map();

const localStorage = set_global("localStorage", {
    getItem(key) {
        return ls_container.get(key);
    },
    setItem(key, val) {
        ls_container.set(key, val);
    },
    removeItem(key) {
        ls_container.delete(key);
    },
    clear() {
        ls_container.clear();
    },
});

const {localstorage} = zrequire("localstorage");
const panels = zrequire("panels");

function test(label, f) {
    run_test(label, (override) => {
        localStorage.clear();
        f(override);
    });
}

test("server_upgrade_alert hide_duration_expired", (override) => {
    const ls = localstorage();
    const start_time = new Date(1620327447050); // Thursday 06/5/2021 07:02:27 AM (UTC+0)

    override(Date, "now", () => start_time);
    assert.equal(ls.get("lastUpgradeNagDismissalTime"), undefined);
    assert.equal(panels.should_show_server_upgrade_notification(ls), true);
    panels.dismiss_upgrade_nag(ls);
    assert.equal(panels.should_show_server_upgrade_notification(ls), false);

    override(Date, "now", () => addDays(start_time, 8)); // Friday 14/5/2021 07:02:27 AM (UTC+0)
    assert.equal(panels.should_show_server_upgrade_notification(ls), true);
    panels.dismiss_upgrade_nag(ls);
    assert.equal(panels.should_show_server_upgrade_notification(ls), false);
});
