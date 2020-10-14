"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

// These will be the row and edit form of the the custom profile we add.
const profile_field_row = "#admin_profile_fields_table tr:nth-last-child(2)";
const profile_field_form = "#admin_profile_fields_table tr:nth-last-child(1)";

async function test_add_new_profile_field(page) {
    await page.waitForSelector(".admin-profile-field-form", {visible: true});
    await common.fill_form(page, "form.admin-profile-field-form", {
        name: "Teams",
        field_type: "1",
    });
    await page.click("form.admin-profile-field-form button[type='submit']");

    await page.waitForSelector("#admin-add-profile-field-status img", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-add-profile-field-status"),
        "Saved",
    );
    await common.wait_for_text(page, `${profile_field_row} span.profile_field_name`, "Teams");
    assert.strictEqual(
        await common.get_text_from_selector(page, `${profile_field_row} span.profile_field_type`),
        "Short text",
    );
}

async function test_edit_profile_field(page) {
    await page.click(`${profile_field_row} button.open-edit-form`);
    await page.waitForSelector(`${profile_field_form} form.name-setting`, {visible: true});
    await common.fill_form(page, `${profile_field_form} form.name-setting`, {
        name: "team",
    });
    await page.click(`${profile_field_form} button.submit`);

    await page.waitForSelector("#admin-profile-field-status img", {visible: true});
    await common.wait_for_text(page, `${profile_field_row} span.profile_field_name`, "team");
    assert.strictEqual(
        await common.get_text_from_selector(page, `${profile_field_row} span.profile_field_type`),
        "Short text",
    );
}

async function test_delete_custom_profile_field(page) {
    await page.click(`${profile_field_row} button.delete`);
    await page.waitForSelector("#admin-profile-field-status img", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-profile-field-status"),
        "Saved",
    );
}

async function test_custom_profile(page) {
    await common.log_in(page);
    await common.manage_organization(page);

    console.log("Testing custom profile fields");
    await page.click("li[data-section='profile-field-settings']");

    await test_add_new_profile_field(page);
    await test_edit_profile_field(page);
    await test_delete_custom_profile_field(page);

    await common.log_out(page);
}

common.run_test(test_custom_profile);
