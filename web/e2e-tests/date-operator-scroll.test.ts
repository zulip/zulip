import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

type DateScrollMeasurement = {
    has_selection: boolean;
    row_top: number | null;
    stuck_header_bottom: number | null;
    gap: number | null;
    clipped: boolean;
};

async function measure_date_anchor_scroll(page: Page): Promise<DateScrollMeasurement> {
    return await page.evaluate(() => {
        const selected = document.querySelector(".focused-message-list .selected_message");
        if (!selected) {
            return {
                has_selection: false,
                row_top: null,
                stuck_header_bottom: null,
                gap: null,
                clipped: false,
            };
        }
        const headers = [
            ...document.querySelectorAll(".focused-message-list .message_header"),
        ] as HTMLElement[];
        const navbar_bottom = document
            .querySelector("#navbar-fixed-container")!
            .getBoundingClientRect().bottom;
        const stuck = headers.find(
            (h) => Math.abs(h.getBoundingClientRect().top - navbar_bottom) < 3,
        );
        const row_top = selected.getBoundingClientRect().top;
        const stuck_header_bottom = stuck?.getBoundingClientRect().bottom ?? null;
        const gap = stuck_header_bottom === null ? null : row_top - stuck_header_bottom;
        const clipped = stuck_header_bottom !== null && row_top < stuck_header_bottom - 1;
        return {
            has_selection: true,
            row_top,
            stuck_header_bottom,
            gap,
            clipped,
        };
    });
}

function assert_not_clipped(measurement: DateScrollMeasurement, label: string): void {
    assert.ok(measurement.has_selection, `${label}: expected a selected message`);
    assert.ok(
        measurement.stuck_header_bottom !== null,
        `${label}: expected a stuck recipient header under the navbar`,
    );
    assert.ok(
        !measurement.clipped,
        `${label}: selected message clipped under sticky recipient header ` +
            `(row_top=${measurement.row_top}, stuck_bottom=${measurement.stuck_header_bottom}, ` +
            `gap=${measurement.gap})`,
    );
    assert.ok(
        measurement.gap !== null && measurement.gap >= -1 && measurement.gap < 30,
        `${label}: unexpected gap between sticky header and selected message: ${measurement.gap}`,
    );
}

async function go_to_hash_and_wait_for_selection(page: Page, hash: string): Promise<void> {
    await page.evaluate((hash: string) => {
        window.location.hash = hash;
    }, hash);
    await page.waitForSelector(".focused-message-list .selected_message", {
        visible: true,
        timeout: 20000,
    });
    // Let sticky-header updates and any backfill scroll settle.
    await new Promise((r) => setTimeout(r, 800));
}

async function date_operator_scroll_test(page: Page): Promise<void> {
    await common.log_in(page);

    const today = await page.evaluate(() => {
        const d = new Date();
        const pad = (n: number) => n.toString().padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    });

    // Multiple topics → multiple recipient headers around the anchored message.
    for (let i = 0; i < 5; i++) {
        await common.send_message(page, "stream", {
            stream_name: "Verona",
            topic: `date-scroll-topic-${i}`,
            content: `date scroll probe message ${i}`,
        });
    }

    // Start from combined feed scrolled toward the bottom, then jump via date:.
    await go_to_hash_and_wait_for_selection(page, "#feed");
    await page.evaluate(() => {
        window.scrollTo(0, document.documentElement.scrollHeight);
    });

    console.log(`Checking date:${today} scroll position`);
    await go_to_hash_and_wait_for_selection(page, `#narrow/date/${today}`);
    assert_not_clipped(await measure_date_anchor_scroll(page), `date:${today}`);

    console.log(`Checking channel + date:${today} scroll position`);
    await go_to_hash_and_wait_for_selection(page, "#feed");
    await go_to_hash_and_wait_for_selection(page, `#narrow/channel/Verona/date/${today}`);
    assert_not_clipped(await measure_date_anchor_scroll(page), `channel/Verona/date/${today}`);
}

common.run_test(date_operator_scroll_test);
