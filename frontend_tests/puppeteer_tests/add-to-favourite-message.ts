import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function add_to_favourite_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});

    const $msg = $("#zhome .message_row").first();
    const $star = $msg.find(".star_container.message_control_button.empty-star");

    await page.evaluate(() => $star.trigger("click"));
    await page.waitForFunction(() => !$star.hasClass("empty-star"));
}

common.run_test(add_to_favourite_test);