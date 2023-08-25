import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function open_set_user_status_modal(page: Page): Promise<void> {
    const menu_icon_selector = ".user_sidebar_entry:first-child .user-list-sidebar-menu-icon";
    // We are clicking on the menu icon with the help of `waitForFunction` because the list
    // re-renders many times and can cause the element to become stale.
    await page.waitForFunction(
        (selector: string): boolean => {
            const menu_icon = document.querySelector(selector);
            if (menu_icon) {
                (menu_icon as HTMLSpanElement).click();
                return true;
            }
            return false;
        },
        {},
        menu_icon_selector,
    );
    await page.waitForSelector(".user_popover", {visible: true});
    // We are using evaluate to click because it is very hard to detect if the user info popover has opened.
    await page.evaluate(() =>
        document.querySelector<HTMLAnchorElement>(".update_status_text")!.click(),
    );

    // Wait for the modal to completely open.
    await common.wait_for_micromodal_to_open(page);
}

async function test_user_status(page: Page): Promise<void> {
    await open_set_user_status_modal(page);
    // Check by clicking on common statues.
    await page.click(".user-status-value:nth-child(2)");
    await page.waitForFunction(
        () => document.querySelector<HTMLInputElement>(".user-status")!.value === "In a meeting",
    );
    // It should select calendar emoji.
    await page.waitForSelector(".selected-emoji.emoji-1f4c5");

    // Clear everything.
    await page.click("#clear_status_message_button");
    await page.waitForFunction(
        () => document.querySelector<HTMLInputElement>(".user-status")!.value === "",
    );
    await page.waitForSelector(".status-emoji-wrapper .smiley-icon", {visible: true});

    // Manually adding everything.
    await page.type(".user-status", "Busy");
    const tada_emoji_selector = ".emoji-1f389";
    await page.click(".status-emoji-wrapper .smiley-icon");
    // Wait until emoji popover is opened.
    await page.waitForSelector(`.emoji-popover  ${tada_emoji_selector}`, {visible: true});
    await page.click(`.emoji-popover  ${tada_emoji_selector}`);
    await page.waitForSelector(".emoji-picker-popover", {hidden: true});
    await page.waitForSelector(`.selected-emoji${tada_emoji_selector}`);

    await page.click("#set-user-status-modal .dialog_submit_button");
    // It should close the modal after saving.
    await page.waitForSelector("#set-user-status-modal", {hidden: true});

    // Check if the emoji is added in user presence list.
    await page.waitForSelector(`.user-presence-link .status-emoji${tada_emoji_selector}`);
}

async function user_status_test(page: Page): Promise<void> {
    await common.log_in(page);
    await test_user_status(page);
}

common.run_test(user_status_test);
