"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const settings_data = zrequire("settings_data");
const settings_config = zrequire("settings_config");

set_global("page_params", {});

/*
    Some methods in settings_data are fairly
    trivial, so the meaningful tests happen
    at the higher layers, such as when we
    test people.js.
*/

const isaac = {
    email: "isaac@example.com",
    delivery_email: "isaac-delivery@example.com",
};

run_test("email_for_user_settings", () => {
    const email = settings_data.email_for_user_settings;

    page_params.realm_email_address_visibility =
        settings_config.email_address_visibility_values.admins_only.code;
    assert.equal(email(isaac), undefined);

    page_params.is_admin = true;
    assert.equal(email(isaac), isaac.delivery_email);

    page_params.realm_email_address_visibility =
        settings_config.email_address_visibility_values.nobody.code;
    assert.equal(email(isaac), undefined);

    page_params.is_admin = false;
    assert.equal(email(isaac), undefined);

    page_params.realm_email_address_visibility =
        settings_config.email_address_visibility_values.everyone.code;
    assert.equal(email(isaac), isaac.email);
});

run_test("user_can_change_logo", () => {
    const can_change_logo = settings_data.user_can_change_logo;

    page_params.is_admin = true;
    page_params.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), true);

    page_params.is_admin = false;
    page_params.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    page_params.is_admin = true;
    page_params.zulip_plan_is_not_limited = false;
    assert.equal(can_change_logo(), false);

    page_params.is_admin = false;
    page_params.zulip_plan_is_not_limited = true;
    assert.equal(can_change_logo(), false);
});
