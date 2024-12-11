/* global $, CSS */

import * as fs from "node:fs";
import path from "node:path";
import {parseArgs} from "node:util";

import "css.escape";
import puppeteer from "puppeteer";

const usage = "Usage: message-screenshot.js <message_id> <image_path> <realm_url>";
const {
    values: {help},
    positionals: [messageId, imagePath, realmUrl],
} = parseArgs({options: {help: {type: "boolean"}}, allowPositionals: true});

if (help) {
    console.log(usage);
    process.exit(0);
}
if (realmUrl === undefined) {
    console.error(usage);
    process.exit(1);
}

console.log(`Capturing screenshot for message ${messageId} to ${imagePath}`);

// TODO: Refactor to share code with web/e2e-tests/realm-creation.test.ts
async function run() {
    const browser = await puppeteer.launch({
        args: [
            "--window-size=1400,1024",
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
        await page.setViewport({width: 1280, height: 1024, deviceScaleFactor: 2});
        await page.goto(`${realmUrl}/devlogin`);
        // wait for Iago devlogin button and click on it.
        await page.waitForSelector('[value="iago@zulip.com"]');

        // By waiting till DOMContentLoaded we're confirming that Iago is logged in.
        await Promise.all([
            page.waitForNavigation({waitUntil: "domcontentloaded"}),
            page.click('[value="iago@zulip.com"]'),
        ]);

        // Navigate to message and capture screenshot
        await page.goto(`${realmUrl}/#narrow/id/${messageId}`, {
            waitUntil: "networkidle2",
        });
        // eslint-disable-next-line no-undef
        const message_list_id = await page.evaluate(() => zulip_test.current_msg_list.id);
        const messageSelector = `#message-row-${message_list_id}-${CSS.escape(messageId)}`;
        await page.waitForSelector(messageSelector);
        // remove unread marker and don't select message
        const marker = `#message-row-${message_list_id}-${CSS.escape(messageId)} .unread_marker`;
        await page.evaluate((sel) => $(sel).remove(), marker);
        const messageBox = await page.$(messageSelector);
        await page.evaluate((msg) => $(msg).removeClass("selected_message"), messageSelector);
        const messageGroup = await messageBox.$("xpath/..");
        // Compute screenshot area, with some padding around the message group
        const clip = {...(await messageGroup.boundingBox())};
        clip.x -= 5;
        clip.width += 10;
        clip.y += 5;
        const imageDir = path.dirname(imagePath);
        await fs.promises.mkdir(imageDir, {recursive: true});
        await page.screenshot({path: imagePath, clip});
    } finally {
        await browser.close();
    }
}

await run();
