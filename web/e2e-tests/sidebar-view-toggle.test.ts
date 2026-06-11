import assert from "node:assert/strict";
import timersPromises from "node:timers/promises";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

const channels_option_selector = '.sidebar-view-toggle-option[data-view="channels"]';
const inbox_option_selector = '.sidebar-view-toggle-option[data-view="inbox"]';

async function wait_for_aria_checked(
    page: Page,
    selector: string,
    expected: "true" | "false",
): Promise<void> {
    await page.waitForFunction(
        (sel: string, want: string) =>
            document.querySelector(sel)?.getAttribute("aria-checked") === want,
        {},
        selector,
        expected,
    );
}

async function get_attr(page: Page, selector: string, attr: string): Promise<string | null> {
    return await page.$eval(selector, (el, name) => el.getAttribute(name), attr);
}

async function test_initial_state(page: Page): Promise<void> {
    console.log("Verifying initial sidebar-view toggle state");
    await page.waitForSelector(channels_option_selector, {visible: true});
    await page.waitForSelector(inbox_option_selector, {visible: true});

    await wait_for_aria_checked(page, channels_option_selector, "true");
    await wait_for_aria_checked(page, inbox_option_selector, "false");

    // Roving tabindex: only the active radio is in the tab order.
    assert.strictEqual(await get_attr(page, channels_option_selector, "tabindex"), "0");
    assert.strictEqual(await get_attr(page, inbox_option_selector, "tabindex"), "-1");

    // The radiogroup ARIA pattern is what screen readers use to
    // expose the toggle as a single-select; verify it's set.
    assert.strictEqual(await get_attr(page, ".sidebar-view-toggle", "role"), "radiogroup");
}

async function test_toggle_to_inbox(page: Page): Promise<void> {
    console.log("Toggling sidebar to inbox view");
    await page.click(inbox_option_selector);

    // aria-checked is updated through the user_settings dispatch path,
    // which only fires after the server confirms the change — so the
    // attribute flipping is also our persistence signal.
    await wait_for_aria_checked(page, inbox_option_selector, "true");
    await wait_for_aria_checked(page, channels_option_selector, "false");

    // Belt-and-suspenders: confirm the persisted setting matches.
    const persisted = await page.evaluate(() => zulip_test.user_settings.web_left_sidebar_view);
    assert.strictEqual(persisted, "inbox", "web_left_sidebar_view persisted as 'inbox'");

    // Roving tabindex follows the active radio.
    assert.strictEqual(await get_attr(page, inbox_option_selector, "tabindex"), "0");
    assert.strictEqual(await get_attr(page, channels_option_selector, "tabindex"), "-1");
}

type PatchCounter = {
    count: number;
    detach: () => void;
};

function start_counting_view_setting_patches(page: Page): PatchCounter {
    let count = 0;
    const counter = (req: {
        method: () => string;
        url: () => string;
        postData: () => string | undefined;
    }): void => {
        if (
            req.method() === "PATCH" &&
            req.url().endsWith("/json/settings") &&
            (req.postData() ?? "").includes("web_left_sidebar_view")
        ) {
            count += 1;
        }
    };
    page.on("request", counter);
    return {
        get count() {
            return count;
        },
        detach() {
            page.off("request", counter);
        },
    };
}

async function test_click_active_is_noop(page: Page): Promise<void> {
    console.log("Clicking the already-active option should fire zero PATCHes");
    // After test_toggle_to_inbox, inbox is active. Re-clicking it must
    // not fire a PATCH; verify directly via request counting rather
    // than relying on a sleep + DOM check.
    const tracker = start_counting_view_setting_patches(page);
    try {
        await page.click(inbox_option_selector);
        // Brief delay to give any spurious PATCH a chance to actually
        // hit the wire before we read the count.
        await timersPromises.setTimeout(100);
    } finally {
        tracker.detach();
    }
    assert.strictEqual(
        tracker.count,
        0,
        `re-clicking active option should fire 0 PATCHes, fired ${tracker.count}`,
    );
}

async function test_rapid_clicks_in_flight_guard(page: Page): Promise<void> {
    console.log("Rapid clicks should fire exactly one PATCH");
    // Currently in inbox mode. Reset to channels, then count the
    // PATCHes that fire when we rapid-click inbox three times. Without
    // the in-flight guard the second and third clicks would also PATCH;
    // counting requests catches that regression directly.
    await page.click(channels_option_selector);
    await wait_for_aria_checked(page, channels_option_selector, "true");

    const tracker = start_counting_view_setting_patches(page);
    try {
        await page.click(inbox_option_selector);
        await page.click(inbox_option_selector);
        await page.click(inbox_option_selector);
        await wait_for_aria_checked(page, inbox_option_selector, "true");
        // Give any in-flight 2nd/3rd PATCH time to land before counting.
        await timersPromises.setTimeout(250);
    } finally {
        tracker.detach();
    }
    assert.strictEqual(
        tracker.count,
        1,
        `rapid clicks should fire exactly 1 PATCH, fired ${tracker.count}`,
    );
}

async function test_arrow_key_navigation(page: Page): Promise<void> {
    console.log("Arrow keys should move focus between the two options");
    await page.focus(inbox_option_selector);
    await page.keyboard.press("ArrowLeft");
    await page.waitForFunction(
        (sel: string) => document.activeElement === document.querySelector(sel),
        {},
        channels_option_selector,
    );
    await page.keyboard.press("ArrowRight");
    await page.waitForFunction(
        (sel: string) => document.activeElement === document.querySelector(sel),
        {},
        inbox_option_selector,
    );
}

async function test_keyboard_activation(page: Page): Promise<void> {
    console.log("ArrowLeft from inbox + Enter activates the channels option");
    await page.focus(inbox_option_selector);
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("Enter");
    await wait_for_aria_checked(page, channels_option_selector, "true");
}

async function sidebar_view_toggle_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.waitForSelector("#left-sidebar", {visible: true});

    await test_initial_state(page);
    await test_toggle_to_inbox(page);
    await test_click_active_is_noop(page);
    await test_rapid_clicks_in_flight_guard(page);
    await test_arrow_key_navigation(page);
    await test_keyboard_activation(page);
}

await common.run_test(sidebar_view_toggle_test);
