"use strict";

const assert = require("node:assert/strict");

const {addDays} = require("date-fns");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const desktop_notifications = mock_esm("../src/desktop_notifications");
const unread = mock_esm("../src/unread");
const util = mock_esm("../src/util");

const {localstorage} = zrequire("localstorage");
const navbar_alerts = zrequire("navbar_alerts");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);

function test(label, f) {
    run_test(label, (helpers) => {
        window.localStorage.clear();
        f(helpers);
    });
}

test("should_show_desktop_notifications_banner", ({override}) => {
    const ls = localstorage();

    // Show desktop notifications banner when following conditions are suitable:
    // - Notification permission is not already granted.
    // - The user is not a spectator.
    // - The device is not mobile.
    // - Notification permission is not denied.
    // - The user has not said to never show banner on this device again.
    ls.set("dontAskForNotifications", undefined);
    page_params.is_spectator = false;
    override(util, "is_mobile", () => false);
    override(desktop_notifications, "granted_desktop_notifications_permission", () => false);
    override(desktop_notifications, "permission_state", () => "default");
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), true);

    // Don't ask for permission if user has said to never show banner on this device again.
    ls.set("dontAskForNotifications", true);
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), false);
    ls.set("dontAskForNotifications", undefined);

    // Don't ask for permission if device is mobile.
    override(util, "is_mobile", () => true);
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), false);
    override(util, "is_mobile", () => false);

    // Don't ask for permission if notification is denied by user.
    override(desktop_notifications, "permission_state", () => "denied");
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), false);

    // Don't ask for permission if notification is already granted by user.
    override(desktop_notifications, "granted_desktop_notifications_permission", () => true);
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), false);

    // Don't ask for permission if user is a spectator.
    page_params.is_spectator = true;
    assert.equal(navbar_alerts.should_show_desktop_notifications_banner(ls), false);
});

test("should_show_bankruptcy_banner", ({override}) => {
    // Show bankruptcy banner when following conditions are suitable:
    // - The user has read at least one message, i.e., furthest_read_time is defined.
    // - The user has more than 500 unread messages.
    // - The user has not read any message in the last 2 days.
    const start_time = new Date("2024-01-01T10:00:00.000Z"); // Wednesday 1/1/2024 10:00:00 AM (UTC+0)
    override(page_params, "furthest_read_time", start_time.getTime() / 1000);
    override(Date, "now", () => addDays(start_time, 3).getTime()); // Saturday 1/4/2024 10:00:00 AM (UTC+0)
    override(unread, "get_unread_message_count", () => 501);
    assert.equal(navbar_alerts.should_show_bankruptcy_banner(), true);

    // Don't show bankruptcy banner if user has not read any message.
    override(page_params, "furthest_read_time", undefined);
    assert.equal(navbar_alerts.should_show_bankruptcy_banner(), false);
    override(page_params, "furthest_read_time", start_time.getTime() / 1000);

    // Don't show bankruptcy banner if user has read any message in the last 2 days.
    override(Date, "now", () => addDays(start_time, 1).getTime()); // Thursday 1/2/2024 10:00:00 AM (UTC+0)
    assert.equal(navbar_alerts.should_show_bankruptcy_banner(), false);

    // Don't show bankruptcy banner if user has less <= 500 unread messages.
    override(unread, "get_unread_message_count", () => 500);
    assert.equal(navbar_alerts.should_show_bankruptcy_banner(), false);
});

test("should_show_organization_profile_incomplete_banner", ({override}) => {
    // Show organization profile incomplete banner when following conditions are suitable:
    // - The user is an admin.
    // - The organization is created >= 15 days ago.
    override(current_user, "is_admin", true);
    const start_time = new Date("2024-01-01T10:00:00.000Z"); // Wednesday 1/1/2024 10:00:00 AM (UTC+0)
    override(realm, "realm_date_created", start_time.getTime() / 1000);
    override(Date, "now", () => addDays(start_time, 15).getTime());
    assert.equal(
        navbar_alerts.should_show_organization_profile_incomplete_banner(realm.realm_date_created),
        true,
    );

    // Don't show banner if user is not an admin.
    override(current_user, "is_admin", false);
    assert.equal(
        navbar_alerts.should_show_organization_profile_incomplete_banner(realm.realm_date_created),
        false,
    );
    override(current_user, "is_admin", true);

    // Don't show banner if organization is created < 15 days ago.
    override(Date, "now", () => addDays(start_time, 14).getTime());
    assert.equal(
        navbar_alerts.should_show_organization_profile_incomplete_banner(realm.realm_date_created),
        false,
    );
});

test("is_organization_profile_incomplete", ({override}) => {
    // The organization profile is incomplete when the realm description is
    // empty or not updated after importing the organization from other product.
    override(realm, "realm_description", "Organization imported from Slack!");
    assert.equal(navbar_alerts.is_organization_profile_incomplete(), true);
    override(realm, "realm_description", "");
    assert.equal(navbar_alerts.is_organization_profile_incomplete(), true);

    // The organization profile is complete if the realm description is updated.
    override(realm, "realm_description", "Organization description already set!");
    assert.equal(navbar_alerts.is_organization_profile_incomplete(), false);
});

test("should_show_server_upgrade_banner", ({override}) => {
    const ls = localstorage();

    // Set the initial date, which will be set as the last upgrade nag dismissal time.
    const start_time = new Date("2024-01-01T10:00:00.000Z"); // Wednesday 1/1/2024 10:00:00 AM (UTC+0)
    override(Date, "now", () => start_time.getTime());
    ls.set("lastUpgradeNagDismissalTime", undefined);
    assert.equal(navbar_alerts.should_show_server_upgrade_banner(ls), true);
    navbar_alerts.set_last_upgrade_nag_dismissal_time(ls);

    // Set the date to <= 7 days from the last upgrade nag dismissal time.
    override(Date, "now", () => addDays(start_time, 7).getTime()); // Wednesday 1/8/2024 10:00:00 AM (UTC+0)
    assert.equal(navbar_alerts.should_show_server_upgrade_banner(ls), false);

    // Set the date to > 7 days from the last upgrade nag dismissal time.
    override(Date, "now", () => addDays(start_time, 8).getTime()); // Thursday 1/9/2024 10:00:00 AM (UTC+0)
    assert.equal(navbar_alerts.should_show_server_upgrade_banner(ls), true);
});
