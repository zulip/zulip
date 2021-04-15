import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

const recent_topic_page = "#recent_topics_view";

// Returns an array based on all text found within the selector passed.
async function get_selector_text(page: Page, selector: string): Promise<string[]> {
    const elements = await page.$$(selector);
    const text = await Promise.all<string>(
        elements.map(async (element) => common.get_element_text(element)),
    ).then((value) => value);

    return text;
}

async function get_stream_names(page: Page): Promise<string[]> {
    await page.waitForSelector(recent_topic_page);

    const stream_name_cells = ".recent_topic_stream a";
    const stream_names = await get_selector_text(page, stream_name_cells);

    return stream_names;
}

async function get_topic_names(page: Page): Promise<string[]> {
    await page.waitForSelector(recent_topic_page);

    const topic_name_cells = ".recent_topic_name a";
    const topic_names = await get_selector_text(page, topic_name_cells);

    return topic_names;
}

// Tests for streams and topic at initial page load.
async function test_initial_topics(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, [
        "Verona",
        "Denmark",
        "Venice",
        "Denmark",
        "Venice",
        "Verona",
        "Verona",
    ]);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, [
        "last nas is loading",
        "last database linking",
        "URLS",
        "last server wasn't loading slowly",
        "database isn't skipping erratically",
        "plotter",
        "green printer is running quickly",
    ]);
}

async function test_recent_topic(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_recent_topics");
    await page.waitForSelector("#recent_topics_view", {visible: true});

    await test_initial_topics(page);
}

common.run_test(test_recent_topic);
