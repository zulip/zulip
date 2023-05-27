import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

type Playground = {
    playground_name: string;
    pygments_language: string;
    url_template: string;
};

async function _add_playground_and_return_status(page: Page, payload: Playground): Promise<string> {
    await page.waitForSelector(".admin-playground-form", {visible: true});
    // Let's first ensure that the success/failure status from an earlier step has disappeared.
    const admin_playground_status_selector = "div#admin-playground-status";
    await page.waitForSelector(admin_playground_status_selector, {hidden: true});

    // Now we can fill and click the submit button.
    await common.fill_form(page, "form.admin-playground-form", payload);
    // Not sure why, but page.click() doesn't seem to always click the submit button.
    // So we resort to using eval with the button ID instead.
    await page.$eval("#submit_playground_button", (el) => (el as HTMLInputElement).click());

    // We return the success/failure status message back to the caller.
    await page.waitForSelector(admin_playground_status_selector, {visible: true});
    const admin_playground_status = await common.get_text_from_selector(
        page,
        admin_playground_status_selector,
    );
    return admin_playground_status;
}

async function test_successful_playground_creation(page: Page): Promise<void> {
    const payload = {
        pygments_language: "Python",
        playground_name: "Python3 playground",
        url_template: "https://python.example.com?code={code}",
    };
    const status = await _add_playground_and_return_status(page, payload);
    assert.strictEqual(status, "Custom playground added!");
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
    const payload = {
        pygments_language: "Python",
        playground_name: "Python3 playground",
        url_template: "not_a_url_template{",
    };
    let status = await _add_playground_and_return_status(page, payload);
    assert.strictEqual(status, "Failed: Invalid URL template.");

    payload.url_template = "https://python.example.com?code={code}";
    payload.pygments_language = "py!@%&";
    status = await _add_playground_and_return_status(page, payload);
    assert.strictEqual(status, "Failed: Invalid characters in pygments language");
}

async function test_successful_playground_deletion(page: Page): Promise<void> {
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

common.run_test(playground_test);
