import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function visual_test(page: Page): Promise<void> {
    await common.log_in(page);

    const stream_name = "Denmark";
    const stream_id = await common.get_stream_id(page, stream_name);
    if (stream_id === undefined) {
        throw new Error(`Missing channel ${stream_name}`);
    }

    await page.goto(`${new URL(page.url()).origin}/#channels/${stream_id}/${stream_name}/general`);
    await page.waitForSelector("#stream_settings .choose_default_stream_color", {visible: true});
    await common.screenshot(page, "step-1-channel-default-color-setting");

    await page.click(`.choose_default_stream_color[data-stream-id="${stream_id}"]`);
    await page.waitForSelector(".color-picker-popover", {visible: true});
    await page.click('.color-picker-popover .color-swatch-label[data-swatch-color="#53a063"]');
    await page.waitForFunction(
        (stream_name) => zulip_test.get_sub(stream_name)?.default_color === "#53a063",
        {},
        stream_name,
    );
    await page.click(".color_picker_confirm_button");
    await page.waitForSelector(".color-picker-popover", {hidden: true});
    await common.screenshot(page, "step-2-channel-default-color-set");

    await page.goto(`${new URL(page.url()).origin}/#channels/${stream_id}/${stream_name}/personal`);
    await page.waitForSelector(`.choose_stream_color[data-stream-id="${stream_id}"]`, {
        visible: true,
    });
    await page.click(`.choose_stream_color[data-stream-id="${stream_id}"]`);
    await page.waitForSelector(".color-picker-popover", {visible: true});
    await page.click('.color-picker-popover .color-swatch-label[data-swatch-color="#e79ab5"]');
    await page.waitForFunction(
        (stream_name) =>
            zulip_test.get_sub(stream_name)?.color === "#e79ab5" &&
            !zulip_test.get_sub(stream_name)?.color_is_default,
        {},
        stream_name,
    );
    await page.click(".color_picker_confirm_button");
    await page.waitForSelector(".color-picker-popover", {hidden: true});
    await page.click(`.choose_stream_color[data-stream-id="${stream_id}"]`);
    await page.waitForSelector(".reset-channel-color", {visible: true});
    await common.screenshot(page, "step-3-reset-to-channel-default");
    await page.click(".reset-channel-color");
    await page.waitForFunction(
        (stream_name) =>
            zulip_test.get_sub(stream_name)?.color === "#53a063" &&
            zulip_test.get_sub(stream_name)?.color_is_default,
        {},
        stream_name,
    );

    await page.setViewport({width: 480, height: 900});
    await common.screenshot(page, "step-4-narrow-channel-settings");
}

await common.run_test(visual_test);
