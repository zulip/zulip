import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function click_mute_and_return_last_topic_id(page: Page): Promise<string | undefined> {
    return await page.evaluate(() => {
        const $topic = $('#recent_topics_table tr[id^="recent_topic"]').last();
        const $mute_icon = $topic.find(".on_hover_topic_mute");
        $mute_icon.trigger("click");
        return $topic.attr("id");
    });
}

async function mute_topic_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_recent_topics");
    await page.waitForSelector('#recent_topics_table tr[id^="recent_topic"]', {visible: true});
    const topics_quantitiy = await page.evaluate(
        () => $('#recent_topics_table tr[id^="recent_topic"]').length,
    );
    const last_topic_id = await click_mute_and_return_last_topic_id(page);

    await page.waitForFunction(
        (expected_length: number) =>
            $('#recent_topics_table tr[id^="recent_topic"]').length === expected_length,
        {},
        topics_quantitiy - 1,
    );

    await page.waitForSelector(`#${CSS.escape(last_topic_id!)}`, {hidden: true});
}

common.run_test(mute_topic_test);
