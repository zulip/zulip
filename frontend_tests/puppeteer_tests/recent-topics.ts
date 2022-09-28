import type {Page} from "puppeteer";

import * as common from "../puppeteer_lib/common";

const include_mute_button_selector = 'button[data-filter="include_muted"]';

async function switch_include_muted_button(page: Page, checked: "true" | "false"): Promise<void> {
    const checkedAttrIncludeMuteButton = await page.$eval(
        include_mute_button_selector,
        (el) => (el as HTMLButtonElement).ariaChecked,
    );
    if (checkedAttrIncludeMuteButton !== checked) {
        await page.click(include_mute_button_selector);
    }
    await page.waitForFunction(
        async (include_mute_button_selector: string) =>
            await page.$eval(
                include_mute_button_selector,
                (el) => (el as HTMLButtonElement).ariaChecked,
            ),
        {},
        include_mute_button_selector,
    );
}

async function click_mute_icon(page: Page): Promise<void> {
    await page.click('#recent_topics_table tr[id^="recent_topic"] > .on_hover_topic_mute');
}

async function click_unmute_icon(page: Page): Promise<void> {
    await page.click('#recent_topics_table tr[id^="recent_topic"] > .on_hover_topic_unmute');
}

async function test_mute_topic(page: Page): Promise<void> {
    await page.waitForSelector("#recent_filters_group", {visible: true});

    await switch_include_muted_button(page, "false");

    await page.waitForSelector('#recent_topics_table tr[id^="recent_topic"]', {visible: true});
    const unmuted_topics_quantity = (await page.$$('#recent_topics_table tr[id^="recent_topic"]'))
        .length;
    if (!unmuted_topics_quantity) {
        throw new Error("cannot find topics");
    }

    await click_mute_icon(page);

    await page.waitForFunction(
        async (expected_length: number) =>
            (await page.$$('#recent_topics_table tr[id^="recent_topic"]')).length ===
            expected_length,
        {},
        unmuted_topics_quantity - 1,
    );
}

async function test_unmute_topic(page: Page): Promise<void> {
    await page.waitForSelector("#recent_filters_group", {visible: true});

    await page.waitForSelector('#recent_topics_table tr[id^="recent_topic"]', {visible: true});
    const unmuted_topics_quantity = (await page.$$('#recent_topics_table tr[id^="recent_topic"]'))
        .length;

    await switch_include_muted_button(page, "true");
    await click_unmute_icon(page);
    await switch_include_muted_button(page, "false");

    await page.waitForFunction(
        async (expected_length: number) =>
            (await page.$$('#recent_topics_table tr[id^="recent_topic"]')).length ===
            expected_length,
        {},
        unmuted_topics_quantity + 1,
    );
}

async function test_recent_topics(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_recent_topics");

    await test_mute_topic(page);
    await test_unmute_topic(page);
}

common.run_test(test_recent_topics);
