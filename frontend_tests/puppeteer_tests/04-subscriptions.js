"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function user_checkbox(page, name) {
    const user_id = await common.get_user_id_from_name(page, name);
    return `#user-checkboxes [data-user-id="${user_id}"]`;
}

async function user_span(page, name) {
    return (await user_checkbox(page, name)) + " input ~ span";
}

async function stream_checkbox(page, stream_name) {
    const stream_id = await common.get_stream_id(page, stream_name);
    return `#stream-checkboxes [data-stream-id="${stream_id}"]`;
}

async function stream_span(page, stream_name) {
    return (await stream_checkbox(page, stream_name)) + " input ~ span";
}

async function wait_for_checked(page, user_name, is_checked) {
    const selector = await user_checkbox(page, user_name);
    await page.waitForFunction(
        (selector, is_checked) => $(selector).find("input")[0].checked === is_checked,
        {},
        selector,
        is_checked,
    );
}

async function stream_name_error(page) {
    await page.waitForSelector("#stream_name_error", {visible: true});
    return await common.get_text_from_selector(page, "#stream_name_error");
}

async function open_streams_modal(page) {
    const all_streams_selector = 'a[href="#streams/all"]';
    await page.waitForSelector(all_streams_selector, {visible: true});
    await page.click(all_streams_selector);

    await page.waitForSelector("#subscription_overlay.new-style", {visible: true});
    assert(page.url().includes("#streams/all"));
}

async function test_subscription_button_verona_stream(page) {
    const verona_subscribed_selector = "[data-stream-name='Verona'] .sub_unsub_button.checked";
    const verona_unsubscribed_selector =
        "[data-stream-name='Verona'] .sub_unsub_button:not(.checked)";
    // assert it's already checked.
    await page.waitForSelector(verona_subscribed_selector, {visible: true});
    // get subscribe/unsubscribe button element.
    const subscription_checkmark = await page.$("[data-stream-name='Verona'] .sub_unsub_button");
    await subscription_checkmark.click(); // Unsubscribe.
    await page.waitForSelector(verona_unsubscribed_selector); // Unsubscribed.
    await subscription_checkmark.click(); // Subscribe again now.
    await page.waitForSelector(verona_subscribed_selector, {visible: true}); // Subscribed.
}

async function click_create_new_stream(page, cordelia_checkbox, othello_checkbox) {
    await page.click("#add_new_subscription .create_stream_button");
    await page.waitForSelector(cordelia_checkbox, {visible: true});
    await page.waitForSelector(othello_checkbox, {visible: true});
}

async function open_copy_from_stream_dropdown(page, scotland_checkbox, rome_checkbox) {
    await page.click("#copy-from-stream-expand-collapse .control-label");
    await page.waitForSelector(scotland_checkbox, {visible: true});
    await page.waitForSelector(rome_checkbox, {visible: true});
}

async function test_check_all_only_affects_visible_users(page) {
    await page.click(".subs_set_all_users");
    await wait_for_checked(page, "cordelia", false);
    await wait_for_checked(page, "othello", true);
}

async function test_uncheck_all(page) {
    await page.click(".subs_unset_all_users");
    await wait_for_checked(page, "othello", false);
}

async function clear_ot_filter_with_backspace(page) {
    await page.click(".add-user-list-filter");
    await page.keyboard.press("Backspace");
    await page.keyboard.press("Backspace");
}

async function verify_filtered_users_are_visible_again(page, cordelia_checkbox, othello_checkbox) {
    await page.waitForSelector(cordelia_checkbox, {visible: true});
    await page.waitForSelector(othello_checkbox, {visible: true});
}

async function test_user_filter_ui(
    page,
    cordelia_checkbox,
    othello_checkbox,
    scotland_checkbox,
    rome_checkbox,
) {
    await page.waitForSelector("form#stream_creation_form", {visible: true});

    await common.fill_form(page, "form#stream_creation_form", {user_list_filter: "ot"});
    await page.waitForSelector("#user-checkboxes", {visible: true});
    await page.waitForSelector(cordelia_checkbox, {hidden: true});
    await page.waitForSelector(othello_checkbox, {visible: true});

    // Filter shouldn't affect streams.
    await page.waitForSelector(scotland_checkbox, {visible: true});
    await page.waitForSelector(rome_checkbox, {visible: true});

    await test_check_all_only_affects_visible_users(page);
    await test_uncheck_all(page);

    await clear_ot_filter_with_backspace(page);
    await verify_filtered_users_are_visible_again(page, cordelia_checkbox, othello_checkbox);
}

