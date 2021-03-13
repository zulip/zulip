import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function test_add_linkifier(page: Page): Promise<void> {
    await page.waitForSelector(".admin-linkifier-form", {visible: true});
    await common.fill_form(page, "form.admin-linkifier-form", {
        pattern: "#(?P<id>[0-9]+)",
        url_format_string: "https://trac.example.com/ticket/%(id)s",
    });
    await page.click("form.admin-linkifier-form button.button");

    const admin_linkifier_status_selector = "div#admin-linkifier-status";
    await page.waitForSelector(admin_linkifier_status_selector, {visible: true});
    const admin_linkifier_status = await common.get_text_from_selector(
        page,
        admin_linkifier_status_selector,
    );
    assert.strictEqual(admin_linkifier_status, "Custom linkifier added!");

    await page.waitForSelector(".linkifier_row", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".linkifier_row span.linkifier_pattern"),
        "#(?P<id>[0-9]+)",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".linkifier_row span.linkifier_url_format_string",
        ),
        "https://trac.example.com/ticket/%(id)s",
    );
}

async function test_delete_linkifier(page: Page): Promise<void> {
    await page.click(".linkifier_row button");
    await page.waitForSelector(".linkifier_row", {hidden: true});
}

async function test_invalid_linkifier_pattern(page: Page): Promise<void> {
    await page.waitForSelector(".admin-linkifier-form", {visible: true});
    await common.fill_form(page, "form.admin-linkifier-form", {
        pattern: "a$",
        url_format_string: "https://trac.example.com/ticket/%(id)s",
    });
    await page.click("form.admin-linkifier-form button.button");

    await page.waitForSelector("div#admin-linkifier-pattern-status", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-linkifier-pattern-status"),
        "Failed: Invalid filter pattern.  Valid characters are [ a-zA-Z_#=/:+!-].",
    );
}

async function linkifier_test(page: Page): Promise<void> {
    await common.log_in(page);
    await common.manage_organization(page);
    await page.click("li[data-section='linkifier-settings']");

    await test_add_linkifier(page);
    await test_delete_linkifier(page);
    await test_invalid_linkifier_pattern(page);

    await common.log_out(page);
}

common.run_test(linkifier_test);
