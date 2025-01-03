/* global $, CSS */

import * as fs from "node:fs";
import path from "node:path";
import {parseArgs} from "node:util";

import "css.escape";
import puppeteer from "puppeteer";

const usage =
    "Usage: thread-screenshot.js <narrow_uri> <narrow> <message_id> <image_path> <realm_url>";
const {
    values: {help},
    positionals: [narrowUri, narrow, messageId, imagePath, realmUrl],
} = parseArgs({options: {help: {type: "boolean"}}, allowPositionals: true});

if (help) {
    console.log(usage);
    process.exit(0);
}
if (realmUrl === undefined) {
    console.error(usage);
    process.exit(1);
}

console.log(`Capturing screenshot for ${narrow} to ${imagePath}`);

// TODO: Refactor to share code with web/e2e-tests/realm-creation.test.ts
async function run() {
    const browser = await puppeteer.launch({
        args: [
            "--window-size=500,1024",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            // Helps render fonts correctly on Ubuntu: https://github.com/puppeteer/puppeteer/issues/661
            "--font-render-hinting=none",
        ],
        defaultViewport: null,
        headless: "new",
    });
    try {
        const page = await browser.newPage();
        // deviceScaleFactor:2 gives better quality screenshots (higher pixel density)
        await page.setViewport({width: 530, height: 1024, deviceScaleFactor: 2});
        await page.goto(`${realmUrl}/devlogin`);
        // wait for Iago devlogin button and click on it.
        await page.waitForSelector('[value="iago@zulip.com"]');

        // By waiting till DOMContentLoaded we're confirming that Iago is logged in.
        await Promise.all([
            page.waitForNavigation({waitUntil: "domcontentloaded"}),
            page.click('[value="iago@zulip.com"]'),
        ]);

        // Navigate to message and capture screenshot
        await page.goto(`${narrowUri}`, {
            waitUntil: "networkidle2",
        });
        // eslint-disable-next-line no-undef
        const message_list_id = await page.evaluate(() => zulip_test.current_msg_list.id);
        const messageListSelector = "#message-lists-container";
        await page.waitForSelector(messageListSelector);

        // remove unread marker and don't select message
        const marker = `.message-list[data-message-list-id="${CSS.escape(
            message_list_id,
        )}"] .unread_marker`;
        await page.evaluate((sel) => {
            $(sel).remove();
        }, marker);

        const messageSelector = `#message-row-${message_list_id}-${CSS.escape(messageId)}`;
        await page.waitForSelector(messageSelector);

        const messageListBox = await page.$(messageListSelector);
        await page.evaluate((msg) => $(msg).removeClass("selected_message"), messageSelector);

        // This is done so as to get white background while capturing screenshots.
        const background_selectors = [".app-main", ".message-feed", ".message_header"];
        await page.evaluate((selectors) => {
            for (const selector of selectors) {
                $(selector).css("background-color", "white");
            }
        }, background_selectors);

        // Compute screenshot area, with some padding around the message group
        const clip = {...(await messageListBox.boundingBox())};
        clip.width -= 64;
        clip.y += 10;
        clip.height -= 8;
        const imageDir = path.dirname(imagePath);
        await fs.promises.mkdir(imageDir, {recursive: true});
        await page.screenshot({path: imagePath, clip});
    } finally {
        await browser.close();
    }
}

await run();
