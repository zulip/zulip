import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function screenshot_docs(page: Page): Promise<void> {
    await page.setViewport({width: 1600, height: 1200});

    await page.goto("http://localhost:4321/change-the-color-of-a-channel");
    await page.waitForSelector("article h1");
    await page.waitForFunction(() => document.fonts.status === "loaded");
    await common.screenshot(page, "help-center-channel-color");

    await page.goto("http://127.0.0.1:8765/var/puppeteer/api-doc-preview.html");
    await page.waitForFunction(() => document.body.innerText.includes("Update a channel"), {
        timeout: 60_000,
    });
    const update_stream = await page.$("#operation/update-stream");
    await update_stream?.evaluate((el) => el.scrollIntoView({block: "start"}));
    await page.waitForFunction(() => document.body.innerText.includes("default_color"));
    await common.screenshot(page, "api-docs-update-channel-color");

    const update_subscription = await page.$("#operation/update-subscription-property");
    await update_subscription?.evaluate((el) => el.scrollIntoView({block: "start"}));
    await page.waitForFunction(() => document.body.innerText.includes("SubscriptionPropertyValue"));
    await common.screenshot(page, "api-docs-reset-channel-color");
}

await common.run_test(screenshot_docs);
