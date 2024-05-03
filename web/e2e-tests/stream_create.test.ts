import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function user_row_selector(page: Page, name: string): Promise<string> {
    const user_id = await common.get_user_id_from_name(page, name);
    const selector = `.remove_potential_subscriber[data-user-id="${user_id}"]`;
    return selector;
}

async function await_user_visible(page: Page, name: string): Promise<void> {
    const selector = await user_row_selector(page, name);
    await page.waitForSelector(selector, {visible: true});
}

async function await_user_hidden(page: Page, name: string): Promise<void> {
    const selector = await user_row_selector(page, name);
    await page.waitForSelector(selector, {hidden: true});
}

async function add_user_to_stream(page: Page, name: string): Promise<void> {
    const user_id = await common.get_user_id_from_name(page, name);
    await page.evaluate((user_id) => {
        zulip_test.add_user_id_to_new_stream(user_id);
    }, user_id);
    await await_user_visible(page, name);
}

async function stream_name_error(page: Page): Promise<string> {
    await page.waitForSelector("#stream_name_error", {visible: true});
    return await common.get_text_from_selector(page, "#stream_name_error");
}

async function click_create_new_stream(page: Page): Promise<void> {
    await page.click("#add_new_subscription .create_stream_button");
    await page.waitForSelector(".finalize_create_stream", {visible: true});

    // sanity check that desdemona is the initial subsscriber
    await await_user_visible(page, "desdemona");
}

async function clear_ot_filter_with_backspace(page: Page): Promise<void> {
    await page.click(".add-user-list-filter");
    await page.keyboard.press("Backspace");
    await page.keyboard.press("Backspace");
}

async function test_user_filter_ui(page: Page): Promise<void> {
    await page.waitForSelector("form#stream_creation_form", {visible: true});
    // Desdemona should be there by default
    await await_user_visible(page, "desdemona");

    await add_user_to_stream(page, "cordelia");
    await add_user_to_stream(page, "othello");

    await page.type(`form#stream_creation_form [name="user_list_filter"]`, "ot", {delay: 100});
    await page.waitForSelector("#create_stream_subscribers", {visible: true});
    // Wait until filtering is completed.
    await page.waitForFunction(
        () =>
            document.querySelectorAll("#create_stream_subscribers .remove_potential_subscriber")
                .length === 1,
    );

    await await_user_hidden(page, "cordelia");
    await await_user_hidden(page, "desdemona");
    await await_user_visible(page, "othello");

    // Clear the filter.
    await clear_ot_filter_with_backspace(page);

    await await_user_visible(page, "cordelia");
    await await_user_visible(page, "desdemona");
    await await_user_visible(page, "othello");
}

async function create_stream(page: Page): Promise<void> {
    await page.waitForSelector('xpath///*[text()="Create channel"]', {visible: true});
    await common.fill_form(page, "form#stream_creation_form", {
        stream_name: "Puppeteer",
        stream_description: "Everything Puppeteer",
    });
    await page.click("form#stream_creation_form .finalize_create_stream");
    // an explanatory modal is shown for the first stream created
    await common.wait_for_micromodal_to_open(page);
    await page.click(".dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
    await page.waitForSelector(".message-header-stream-settings-button");
    await page.click(".message-header-stream-settings-button");
    await page.waitForSelector(".stream_section");
    await page.waitForSelector(
        `xpath///*[${common.has_class_x("stream-name")} and text()="Puppeteer"]`,
    );
    const stream_name = await common.get_text_from_selector(
        page,
        ".stream-header .stream-name .sub-stream-name",
    );
    const stream_description = await common.get_text_from_selector(
        page,
        ".stream-description .sub-stream-description",
    );
    assert.strictEqual(stream_name, "Puppeteer");
    assert.strictEqual(stream_description, "Everything Puppeteer");

    // Assert subscriber count becomes 3 (cordelia, desdemona, othello)
    await page.waitForSelector(
        `xpath///*[@data-stream-name="Puppeteer"]//*[${common.has_class_x(
            "subscriber-count",
        )} and normalize-space()="3"]`,
    );
}

async function test_streams_with_empty_names_cannot_be_created(page: Page): Promise<void> {
    await page.click("#add_new_subscription .create_stream_button");
    await page.waitForSelector("form#stream_creation_form", {visible: true});
    await common.fill_form(page, "form#stream_creation_form", {stream_name: "  "});
    await page.click("form#stream_creation_form button.finalize_create_stream");
    assert.strictEqual(await stream_name_error(page), "Choose a name for the new channel.");
}

async function test_streams_with_duplicate_names_cannot_be_created(page: Page): Promise<void> {
    await common.fill_form(page, "form#stream_creation_form", {stream_name: "Puppeteer"});
    await page.click("form#stream_creation_form button.finalize_create_stream");
    assert.strictEqual(await stream_name_error(page), "A channel with this name already exists.");

    const cancel_button_selector = "form#stream_creation_form button.button.white";
    await page.click(cancel_button_selector);
}

async function test_stream_creation(page: Page): Promise<void> {
    await click_create_new_stream(page);
    await test_user_filter_ui(page);
    await create_stream(page);
    await test_streams_with_empty_names_cannot_be_created(page);
    await test_streams_with_duplicate_names_cannot_be_created(page);
}

async function test_streams_search_feature(page: Page): Promise<void> {
    assert.strictEqual(await common.get_text_from_selector(page, "#search_stream_name"), "");
    const hidden_streams_selector = ".stream-row.notdisplayed .stream-name";
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            '.stream-row[data-stream-name="Verona"] .stream-name',
        ),
        "Verona",
    );
    assert.ok(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is hidden",
    );

    await page.type('#stream_filter input[type="text"]', "Puppeteer");
    await page.waitForSelector(".stream-row[data-stream-name='core team']", {hidden: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, ".stream-row:not(.notdisplayed) .stream-name"),
        "Puppeteer",
    );
    assert.ok(
        (await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is not hidden",
    );
    assert.ok(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("Puppeteer"),
        "Puppeteer is hidden after searching.",
    );
}

async function subscriptions_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await common.open_streams_modal(page);
    await test_stream_creation(page);
    await test_streams_search_feature(page);
}

common.run_test(subscriptions_tests);
