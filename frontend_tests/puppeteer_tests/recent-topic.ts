import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

const recent_topic_page = "#recent_topics_view";
const all_filter_button = ".btn-recent-filters[data-filter='all']";
const include_muted_filter_button = ".btn-recent-filters[data-filter='include_muted']";
const unread_filter_button = ".btn-recent-filters[data-filter='unread']";
const participated_filter_button = ".btn-recent-filters[data-filter='participated']";

// Returns an array based on all text found within the selector passed.
async function get_selector_text(page: Page, selector: string): Promise<string[]> {
    const elements = await page.$$(selector);
    const text = await Promise.all<string>(
        elements.map(async (element) => common.get_element_text(element)),
    ).then((value) => value);

    return text;
}

async function trigger_filter_button(page: Page, selector: string): Promise<void> {
    await page.waitForSelector(selector);
    await page.click(selector);
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

// Waits for the recent topics to filter once typed a certain query within
// `filter topic` input field.
async function wait_for_topics_to_filter(page: Page, no_of_topics: number): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    await page.waitForFunction(
        (recent_topic_page: string, no_of_topics: number) => {
            const topics = $(recent_topic_page).find("tbody").find("tr");
            return topics.length === no_of_topics;
        },
        {},
        recent_topic_page,
        no_of_topics,
    );
}

async function clear_input_field(
    page: Page,
    input_field: string,
    input_text: string,
): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Trigger focus to input field in case it loses focus.
    await page.evaluate((input_field: string) => {
        $(input_field).trigger("focus");
    }, input_field);

    for (let i = 0; i < input_text.length; i += 1) {
        await page.keyboard.press("Backspace");
    }

    // Wait for all topics to load back again.
    await wait_for_topics_to_filter(page, 7);
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

// Marks a specific topic as read.
async function mark_as_read(page: Page, topic: string): Promise<void> {
    await page.evaluate((topic: string) => {
        const mark_as_read_icon = $(`.on_hover_topic_read[data-topic-name='${topic}']`);
        mark_as_read_icon.trigger("click");
    }, topic);
}

// Mutes the topic for the corresponding topic name passed.
async function mute_topic(page: Page, topic: string): Promise<void> {
    await page.evaluate((topic: string) => {
        const mute_icon = $(`.on_hover_topic_mute[data-topic-name='${topic}']`);
        mute_icon.trigger("click");
    }, topic);
}

// Should yield same result as `test_initial_topics`.
async function test_all_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `All` filter button.
    await trigger_filter_button(page, all_filter_button);

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

async function test_include_muted_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Include muted` filter button.
    await trigger_filter_button(page, include_muted_filter_button);

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

    // Unchecking the checkbox by clicking the button again.
    await trigger_filter_button(page, include_muted_filter_button);
}

async function test_unread_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Unread` filter button.
    await trigger_filter_button(page, unread_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, []);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, []);

    await trigger_filter_button(page, unread_filter_button);
}

async function test_participated_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Participated` filter button.
    await trigger_filter_button(page, participated_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, ["Venice", "Denmark", "Verona"]);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, ["URLS", "last server wasn't loading slowly", "plotter"]);

    await trigger_filter_button(page, participated_filter_button);
}

async function test_include_muted_and_unread_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Include Muted` and `Unread` filter button.
    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, unread_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, []);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, []);

    // Unchecking the checkboxes again by triggering them.
    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, unread_filter_button);
}