async function create_stream(page) {
    await page.waitForXPath('//*[text()="Create stream"]', {visible: true});
    await common.fill_form(page, "form#stream_creation_form", {
        stream_name: "Puppeteer",
        stream_description: "Everything Puppeteer",
    });
    await page.click(await stream_span(page, "Scotland")); //  Subscribes all users from Scotland
    await page.click(await user_span(page, "cordelia")); // Add cordelia.
    await wait_for_checked(page, "cordelia", true);
    await page.click(await user_span(page, "othello")); // Remove othello who was selected from Scotland.
    await wait_for_checked(page, "othello", false);
    await page.click("form#stream_creation_form button.button.sea-green");
    await page.waitForFunction(() => $(".stream-name").is(':contains("Puppeteer")'));
    const stream_name = await common.get_text_from_selector(
        page,
        ".stream-header .stream-name .stream-name-editable",
    );
    const stream_description = await common.get_text_from_selector(
        page,
        ".stream-description-editable ",
    );
    const subscriber_count_selector = "[data-stream-name='Puppeteer'] .subscriber-count";
    assert.strictEqual(stream_name, "Puppeteer");
    assert.strictEqual(stream_description, "Everything Puppeteer");

    // Assert subscriber count becomes 5(scotland(+4), cordelia(+1), othello(-1), Desdemona(+1)).
    await page.waitForFunction(
        (subscriber_count_selector) => $(subscriber_count_selector).text().trim() === "5",
        {},
        subscriber_count_selector,
    );
}

async function test_streams_with_empty_names_cannot_be_created(page) {
    await page.click("#add_new_subscription .create_stream_button");
    await page.waitForSelector("form#stream_creation_form", {visible: true});
    await common.fill_form(page, "form#stream_creation_form", {stream_name: "  "});
    await page.click("form#stream_creation_form button.button.sea-green");
    assert.strictEqual(await stream_name_error(page), "A stream needs to have a name");
}

async function test_streams_with_duplicate_names_cannot_be_created(page) {
    await common.fill_form(page, "form#stream_creation_form", {stream_name: "Puppeteer"});
    await page.click("form#stream_creation_form button.button.sea-green");
    assert.strictEqual(await stream_name_error(page), "A stream with this name already exists");

    const cancel_button_selector = "form#stream_creation_form button.button.white";
    await page.click(cancel_button_selector);
}

async function test_stream_creation(page) {
    const cordelia_checkbox = await user_checkbox(page, "cordelia");
    const othello_checkbox = await user_checkbox(page, "othello");
    const scotland_checkbox = await stream_checkbox(page, "Scotland");
    const rome_checkbox = await stream_checkbox(page, "Rome");

    await click_create_new_stream(page, cordelia_checkbox, othello_checkbox);
    await open_copy_from_stream_dropdown(page, scotland_checkbox, rome_checkbox);
    await test_user_filter_ui(
        page,
        cordelia_checkbox,
        othello_checkbox,
        scotland_checkbox,
        rome_checkbox,
    );
    await create_stream(page);
    await test_streams_with_empty_names_cannot_be_created(page);
    await test_streams_with_duplicate_names_cannot_be_created(page);
}

async function test_streams_search_feature(page) {
    assert.strictEqual(await common.get_text_from_selector(page, "#search_stream_name"), "");
    const hidden_streams_selector = ".stream-row.notdisplayed .stream-name";
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            '.stream-row[data-stream-name="Verona"] .stream-name',
        ),
        "Verona",
    );
    assert(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is hidden",
    );

    await page.type('#stream_filter input[type="text"]', "Puppeteer");
    assert.strictEqual(
        await common.get_text_from_selector(page, ".stream-row:not(.notdisplayed) .stream-name"),
        "Puppeteer",
    );
    assert(
        (await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is not hidden",
    );
    assert(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("Puppeteer"),
        "Puppeteer is hidden after searching.",
    );
}

async function subscriptions_tests(page) {
    await common.log_in(page);
    await open_streams_modal(page);
    await test_subscription_button_verona_stream(page);
    await test_stream_creation(page);
    await test_streams_search_feature(page);
}

common.run_test(subscriptions_tests);
