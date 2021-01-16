import {strict as assert} from "assert";

import type {ElementHandle, Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function open_streams_modal(page: Page): Promise<void> {
    const all_streams_selector = "#add-stream-link";
    await page.waitForSelector(all_streams_selector, {visible: true});
    await page.click(all_streams_selector);

    await page.waitForSelector("#subscription_overlay.new-style", {visible: true});
    const url = await common.page_url_with_fragment(page);
    assert(url.includes("#streams/all"));
}

async function test_subscription_button_verona_stream(page: Page): Promise<void> {
    const button_selector = "[data-stream-name='Verona'] .sub_unsub_button";
    const subscribed_selector = `${button_selector}.checked`;
    const unsubscribed_selector = `${button_selector}:not(.checked)`;

    async function subscribed(): Promise<ElementHandle | null> {
        return await page.waitForSelector(subscribed_selector, {visible: true});
    }

    async function unsubscribed(): Promise<ElementHandle | null> {
        return await page.waitForSelector(unsubscribed_selector, {visible: true});
    }

    // Note that we intentionally re-find the button after each click, since
    // the live-update code may replace the whole row.
    let button;

    // We assume Verona is already subscribed, so the first line here
    // should happen immediately.
    button = await subscribed();
    button!.click();
    button = await unsubscribed();
    button!.click();
    button = await subscribed();
    button!.click();
    button = await unsubscribed();
    button!.click();
    button = await subscribed();
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
    assert(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is hidden",
    );

    await page.type('#stream_filter input[type="text"]', "General");
    assert(
        (await common.get_text_from_selector(page, hidden_streams_selector)).includes("Verona"),
        "#Verona is not hidden",
    );
    assert(
        !(await common.get_text_from_selector(page, hidden_streams_selector)).includes("General"),
        "General is hidden after searching.",
    );
}

async function subscriptions_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await open_streams_modal(page);
    await test_subscription_button_verona_stream(page);
    await test_streams_search_feature(page);
}

common.run_test(subscriptions_tests);
