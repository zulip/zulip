import {strict as assert} from "assert";

import type {ElementHandle, Page} from "puppeteer";

import * as common from "./lib/common";

async function submit_notifications_stream_settings(page: Page): Promise<void> {
    await page.waitForSelector('#org-notifications .save-button[data-status="unsaved"]', {
        visible: true,
    });

    const save_button = "#org-notifications .save-button";
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button has incorrect text.",
    );
    await page.click(save_button);

    await page.waitForSelector('#org-notifications .save-button[data-status="saved"]', {
        visible: true,
    });
    assert.strictEqual(
        await common.get_text_from_selector(page, "#org-notifications .save-button"),
        "Saved",
        "Saved text didn't appear after saving new stream notifications setting",
    );

    await page.waitForSelector("#org-notifications .save-button", {hidden: true});
}

async function test_change_new_stream_notifications_setting(page: Page): Promise<void> {
    await page.click("#realm_notifications_stream_id_widget.dropdown-widget-button");
    await page.waitForSelector(".dropdown-list-container", {
        visible: true,
    });

    await page.type(".dropdown-list-search-input", "rome");

    const rome_in_dropdown = await page.waitForSelector(
        `xpath///*[${common.has_class_x("list-item")}][normalize-space()="Rome"]`,
        {visible: true},
    );
    assert.ok(rome_in_dropdown);
    await rome_in_dropdown.click();

    await submit_notifications_stream_settings(page);
}

async function test_change_signup_notifications_stream(page: Page): Promise<void> {
    console.log('Changing signup notifications stream to Verona by filtering with "verona"');

    await page.click("#realm_signup_notifications_stream_id_widget");
    await page.waitForSelector(".dropdown-list-search-input", {visible: true});

    await page.type(".dropdown-list-search-input", "verona");
    await page.waitForSelector(".dropdown-list .list-item", {visible: true});
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await submit_notifications_stream_settings(page);
}

async function test_permissions_change_save_worked(page: Page): Promise<void> {
    const saved_status = '#org-stream-permissions .save-button[data-status="saved"]';
    await page.waitForSelector(saved_status, {
        visible: true,
    });
    await page.waitForSelector(saved_status, {hidden: true});
}

async function submit_stream_permissions_change(page: Page): Promise<void> {
    const save_button = "#org-stream-permissions .save-button";
    await page.waitForSelector(save_button, {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button didn't appear for permissions change.",
    );
    await page.click(save_button);

    await test_permissions_change_save_worked(page);
}

async function test_changing_create_streams_and_invite_to_stream_policies(
    page: Page,
): Promise<void> {
    const policies = {
        "create private stream": "#id_realm_create_private_stream_policy",
        "create public stream": "#id_realm_create_public_stream_policy",
        "invite to stream": "#id_realm_invite_to_stream_policy",
    };
    const policy_values = {
        "admins only": 2,
        "members and admins": 1,
        "full members": 3,
    };

    for (const [policy, selector] of Object.entries(policies)) {
        for (const [policy_value_name, policy_value] of Object.entries(policy_values)) {
            console.log(`Test setting ${policy} policy to '${policy_value_name}'.`);
            await page.waitForSelector(selector, {visible: true});
            await page.select(selector, `${policy_value}`);
            await submit_stream_permissions_change(page);
        }
    }
}

async function test_save_joining_organization_change_worked(page: Page): Promise<void> {
    const saved_status = '#org-join-settings .save-button[data-status="saved"]';
    await page.waitForSelector(saved_status, {
        visible: true,
    });
    await page.waitForSelector(saved_status, {hidden: true});
}

async function submit_joining_organization_change(page: Page): Promise<void> {
    const save_button = "#org-join-settings .save-button";
    await page.waitForSelector(save_button, {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button didn't appear for permissions change.",
    );
    await page.waitForSelector(save_button, {visible: true});
    await page.click(save_button);

    await test_save_joining_organization_change_worked(page);
}

async function test_set_new_user_threshold_to_three_days(page: Page): Promise<void> {
    console.log("Test setting new user threshold to three days.");
    await page.waitForSelector("#id_realm_waiting_period_threshold", {visible: true});
    await page.select("#id_realm_waiting_period_threshold", "3");
    await submit_joining_organization_change(page);
}

async function test_set_new_user_threshold_to_N_days(page: Page): Promise<void> {
    console.log("Test setting new user threshold to N days.");
    await page.waitForSelector("#id_realm_waiting_period_threshold", {visible: true});
    await page.select("#id_realm_waiting_period_threshold", "custom_period");

    const N = "10";
    await common.clear_and_type(page, "#id_realm_waiting_period_threshold_custom_input", N);
    await submit_joining_organization_change(page);
}

async function test_organization_permissions(page: Page): Promise<void> {
    await page.click("li[data-section='organization-permissions']");

    await test_changing_create_streams_and_invite_to_stream_policies(page);

    await test_set_new_user_threshold_to_three_days(page);
    await test_set_new_user_threshold_to_N_days(page);
}

async function test_add_emoji(page: Page): Promise<void> {
    await common.fill_form(page, "#add-custom-emoji-form", {name: "zulip logo"});

    const emoji_upload_handle = await page.$("#emoji_file_input");
    assert.ok(emoji_upload_handle);
    await (emoji_upload_handle as ElementHandle<HTMLInputElement>).uploadFile(
        "static/images/logo/zulip-icon-128x128.png",
    );
    await page.click("#add-custom-emoji-modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector("tr#emoji_zulip_logo", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "tr#emoji_zulip_logo .emoji_name"),
        "zulip logo",
        "Emoji name incorrectly saved.",
    );
    await page.waitForSelector("tr#emoji_zulip_logo img", {visible: true});
}

async function test_delete_emoji(page: Page): Promise<void> {
    await page.click("tr#emoji_zulip_logo button.delete");

    await common.wait_for_micromodal_to_open(page);
    await page.click("#confirm_deactivate_custom_emoji_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    // assert the emoji is deleted.
    await page.waitForSelector("tr#emoji_zulip_logo", {hidden: true});
}

async function test_custom_realm_emoji(page: Page): Promise<void> {
    await page.click("li[data-section='emoji-settings']");
    await page.click("#add-custom-emoji-button");
    await common.wait_for_micromodal_to_open(page);

    await test_add_emoji(page);
    await test_delete_emoji(page);
}

async function test_add_default_stream(page: Page): Promise<void> {
    const streams = ["Denmark", "Venice"];
    for (let i = 0; i < 2; i += 1) {
        await page.click(`#select_default_stream_${i}_widget`);
        await page.waitForSelector(".dropdown-list-container .list-item", {
            visible: true,
        });

        const stream_to_select = `.dropdown-list-container .list-item[data-name="${streams[i]}"]`;
        await page.waitForSelector(stream_to_select, {visible: true});
        await page.click(stream_to_select);
        assert((await page.$(".dropdown-list-container")) === null);
    }

    await page.click("#add-default-stream-modal .dialog_submit_button");

    await common.wait_for_micromodal_to_close(page);

    let stream_id = await common.get_stream_id(page, "Denmark");
    let row = `.default_stream_row[data-stream-id='${CSS.escape(stream_id.toString())}']`;
    await page.waitForSelector(row, {visible: true});

    stream_id = await common.get_stream_id(page, "Venice");
    row = `.default_stream_row[data-stream-id='${CSS.escape(stream_id.toString())}']`;
    await page.waitForSelector(row, {visible: true});
}

async function test_remove_default_stream(page: Page, row: string): Promise<void> {
    await page.click(row + " button.remove-default-stream");

    // assert row doesn't exist.
    await page.waitForSelector(row, {hidden: true});
}

async function test_default_streams(page: Page): Promise<void> {
    await page.click("li[data-section='default-streams-list']");
    await page.click("#show-add-default-streams-modal");
    await common.wait_for_micromodal_to_open(page);

    const stream_name = "Denmark";
    const stream_id = await common.get_stream_id(page, stream_name);
    const row = `.default_stream_row[data-stream-id='${CSS.escape(stream_id.toString())}']`;

    await test_add_default_stream(page);
    await test_remove_default_stream(page, row);
}

async function test_upload_realm_icon_image(page: Page): Promise<void> {
    const upload_handle = await page.$("#realm-icon-upload-widget .image_file_input");
    assert.ok(upload_handle);
    await (upload_handle as ElementHandle<HTMLInputElement>).uploadFile(
        "static/images/logo/zulip-icon-128x128.png",
    );

    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        visible: true,
    });
    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        hidden: true,
    });
    await page.waitForSelector(
        '#realm-icon-upload-widget .image-block[src^="/user_avatars/2/realm/icon.png?version=2"]',
        {visible: true},
    );
}

