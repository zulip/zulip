import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function test_successful_playground_creation(page: Page): Promise<void> {
    const payload = {
        pygments_language: "Python",
        playground_name: "Python3 playground",
        url_template: "https://python.example.com?code={code}",
    };

    await page.waitForSelector("#add-playground-button", {visible: true});
    await page.click("#add-playground-button");
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector("form.admin-playground-form", {visible: true});

    await common.select_item_via_typeahead(
        page,
        "#playground_pygments_language",
        payload.pygments_language,
        payload.pygments_language,
    );

    await common.fill_form(page, "form.admin-playground-form", {
        playground_name: payload.playground_name,
        url_template: payload.url_template,
    });

    await page.click(".dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    const admin_playground_status_selector = "div#admin-playground-status";
    await page.waitForSelector(admin_playground_status_selector, {visible: true});
    const admin_playground_status = await common.get_text_from_selector(
        page,
        admin_playground_status_selector,
    );
    assert.strictEqual(admin_playground_status, "Custom playground added!");

    await page.waitForSelector(".playground_row", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".playground_row span.playground_pygments_language",
        ),
        "Python",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".playground_row span.playground_name"),
        "Python3 playground",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".playground_row span.playground_url_template"),
        "https://python.example.com?code={code}",
    );
}

async function test_invalid_playground_parameters(page: Page): Promise<void> {
    await page.waitForSelector("#add-playground-button", {visible: true});
    await page.click("#add-playground-button");
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector("form.admin-playground-form", {visible: true});

    await common.select_item_via_typeahead(
        page,
        "#playground_pygments_language",
        "Python",
        "Python",
    );

    await common.fill_form(page, "form.admin-playground-form", {
        playground_name: "Python3 playground",
        url_template: "not_a_url_template{",
    });

    await page.click(".dialog_submit_button");

    await page.waitForSelector("div#dialog_error", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#dialog_error"),
        "Failed: Invalid URL template.",
    );

    await common.fill_form(page, "form.admin-playground-form", {
        url_template: "https://python.example.com?code={code}",
        pygments_language: "py!@%&",
    });
    await page.click(".dialog_submit_button");

    await page.waitForSelector("div#dialog_error", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#dialog_error"),
        "Failed: Invalid character in language: !",
    );

    await page.click(".dialog_exit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function test_successful_playground_deletion(page: Page): Promise<void> {
    await page.waitForSelector(".playground_row button.delete", {visible: true});
    await page.click(".playground_row button.delete");

    await common.wait_for_micromodal_to_open(page);
    await page.click("#confirm_delete_code_playgrounds_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(".playground_row", {hidden: true});
}

async function playground_test(page: Page): Promise<void> {
    await common.log_in(page);
    await common.manage_organization(page);
    await page.click("li[data-section='playground-settings']");

    await test_successful_playground_creation(page);
    await test_invalid_playground_parameters(page);
    await test_successful_playground_deletion(page);
}

await common.run_test(playground_test);
