"use strict";

const assert = require("node:assert/strict");

const {addDays} = require("date-fns");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const demo_organization_ui = zrequire("demo_organizations_ui");
const {set_realm} = zrequire("state_data");

const realm = {};
set_realm(realm);

run_test("get_demo_organization_deadline_days_remaining", ({override}) => {
    const start_time = new Date("2024-01-01T10:00:00.000Z"); // Wednesday 1/1/2024 10:00:00 AM (UTC+0)
    override(Date, "now", () => start_time);

    const demo_organization_scheduled_deletion_date = addDays(start_time, 7); // Wednesday 1/8/2024 10:00:00 AM (UTC+0)
    override(
        realm,
        "demo_organization_scheduled_deletion_date",
        Math.trunc(demo_organization_scheduled_deletion_date / 1000),
    );
    assert.equal(demo_organization_ui.get_demo_organization_deadline_days_remaining(), 7);
});
