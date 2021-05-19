"use strict";

const {strict: assert} = require("assert");

const {addDays} = require("date-fns");

const {mock_cjs, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

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
// Dependencies
set_global("document", {
    hasFocus() {
        return true;
    },
});

const {localstorage} = zrequire("localstorage");
const panels = zrequire("panels");
const notifications = zrequire("notifications");
const util = zrequire("util");

function test(label, f) {
    run_test(label, (override) => {
        localStorage.clear();
        f(override);
    });
}

test("allow_notification_alert", () => {
    const ls = localstorage();

    // Show alert.
    assert.equal(ls.get("dontAskForNotifications"), undefined);
    util.is_mobile = () => false;
    notifications.granted_desktop_notifications_permission = () => false;
    notifications.permission_state = () => "granted";
    assert.equal(panels.should_show_notifications(ls), true);

    // Avoid showing if the user said to never show alert on this computer again.
    ls.set("dontAskForNotifications", true);
    assert.equal(panels.should_show_notifications(ls), false);

    // Avoid showing if device is mobile.
    ls.set("dontAskForNotifications", undefined);
    assert.equal(panels.should_show_notifications(ls), true);
    util.is_mobile = () => true;
    assert.equal(panels.should_show_notifications(ls), false);

    // Avoid showing if notificaiton permission is denied.
    util.is_mobile = () => false;
    assert.equal(panels.should_show_notifications(ls), true);
    notifications.permission_state = () => "denied";
    assert.equal(panels.should_show_notifications(ls), false);

    // Avoid showing if notification is already granted.
    notifications.permission_state = () => "granted";
    notifications.granted_desktop_notifications_permission = () => "granted";
    assert.equal(panels.should_show_notifications(ls), false);
});

test("profile_incomplete_alert", () => {
    // Show alert.
    page_params.is_admin = true;
    page_params.realm_description = "Organization imported from Slack!";
    assert.equal(panels.check_profile_incomplete(), true);

    // Avoid showing if the user is not admin.
    page_params.is_admin = false;
    assert.equal(panels.check_profile_incomplete(), false);

    // Avoid showing if the realm description is already updated.
    page_params.is_admin = true;
    assert.equal(panels.check_profile_incomplete(), true);
    page_params.realm_description = "Organization description already set!";
    assert.equal(panels.check_profile_incomplete(), false);
});

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
