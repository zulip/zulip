"use strict";

const {strict: assert} = require("assert");

const {addDays} = require("date-fns");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

page_params.is_spectator = false;

const notifications = mock_esm("../src/notifications");
const util = mock_esm("../src/util");
const timerender = mock_esm("../src/timerender");

const {localstorage} = zrequire("localstorage");
const navbar_alerts = zrequire("navbar_alerts");

function test(label, f) {
    run_test(label, (helpers) => {
        window.localStorage.clear();
        f(helpers);
    });
}

test("allow_notification_alert", ({disallow, override}) => {
    const ls = localstorage();

    // Show alert.
    assert.equal(ls.get("dontAskForNotifications"), undefined);
    override(util, "is_mobile", () => false);
    override(notifications, "granted_desktop_notifications_permission", () => false);
    override(notifications, "permission_state", () => "granted");
    assert.equal(navbar_alerts.should_show_notifications(ls), true);

    // Avoid showing if the user said to never show alert on this computer again.
    ls.set("dontAskForNotifications", true);
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if device is mobile.
    ls.set("dontAskForNotifications", undefined);
    assert.equal(navbar_alerts.should_show_notifications(ls), true);
    override(util, "is_mobile", () => true);
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if notification permission is denied.
    override(util, "is_mobile", () => false);
    assert.equal(navbar_alerts.should_show_notifications(ls), true);
    override(notifications, "permission_state", () => "denied");
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if notification is already granted.
    disallow(notifications, "permission_state");
    override(notifications, "granted_desktop_notifications_permission", () => "granted");
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Don't ask for permission to spectator.
    disallow(util, "is_mobile");
    disallow(notifications, "granted_desktop_notifications_permission");
    disallow(notifications, "permission_state");
    page_params.is_spectator = true;
    assert.equal(navbar_alerts.should_show_notifications(ls), false);
});

test("profile_incomplete_alert", ({override}) => {
    // Don't test time related conditions
    override(timerender, "should_display_profile_incomplete_alert", () => true);

    // Show alert.
    page_params.is_admin = true;
    page_params.realm_description = "Organization imported from Slack!";
    assert.equal(navbar_alerts.check_profile_incomplete(), true);

    // Avoid showing if the user is not admin.
    page_params.is_admin = false;
    assert.equal(navbar_alerts.check_profile_incomplete(), false);

    // Avoid showing if the realm description is already updated.
    page_params.is_admin = true;
    assert.equal(navbar_alerts.check_profile_incomplete(), true);
    page_params.realm_description = "Organization description already set!";
    assert.equal(navbar_alerts.check_profile_incomplete(), false);
});

test("server_upgrade_alert hide_duration_expired", ({override}) => {
    const ls = localstorage();
    const start_time = 1620327447050; // Thursday 06/5/2021 07:02:27 AM (UTC+0)

    override(Date, "now", () => start_time);
    assert.equal(ls.get("lastUpgradeNagDismissalTime"), undefined);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), true);
    navbar_alerts.dismiss_upgrade_nag(ls);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), false);

    override(Date, "now", () => addDays(start_time, 8).getTime()); // Friday 14/5/2021 07:02:27 AM (UTC+0)
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), true);
    navbar_alerts.dismiss_upgrade_nag(ls);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), false);
});

test("demo_organization_days_remaining", ({override}) => {
    const start_time = new Date(1620327447050); // Thursday 06/5/2021 07:02:27 AM (UTC+0)

    const high_priority_deadline = addDays(start_time, 5);
    page_params.demo_organization_scheduled_deletion_date = Math.trunc(
        high_priority_deadline / 1000,
    );
    override(Date, "now", () => start_time);
    assert.equal(navbar_alerts.get_demo_organization_deadline_days_remaining(), 5);

    const low_priority_deadline = addDays(start_time, 10);
    page_params.demo_organization_scheduled_deletion_date = Math.trunc(
        low_priority_deadline / 1000,
    );
    override(Date, "now", () => start_time);
    assert.equal(navbar_alerts.get_demo_organization_deadline_days_remaining(), 10);
});
