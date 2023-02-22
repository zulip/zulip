import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

// This will be the row of the the custom profile field we add.
const profile_field_row = "#admin_profile_fields_table tr:nth-last-child(1)";

async function test_add_new_profile_field(page: Page): Promise<void> {
    await page.click("#add-custom-profile-field-btn");
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Add a new custom profile field",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Add",
    );
    await page.waitForSelector(".admin-profile-field-form", {visible: true});
    await common.fill_form(page, "form.admin-profile-field-form", {
        field_type: "1",
        name: "Teams",
    });
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(
        'xpath///*[@id="admin_profile_fields_table"]//tr[last()]/td[normalize-space()="Teams"]',
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, `${profile_field_row} span.profile_field_type`),
        "Short text",
    );
}

async function test_edit_profile_field(page: Page): Promise<void> {
    await page.click(`${profile_field_row} button.open-edit-form-modal`);
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Edit custom profile field",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Save changes",
    );
    await common.fill_form(page, "form.name-setting", {
        name: "team",
    });
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(
        'xpath///*[@id="admin_profile_fields_table"]//tr[last()]/td[normalize-space()="team"]',
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, `${profile_field_row} span.profile_field_type`),
        "Short text",
    );
}

async function test_delete_custom_profile_field(page: Page): Promise<void> {
    await page.click(`${profile_field_row} button.delete`);
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Delete custom profile field?",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Confirm",
    );
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector("#admin-profile-field-status img", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-profile-field-status"),
        "Saved",
    );
}

async function test_custom_profile(page: Page): Promise<void> {
    await common.log_in(page);
    await common.manage_organization(page);

    console.log("Testing custom profile fields");
    await page.click("li[data-section='profile-field-settings']");

    await test_add_new_profile_field(page);
    await test_edit_profile_field(page);
    await test_delete_custom_profile_field(page);
}

common.run_test(test_custom_profile);
