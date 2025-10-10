/* global $, CSS */

import * as assert from "node:assert/strict";
import * as fs from "node:fs";
import path from "node:path";
import {parseArgs} from "node:util";

import "css.escape";
import puppeteer from "puppeteer";
import * as z from "zod/mini";

const usage =
    "Usage: thread-screenshot.ts <narrow_uri> <narrow> <message_id> <image_path> <realm_url>";
const {
    values: {help},
    positionals,
} = parseArgs({options: {help: {type: "boolean"}}, allowPositionals: true});

if (help) {
    console.log(usage);
    process.exit(0);
}

const parsed = z
    .tuple([
        z.url(),
        z.string(),
        z.string(),
        z.templateLiteral([z.string(), z.enum([".png", ".jpeg", ".webp"])]),
        z.url(),
    ])
    .safeParse(positionals);
if (!parsed.success) {
    console.error(usage);
    process.exit(1);
}
const [narrowUri, narrow, messageId, imagePath, realmUrl] = parsed.data;

console.log(`Capturing screenshot for ${narrow} to ${imagePath}`);

// TODO: Refactor to share code with web/e2e-tests/realm-creation.test.ts
async function run(): Promise<void> {
    const browser = await puppeteer.launch({
        args: [
            "--window-size=500,1024",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            // Helps render fonts correctly on Ubuntu: https://github.com/puppeteer/puppeteer/issues/661
            "--font-render-hinting=none",
        ],
        defaultViewport: null,
        headless: true,
    });
    try {
        const page = await browser.newPage();
        // deviceScaleFactor:2 gives better quality screenshots (higher pixel density)
        await page.setViewport({width: 580, height: 1024, deviceScaleFactor: 2});
        await page.goto(`${realmUrl}/devlogin`);
        // wait for Iago devlogin button and click on it.
        await page.waitForSelector('[value="iago@zulip.com"]');

        // By waiting till DOMContentLoaded we're confirming that Iago is logged in.
        await Promise.all([
            page.waitForNavigation({waitUntil: "domcontentloaded"}),
            page.click('[value="iago@zulip.com"]'),
        ]);

        // Close any banner at the top of the app before taking any screenshots.
        const top_banner_close_button_selector = ".banner-close-action";
        await page.waitForSelector(top_banner_close_button_selector);
        await page.click(top_banner_close_button_selector);

        // Navigate to message and capture screenshot
        await page.goto(narrowUri, {
            waitUntil: "networkidle2",
        });
        // eslint-disable-next-line no-undef
        const message_list_id = await page.evaluate(() => zulip_test.current_msg_list?.id);
        assert.ok(message_list_id !== undefined);
        const messageListSelector = "#message-lists-container";
        await page.waitForSelector(messageListSelector);

        // remove unread marker and don't select message
        const marker = `.message-list[data-message-list-id="${CSS.escape(
            `${message_list_id}`,
        )}"] .unread_marker`;
        await page.evaluate((sel) => {
            $(sel).remove();
        }, marker);

        const messageSelector = `#message-row-${message_list_id}-${CSS.escape(messageId)}`;
        await page.waitForSelector(messageSelector);

        const messageListBox = await page.$(messageListSelector);
        assert.ok(messageListBox !== null);
        await page.evaluate((msg) => $(msg).removeClass("selected_message"), messageSelector);

        // This is done so as to get white background while capturing screenshots.
        const background_selectors = [".app-main", ".message-feed", ".message_header"];
        await page.evaluate((selectors) => {
            for (const selector of selectors) {
                $(selector).css("background-color", "white");
            }
        }, background_selectors);

        // This is done so that the message control buttons are not visible.
        await page.hover(".compose_new_conversation_button");

        // Compute screenshot area, with some padding around the message group
        const box = await messageListBox.boundingBox();
        assert.ok(box !== null);
        const imageDir = path.dirname(imagePath);
        await fs.promises.mkdir(imageDir, {recursive: true});
        await page.screenshot({
            path: imagePath,
            clip: {x: box.x, y: box.y + 10, width: box.width - 70, height: box.height - 8},
        });
    } finally {
        await browser.close();
    }
}

await run();