async function test_unread_and_participated_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Unread` and `Participated` filter button.
    await trigger_filter_button(page, unread_filter_button);
    await trigger_filter_button(page, participated_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, []);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, []);

    await trigger_filter_button(page, unread_filter_button);
    await trigger_filter_button(page, participated_filter_button);
}

async function test_include_muted_and_participated_filter_button(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering the `Include muted` and `Participated` filter button.
    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, participated_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, ["Venice", "Denmark", "Verona"]);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, ["URLS", "last server wasn't loading slowly", "plotter"]);

    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, participated_filter_button);
}

async function test_all_filters(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Triggering all filter buttons.
    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, unread_filter_button);
    await trigger_filter_button(page, participated_filter_button);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, []);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, []);

    await trigger_filter_button(page, include_muted_filter_button);
    await trigger_filter_button(page, unread_filter_button);
    await trigger_filter_button(page, participated_filter_button);
}

// Tests the `t` hotkey which navigates back to recent topic page.
async function test_recent_topic_hotkey(page: Page): Promise<void> {
    await page.waitForSelector("#zfilt", {visible: true});
    await page.keyboard.press("t");
    await page.waitForSelector(recent_topic_page, {visible: true});
}

async function test_stream_navigation(page: Page, stream_name: string): Promise<void> {
    await page.waitForSelector(recent_topic_page, {visible: true});

    const stream = await page.evaluate((stream_name: string) => {
        const stream_selector = $(`.recent_topic_stream a:contains('${stream_name}')`).first();
        return stream_selector.attr("href");
    }, stream_name);

    await page.click(`${recent_topic_page} a[href = '${stream}']`);
    await page.waitForSelector("#zfilt", {visible: true});
}

async function test_topic_navigation(page: Page, topic_name: string): Promise<void> {
    await page.waitForSelector(recent_topic_page, {visible: true});

    const topic = await page.evaluate((topic_name: string) => {
        const topic_selector = $(`.recent_topic_name a:contains('${topic_name}')`).first();
        return topic_selector.attr("href");
    }, topic_name);

    await page.click(`${recent_topic_page} a[href = '${topic}']`);
    await page.waitForSelector("#zfilt", {visible: true});
}

async function test_filter_topic_input(page: Page): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    const input_field = "#recent_topics_search";
    const topic_filter = "database";
    const stream_filter = "Verona";

    // Filter topics

    await page.type(input_field, topic_filter);
    // Wait for all topics to filter.
    await wait_for_topics_to_filter(page, 2);

    const filtered_stream_names = await get_stream_names(page);
    assert.deepStrictEqual(filtered_stream_names, ["Denmark", "Venice"]);

    const filtered_topic_names = await get_topic_names(page);
    assert.deepStrictEqual(filtered_topic_names, [
        "last database linking",
        "database isn't skipping erratically",
    ]);

    // Clear the input field.
    await clear_input_field(page, input_field, topic_filter);

    // Filter streams

    await page.type(input_field, stream_filter);
    await wait_for_topics_to_filter(page, 3);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, ["Verona", "Verona", "Verona"]);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, [
        "last nas is loading",
        "plotter",
        "green printer is running quickly",
    ]);

    await clear_input_field(page, input_field, stream_filter);
}

async function test_mark_as_read_button(page: Page, topic: string): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Marking the topic passed as read.
    await mark_as_read(page, topic);

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

async function test_muted_topic_button(page: Page, topic: string): Promise<void> {
    await page.waitForSelector(recent_topic_page);

    // Muting the topic passed.
    await mute_topic(page, topic);

    const stream_names = await get_stream_names(page);
    assert.deepStrictEqual(stream_names, [
        "Verona",
        "Denmark",
        "Denmark",
        "Venice",
        "Verona",
        "Verona",
    ]);

    const topic_names = await get_topic_names(page);
    assert.deepStrictEqual(topic_names, [
        "last nas is loading",
        "last database linking",
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

    await test_all_filter_button(page);
    await test_include_muted_filter_button(page);
    await test_unread_filter_button(page);
    await test_participated_filter_button(page);

    await test_include_muted_and_unread_filter_button(page);
    await test_unread_and_participated_filter_button(page);
    await test_include_muted_and_participated_filter_button(page);
    await test_all_filters(page);

    await test_stream_navigation(page, "Verona");
    await test_recent_topic_hotkey(page); // Tests for 't' hotkey.
    await test_topic_navigation(page, "plotter");
    await test_recent_topic_hotkey(page); // Navigate back to recent topic page.

    await test_filter_topic_input(page); // Inputs `nas` in filter input text field.

    await test_mark_as_read_button(page, "plotter"); // Marks the plotter topic as read.
    await test_muted_topic_button(page, "URLS"); // Mutes the URLS topic.
}

common.run_test(test_recent_topic);
