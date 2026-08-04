import assert from "node:assert/strict";
import {setTimeout as sleep} from "node:timers/promises";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

type PopoverState = {
    open: boolean;
    overlay_backgrounds: number;
    popover_top: number;
    row_top: number;
};

async function read_popover_state(page: Page, user_id: string): Promise<PopoverState> {
    return page.evaluate((user_id) => {
        const popover = document.querySelector("#user_card_popover");
        const popover_rect = popover?.closest(".tippy-box")?.parentElement?.getBoundingClientRect();
        const row = document.querySelector(
            `li.user_sidebar_entry[data-user-id="${CSS.escape(user_id)}"]`,
        );
        return {
            open: popover !== null,
            overlay_backgrounds: document.querySelectorAll("[id='popover-overlay-background']")
                .length,
            popover_top: popover_rect ? Math.round(popover_rect.top) : -1,
            row_top: row ? Math.round(row.getBoundingClientRect().top) : -1,
        };
    }, user_id);
}

async function open_sidebar_user_card(page: Page, row_index: number): Promise<string> {
    const user_id = await page.evaluate((row_index) => {
        const rows = document.querySelectorAll<HTMLElement>("li.user_sidebar_entry");
        const row = rows[row_index];
        if (row === undefined) {
            throw new Error(`No buddy list row at index ${row_index}.`);
        }
        // Blur first, so focus isn't restored to the row (scrolling it back into
        // view) when the popover closes.
        if (document.activeElement instanceof HTMLElement) {
            document.activeElement.blur();
        }
        return row.dataset["userId"]!;
    }, row_index);

    const row_selector = `li.user_sidebar_entry[data-user-id="${user_id}"]`;
    await page.hover(row_selector);
    await page.evaluate((row_selector) => {
        const opener = document
            .querySelector(row_selector)!
            .querySelector<HTMLElement>(".user-list-sidebar-menu-icon, .user-profile-picture");
        if (opener === null) {
            throw new Error("No user card opener found in buddy list row.");
        }
        opener.click();
    }, row_selector);
    await page.waitForSelector("#user_card_popover", {visible: true});
    return user_id;
}

// Popper only repositions on scroll and resize; a resize does so without
// scrolling the anchored row.
async function reposition_popover(page: Page): Promise<void> {
    await page.evaluate(() => {
        window.dispatchEvent(new Event("resize"));
    });
    await sleep(300);
}

async function open_buddy_list(page: Page): Promise<void> {
    await page.waitForSelector("#buddy_list_wrapper", {visible: true});
    await page.waitForSelector("li.user_sidebar_entry", {visible: true});
}

async function test_card_stays_anchored_across_rerender(page: Page): Promise<void> {
    await page.setViewport(common.window_size);
    await open_buddy_list(page);

    const user_id = await open_sidebar_user_card(page, 3);
    const initial = await read_popover_state(page, user_id);
    assert.ok(initial.open, "user card popover should open from the buddy list row.");
    assert.equal(
        initial.overlay_backgrounds,
        0,
        "user card should open anchored to its row, not as a centered overlay.",
    );

    await page.evaluate((user_id) => {
        const row = document.querySelector<HTMLElement>(
            `li.user_sidebar_entry[data-user-id="${CSS.escape(user_id)}"]`,
        )!;
        row.replaceWith(row.cloneNode(true));
    }, user_id);
    await reposition_popover(page);

    const after_rerender = await read_popover_state(page, user_id);
    assert.ok(after_rerender.open, "user card should stay open after its row is rerendered.");
    assert.equal(
        after_rerender.overlay_backgrounds,
        0,
        "user card must stay anchored after a rerender, not become a centered overlay.",
    );

    await page.evaluate((user_id) => {
        const row = document.querySelector(
            `li.user_sidebar_entry[data-user-id="${CSS.escape(user_id)}"]`,
        )!;
        const spacer = document.createElement("li");
        spacer.style.height = "60px";
        row.parentElement!.insertBefore(spacer, row);
    }, user_id);
    await reposition_popover(page);

    const after_shift = await read_popover_state(page, user_id);
    const row_moved = after_shift.row_top - after_rerender.row_top;
    const popover_moved = after_shift.popover_top - after_rerender.popover_top;
    assert.ok(
        Math.abs(popover_moved - row_moved) <= 5,
        `user card should follow its row (row moved ${row_moved}px, card moved ${popover_moved}px).`,
    );
}

async function test_card_hides_when_row_scrolls_away(page: Page): Promise<void> {
    await page.setViewport({width: common.window_size.width, height: 400});
    await open_buddy_list(page);

    const user_id = await open_sidebar_user_card(page, 1);

    const buddy_list = (await page.$("#buddy_list_wrapper"))!;
    const bounds = (await buddy_list.boundingBox())!;
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    await page.mouse.wheel({deltaY: 400});
    await sleep(300);

    const scrolled_away = await page.evaluate((user_id) => {
        const wrapper = document.querySelector("#buddy_list_wrapper")!;
        const row = document.querySelector(
            `li.user_sidebar_entry[data-user-id="${CSS.escape(user_id)}"]`,
        );
        if (row === null) {
            return true;
        }
        return row.getBoundingClientRect().top < wrapper.getBoundingClientRect().top;
    }, user_id);
    assert.ok(
        scrolled_away,
        "the anchored row should scroll out of the buddy list's visible area.",
    );

    const after_scroll = await read_popover_state(page, user_id);
    assert.ok(!after_scroll.open, "user card should hide once its row scrolls out of view.");
    assert.equal(
        after_scroll.overlay_backgrounds,
        0,
        "user card must not recenter itself as an overlay when its row scrolls away.",
    );
}

async function test_narrow_overlay_stays_centered(page: Page): Promise<void> {
    await page.reload({waitUntil: "networkidle2"});
    await page.setViewport({width: 600, height: 800});
    await page.waitForSelector("#userlist-toggle-button", {visible: true});
    await page.click("#userlist-toggle-button");
    await open_buddy_list(page);

    const user_id = await open_sidebar_user_card(page, 1);
    const overlay = await read_popover_state(page, user_id);
    assert.equal(
        overlay.overlay_backgrounds,
        1,
        "user card should be a single centered overlay on a narrow screen.",
    );

    await reposition_popover(page);
    const after_reposition = await read_popover_state(page, user_id);
    assert.ok(after_reposition.open, "centered overlay should stay open across a reposition.");
    assert.equal(
        after_reposition.overlay_backgrounds,
        1,
        "centered overlay should not stack extra backdrops across repositions.",
    );
}

async function test_user_card_popover(page: Page): Promise<void> {
    await common.log_in(page);
    await test_card_stays_anchored_across_rerender(page);
    await test_card_hides_when_row_scrolls_away(page);
    await test_narrow_overlay_stays_centered(page);
}

await common.run_test(test_user_card_popover);
