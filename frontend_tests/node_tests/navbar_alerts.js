"use strict";

const {strict: assert} = require("assert");

const {addDays} = require("date-fns");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {page_params} = require("../zjsunit/zpage_params");

page_params.is_spectator = false;

// Dependencies
set_global("document", {
    hasFocus() {
        return true;
    },
});

const {localstorage} = zrequire("localstorage");
const navbar_alerts = zrequire("navbar_alerts");
const notifications = zrequire("notifications");
const util = zrequire("util");

function test(label, f) {
    run_test(label, ({override}) => {
        window.localStorage.clear();
        f({override});
    });
}

test("allow_notification_alert", () => {
    const ls = localstorage();

    // Show alert.
    assert.equal(ls.get("dontAskForNotifications"), undefined);
    util.is_mobile = () => false;
    notifications.granted_desktop_notifications_permission = () => false;
    notifications.permission_state = () => "granted";
    assert.equal(navbar_alerts.should_show_notifications(ls), true);

    // Avoid showing if the user said to never show alert on this computer again.
    ls.set("dontAskForNotifications", true);
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if device is mobile.
    ls.set("dontAskForNotifications", undefined);
    assert.equal(navbar_alerts.should_show_notifications(ls), true);
    util.is_mobile = () => true;
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if notification permission is denied.
    util.is_mobile = () => false;
    assert.equal(navbar_alerts.should_show_notifications(ls), true);
    notifications.permission_state = () => "denied";
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Avoid showing if notification is already granted.
    /* istanbul ignore next */
    notifications.permission_state = () => "granted";
    notifications.granted_desktop_notifications_permission = () => "granted";
    assert.equal(navbar_alerts.should_show_notifications(ls), false);

    // Don't ask for permission to spectator.
    /* istanbul ignore next */
    util.is_mobile = () => false;
    /* istanbul ignore next */
    notifications.granted_desktop_notifications_permission = () => false;
    /* istanbul ignore next */
    notifications.permission_state = () => "granted";
    page_params.is_spectator = true;
    assert.equal(navbar_alerts.should_show_notifications(ls), false);
});

test("profile_incomplete_alert", () => {
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
    const start_time = new Date(1620327447050); // Thursday 06/5/2021 07:02:27 AM (UTC+0)

    override(Date, "now", () => start_time);
    assert.equal(ls.get("lastUpgradeNagDismissalTime"), undefined);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), true);
    navbar_alerts.dismiss_upgrade_nag(ls);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), false);

    override(Date, "now", () => addDays(start_time, 8)); // Friday 14/5/2021 07:02:27 AM (UTC+0)
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), true);
    navbar_alerts.dismiss_upgrade_nag(ls);
    assert.equal(navbar_alerts.should_show_server_upgrade_notification(ls), false);
});

test("demo_org_days_remaining", ({override}) => {
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