async function delete_realm_icon(page: Page): Promise<void> {
    await page.click("li[data-section='organization-profile']");
    await page.click("#realm-icon-upload-widget .image-delete-button");

    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});
}

async function test_organization_profile(page: Page): Promise<void> {
    await page.click("li[data-section='organization-profile']");
    const gravatar_selctor =
        '#realm-icon-upload-widget .image-block[src^="https://secure.gravatar.com/avatar/"]';
    await page.waitForSelector(gravatar_selctor, {visible: true});
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});

    await test_upload_realm_icon_image(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: true});

    await delete_realm_icon(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});
    await page.waitForSelector(gravatar_selctor, {visible: true});
}

async function test_authentication_methods(page: Page): Promise<void> {
    await page.click("li[data-section='auth-methods']");
    await page.waitForSelector(".method_row[data-method='Google'] input[type='checkbox'] + span", {
        visible: true,
    });

    await page.click(".method_row[data-method='Google'] input[type='checkbox'] + span");
    const save_button = "#org-auth_settings .save-button";
    assert.strictEqual(await common.get_text_from_selector(page, save_button), "Save changes");
    await page.click(save_button);

    // Leave the page and return.
    const settings_dropdown = "#settings-dropdown";
    await page.click(settings_dropdown);

    await common.manage_organization(page);
    await page.click("li[data-section='auth-methods']");

    // Test setting was saved.
    await page.waitForSelector(".method_row[data-method='Google'] input[type='checkbox'] + span", {
        visible: true,
    });
    await page.waitForSelector(
        ".method_row[data-method='Google'] input[type='checkbox']:not(:checked)",
    );
}

async function admin_test(page: Page): Promise<void> {
    await common.log_in(page);

    await common.manage_organization(page);
    await test_change_new_stream_notifications_setting(page);
    await test_change_signup_notifications_stream(page);

    await test_organization_permissions(page);
    // Currently, Firefox (with puppeteer) does not support file upload:
    //    https://github.com/puppeteer/puppeteer/issues/6688.
    // Until that is resolved upstream, we need to skip the tests that involve
    // doing file upload on Firefox.
    if (!common.is_firefox) {
        await test_custom_realm_emoji(page);
        await test_organization_profile(page);
    }
    await test_default_streams(page);
    await test_authentication_methods(page);
}

common.run_test(admin_test);
