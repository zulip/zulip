import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function test_add_linkifier(page: Page): Promise<void> {
    await page.waitForSelector(".admin-linkifier-form", {visible: true});
    await common.fill_form(page, "form.admin-linkifier-form", {
        pattern: "#(?P<id>[0-9]+)",
        url_template: "https://trac.example.com/ticket/{id}",
    });
    await page.click("form.admin-linkifier-form button.button");

    const admin_linkifier_status_selector = "div#admin-linkifier-status";
    await page.waitForSelector(admin_linkifier_status_selector, {visible: true});
    const admin_linkifier_status = await common.get_text_from_selector(
        page,
        admin_linkifier_status_selector,
    );
    assert.strictEqual(admin_linkifier_status, "Custom linkifier added!");

    await page.waitForSelector(".linkifier_row:nth-child(4)", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row:nth-child(4) span.linkifier_pattern",
        ),
        "#(?P<id>[0-9]+)",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row:nth-child(4) span.linkifier_url_template",
        ),
        "https://trac.example.com/ticket/{id}",
    );
}

async function test_delete_linkifier(page: Page): Promise<void> {
    await page.waitForFunction(() => document.querySelectorAll(".linkifier_row").length === 4);
    await page.click(".linkifier_row:nth-last-child(1) .delete");
    await common.wait_for_micromodal_to_open(page);
    await page.click("#confirm_delete_linkifiers_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
    await page.waitForFunction(() => document.querySelectorAll(".linkifier_row").length === 3);
}

async function test_add_invalid_linkifier_pattern(page: Page): Promise<void> {
    await page.waitForSelector(".admin-linkifier-form", {visible: true});
    await common.fill_form(page, "form.admin-linkifier-form", {
        pattern: "(foo",
        url_template: "https://trac.example.com/ticket/{id}",
    });
    await page.click("form.admin-linkifier-form button.button");

    await page.waitForSelector("div#admin-linkifier-status", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-linkifier-status"),
        "Failed: Bad regular expression: missing ): (foo",
    );
}

async function test_edit_linkifier(page: Page): Promise<void> {
    await page.click(".linkifier_row:nth-last-child(1) .edit");
    await common.wait_for_micromodal_to_open(page);
    await common.fill_form(page, "form.linkifier-edit-form", {
        pattern: "(?P<num>[0-9a-f]{40})",
        url_template: "https://trac.example.com/commit/{num}",
    });
    await page.click(".dialog_submit_button");

    await page.waitForSelector("#dialog_widget_modal", {hidden: true});
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(".linkifier_row:nth-last-child(1)", {visible: true});
    await page.waitForFunction(
        () =>
            document.querySelector(".linkifier_row:nth-last-child(1) span.linkifier_pattern")
                ?.textContent === "(?P<num>[0-9a-f]{40})",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row:nth-last-child(1) span.linkifier_url_template",
        ),
        "https://trac.example.com/commit/{num}",
    );
}

async function test_edit_invalid_linkifier(page: Page): Promise<void> {
    await page.click(".linkifier_row:nth-last-child(1) .edit");
    await common.wait_for_micromodal_to_open(page);
    await common.fill_form(page, "form.linkifier-edit-form", {
        pattern: "#(?P<id>d????)",
        url_template: "{id",
    });
    await page.click(".dialog_submit_button");

    const edit_linkifier_pattern_status_selector = "div#dialog_error";
    await page.waitForSelector(edit_linkifier_pattern_status_selector, {visible: true});
    const edit_linkifier_pattern_status = await common.get_text_from_selector(
        page,
        edit_linkifier_pattern_status_selector,
    );
    assert.strictEqual(
        edit_linkifier_pattern_status,
        "Failed: Bad regular expression: bad repetition operator: ????",
    );

    const edit_linkifier_template_status_selector = "div#edit-linkifier-template-status";
    await page.waitForSelector(edit_linkifier_template_status_selector, {visible: true});
    const edit_linkifier_template_status = await common.get_text_from_selector(
        page,
        edit_linkifier_template_status_selector,
    );
    assert.strictEqual(edit_linkifier_template_status, "Failed: Invalid URL template.");

    await page.click(".dialog_exit_button");
    await page.waitForSelector("#dialog_widget_modal", {hidden: true});

    await page.waitForSelector(".linkifier_row:nth-last-child(1)", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row:nth-last-child(1) span.linkifier_pattern",
        ),
        "(?P<num>[0-9a-f]{40})",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row:nth-last-child(1) span.linkifier_url_template",
        ),
        "https://trac.example.com/commit/{num}",
    );
}

async function linkifier_test(page: Page): Promise<void> {
    await common.log_in(page);
    await common.manage_organization(page);
    await page.click("li[data-section='linkifier-settings']");

    await test_add_linkifier(page);
    await test_edit_linkifier(page);
    await test_edit_invalid_linkifier(page);
    await test_add_invalid_linkifier_pattern(page);
    await test_delete_linkifier(page);
}

common.run_test(linkifier_test);
