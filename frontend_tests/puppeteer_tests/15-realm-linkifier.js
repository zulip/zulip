"use strict";

const assert = require("assert").strict;

const common = require("../puppeteer_lib/common");

async function test_add_linkifier(page) {
    await page.waitForSelector(".admin-filter-form", {visible: true});
    await common.fill_form(page, "form.admin-filter-form", {
        pattern: "#(?P<id>[0-9]+)",
        url_format_string: "https://trac.example.com/ticket/%(id)s",
    });
    await page.click("form.admin-filter-form button.button");

    const admin_filter_status_selector = "div#admin-filter-status";
    await page.waitForSelector(admin_filter_status_selector, {visible: true});
    const admin_filter_status = await common.get_text_from_selector(
        page,
        admin_filter_status_selector,
    );
    assert.strictEqual(admin_filter_status, "Custom filter added!");

    await page.waitForSelector(".filter_row", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".filter_row span.filter_pattern"),
        "#(?P<id>[0-9]+)",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".filter_row span.filter_url_format_string"),
        "https://trac.example.com/ticket/%(id)s",
    );
}

async function test_delete_linkifier(page) {
    await page.click(".filter_row button");
    await page.waitForSelector(".filter_row", {hidden: true});
}

async function test_invalid_linkifier_pattern(page) {
    await page.waitForSelector(".admin-filter-form", {visible: true});
    await common.fill_form(page, "form.admin-filter-form", {
        pattern: "a$",
        url_format_string: "https://trac.example.com/ticket/%(id)s",
    });
    await page.click("form.admin-filter-form button.button");

    await page.waitForSelector("div#admin-filter-pattern-status", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div#admin-filter-pattern-status"),
        "Failed: Invalid filter pattern.  Valid characters are [ a-zA-Z_#=/:+!-].",
    );
}

async function realm_linkifier_test(page) {
    await common.log_in(page);
    await common.manage_organization(page);
    await page.click("li[data-section='filter-settings']");

    await test_add_linkifier(page);
    await test_delete_linkifier(page);
    await test_invalid_linkifier_pattern(page);

    await common.log_out(page);
}

common.run_test(realm_linkifier_test);
