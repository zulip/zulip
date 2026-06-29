import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

type DateScrollMeasurement = {
    has_selection: boolean;
    row_top: number | null;
    stuck_header_bottom: number | null;
    gap: number | null;
    clipped: boolean;
    selected_id: number | null;
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
                selected_id: null,
            };
        }
        const headers = [
            ...document.querySelectorAll(".focused-message-list .message_header"),
        ] as HTMLElement[];
        const navbar_bottom = document
            .querySelector("#navbar-fixed-container")!
            .getBoundingClientRect().bottom;
        // The CSS position:sticky recipient header that is currently stuck
        // under the navbar — not necessarily the element with .sticky_header,
        // which can lag behind the final scroll position.
        const stuck = headers.find(
            (h) => Math.abs(h.getBoundingClientRect().top - navbar_bottom) < 3,
        );
        const row_top = selected.getBoundingClientRect().top;
        const stuck_header_bottom = stuck?.getBoundingClientRect().bottom ?? null;
        const gap =
            stuck_header_bottom === null ? null : row_top - stuck_header_bottom;
        // Allow 1px of subpixel tolerance.
        const clipped = stuck_header_bottom !== null && row_top < stuck_header_bottom - 1;
        const selected_id = Number(selected.getAttribute("zid"));
        return {
            has_selection: true,
            row_top,
            stuck_header_bottom,
            gap,
            clipped,
            selected_id: Number.isFinite(selected_id) ? selected_id : null,
        };
    });
}

async function navigate_to_date_and_measure(
    page: Page,
    date_operand: string,
): Promise<DateScrollMeasurement> {
    // Start from combined feed so date narrows always go through a full
    // message-list render (including the server-anchor path when local
    // history does not contain the oldest matching message).
    await page.evaluate(() => {
        window.location.hash = "#feed";
    });
    const feed_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${feed_list_id}']`, {
        visible: true,
    });

    await page.evaluate((date_operand: string) => {
        window.location.hash = `#narrow/date/${date_operand}`;
    }, date_operand);

    const date_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${date_list_id}']`, {
        visible: true,
    });
    await page.waitForSelector(".focused-message-list .selected_message", {visible: true});
    // Allow sticky-header bookkeeping and any follow-up backfill scroll
    // adjustments to settle before measuring.
    await page.waitForFunction(() => {
        const selected = document.querySelector(".focused-message-list .selected_message");
        return selected !== null;
    });
    // Small delay for post-scroll sticky updates and older-message fetches
    // that can shift scroll position when history exceeds the local window.
    await new Promise((r) => setTimeout(r, 500));

    return await measure_date_anchor_scroll(page);
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
    // The date-anchored message should sit at (or only slightly below) the
    // sticky header — not substantially lower (which would mean we failed to
    // scroll to the top of the feed) and not above it (clipped).
    assert.ok(
        measurement.gap !== null && measurement.gap >= -1 && measurement.gap < 30,
        `${label}: unexpected gap between sticky header and selected message: ${measurement.gap}`,
    );
}

async function date_operator_scroll_test(page: Page): Promise<void> {
    await common.log_in(page);

    // Send enough messages that a date narrow is meaningful and, on a
    // populated realm, exercises the server-anchor render path. Timestamps
    // are "now", so we use today's date operand.
    const today = await page.evaluate(() => {
        const d = new Date();
        const pad = (n: number) => n.toString().padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    });

    // Multiple topics so we get multiple recipient headers around the
    // anchored message (sticky header interactions are part of the bug).
    for (let i = 0; i < 5; i++) {
        await common.send_message(page, "stream", {
            stream_name: "Verona",
            topic: `date-scroll-topic-${i}`,
            content: `date scroll probe message ${i}`,
        });
    }

    // Also navigate from combined feed after scrolling toward the bottom,
    // which is the usual user path into a date: search.
    await page.evaluate(() => {
        window.location.hash = "#feed";
    });
    await common.get_current_msg_list_id(page, true);
    await page.evaluate(() => {
        window.scrollTo(0, document.documentElement.scrollHeight);
    });

    const dates_to_try = [today];
    // Yesterday and a week ago cover operands that often require the server
    // date anchor when the test realm has any older history.
    const extra_dates = await page.evaluate(() => {
        const fmt = (d: Date) => {
            const pad = (n: number) => n.toString().padStart(2, "0");
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        };
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const week_ago = new Date();
        week_ago.setDate(week_ago.getDate() - 7);
        return [fmt(yesterday), fmt(week_ago)];
    });
    dates_to_try.push(...extra_dates);

    for (const date_operand of dates_to_try) {
        console.log(`Checking date:${date_operand} scroll position`);
        const measurement = await navigate_to_date_and_measure(page, date_operand);
        assert_not_clipped(measurement, `date:${date_operand}`);
    }

    // Channel + date should use the same scroll placement.
    console.log(`Checking channel + date:${today} scroll position`);
    await page.evaluate(() => {
        window.location.hash = "#feed";
    });
    await common.get_current_msg_list_id(page, true);
    await page.evaluate((today: string) => {
        window.location.hash = `#narrow/channel/Verona/date/${today}`;
    }, today);
    const channel_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${channel_list_id}']`, {
        visible: true,
    });
    await page.waitForSelector(".focused-message-list .selected_message", {visible: true});
    await new Promise((r) => setTimeout(r, 500));
    assert_not_clipped(await measure_date_anchor_scroll(page), `channel/Verona/date/${today}`);
}

common.run_test(date_operator_scroll_test);
